"""
Download audio from YouTube videos and playlists directly into the music library.

The download is performed by `yt-dlp <https://github.com/yt-dlp/yt-dlp>`_ and requires the ``ffmpeg``
binary to be installed on the system for the audio extraction / conversion step.

If no destination folder is given, a new folder named after the video's (or playlist's) title is
created in the music library root. Downloads run in a background thread so the RPC call returns
immediately; progress and the final result are published on the ``library.youtube.progress`` topic
via the regular ZMQ publisher, so any subscriber (e.g. the WebUI) can follow along.
"""

import logging
import re
import threading
import time

import yt_dlp

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.publishing as publishing
from jukebox.library import (
    LibraryError,
    create_music_library,
    resolve_library_path,
)

logger = logging.getLogger('jb.youtube')
cfg = jukebox.cfghandler.get_handler('jukebox')

#: Topic on which download progress / result is published
PROGRESS_TOPIC = 'library.youtube.progress'

_INVALID_FOLDER_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WHITESPACE_RE = re.compile(r'\s+')
_MAX_FOLDER_NAME_LENGTH = 120
_PROGRESS_THROTTLE_SEC = 0.5


class YoutubeDownloadError(Exception):
    """Raised for download failures that are not already a :class:`LibraryError`"""


def _sanitize_folder_name(title: str) -> str:
    """Turn a video / playlist title into a safe, single-level folder name"""
    name = _INVALID_FOLDER_CHARS_RE.sub('_', title or '')
    name = _WHITESPACE_RE.sub(' ', name).strip().strip('.')
    return name[:_MAX_FOLDER_NAME_LENGTH] or 'YouTube Download'


class _YtDlpLogger:
    """Route yt-dlp's internal log messages into the Jukebox logger"""

    def __init__(self):
        self.last_error = None

    def debug(self, msg):
        # yt-dlp also routes non-debug info messages through debug() prefixed with '[debug] '
        if msg.startswith('[debug] '):
            logger.debug(msg)
        else:
            self.info(msg)

    def info(self, msg):
        logger.debug(msg)

    def warning(self, msg):
        logger.warning(msg)

    def error(self, msg):
        self.last_error = msg
        logger.error(msg)


class YoutubeDownload:
    """Control class for downloading YouTube audio into the music library"""

    def __init__(self):
        with cfg:
            self._enabled = cfg.setndefault('youtube', 'enable', value=False) is True
            self._audio_format = cfg.setndefault('youtube', 'audio_format', value='mp3')
        if self._enabled:
            logger.info("YouTube download enabled")
        else:
            logger.info("YouTube download deactivated")
        # Only a single download at a time is supported for now
        self._lock = threading.Lock()
        self._last_progress_publish = 0.0

    @plugs.tag
    def download(self, url: str, folder: str = '') -> dict:
        """
        Download the audio of a YouTube video or playlist into the music library.

        The call returns immediately; the download itself runs in a background thread.
        Subscribe to the topic :attr:`PROGRESS_TOPIC` to follow progress and completion / errors.

        :param url: URL of a YouTube video or playlist
        :param folder: Library folder (path relative to the music library) to download into.
            Leave empty to create a new folder named after the video's / playlist's title.
        :return: ``{'accepted': True}`` if the download was started, or
            ``{'accepted': False, 'message': str}`` if it was rejected right away
        """
        if not isinstance(url, str) or not url.strip():
            message = "A YouTube URL is required."
            self._publish_progress(state='error', message=message, url=url)
            return {'accepted': False, 'message': message}

        if not self._enabled:
            message = "YouTube download is disabled in the Jukebox configuration."
            logger.error(message)
            self._publish_progress(state='error', message=message, url=url)
            return {'accepted': False, 'message': message}

        if not self._lock.acquire(blocking=False):
            message = "A YouTube download is already in progress."
            logger.warning(message)
            self._publish_progress(state='error', message=message, url=url)
            return {'accepted': False, 'message': message}

        threading.Thread(
            target=self._download_worker,
            args=(url, folder),
            daemon=True,
            name='YoutubeDownload',
        ).start()
        return {'accepted': True}

    def _download_worker(self, url: str, folder: str):
        try:
            self._run_download(url, folder)
        except Exception as error:  # last resort so the background thread never dies silently
            logger.error(f"YouTube download failed: {error.__class__.__name__}: {error}", exc_info=True)
            self._publish_progress(state='error', message=str(error), url=url)
        finally:
            self._lock.release()

    def _run_download(self, url: str, folder: str):
        library = create_music_library()
        self._publish_progress(state='preparing', message='Fetching video information', url=url)

        try:
            target_dir, folder_relpath = self._resolve_target_directory(library, url, folder)
        except (LibraryError, YoutubeDownloadError, OSError) as error:
            message = error.message if isinstance(error, LibraryError) else str(error)
            logger.error(f"Could not prepare download folder for '{url}': {message}")
            self._publish_progress(state='error', message=message, url=url)
            return

        self._last_progress_publish = 0.0
        self._publish_progress(state='downloading', percent=0, url=url, folder=folder_relpath)
        try:
            self._run_ytdlp(url, target_dir, folder_relpath)
        except (yt_dlp.utils.DownloadError, YoutubeDownloadError) as error:
            logger.error(f"YouTube download failed for '{url}': {error}")
            self._publish_progress(state='error', message=str(error), url=url, folder=folder_relpath)
            return

        logger.info(f"YouTube download of '{url}' finished into '{folder_relpath}'")
        # Refresh MPD's library so the new files show up immediately
        plugs.call_ignore_errors('player', 'ctrl', 'update')
        self._publish_progress(state='complete', percent=100, url=url, folder=folder_relpath)

    def _resolve_target_directory(self, library, url: str, folder: str):
        root = library.root
        if folder:
            target_dir = resolve_library_path(root, folder, require_exists=True)
            if not target_dir.is_dir():
                raise LibraryError(400, 'not_a_folder', 'The destination path is not a folder.')
            return target_dir, target_dir.relative_to(root).as_posix()

        title = self._probe_title(url)
        relpath = self._create_unique_folder(library, _sanitize_folder_name(title))
        target_dir = resolve_library_path(root, relpath, require_exists=True)
        return target_dir, relpath

    @staticmethod
    def _create_unique_folder(library, base_name: str) -> str:
        """Create a folder named ``base_name`` in the library root, appending a counter on clashes"""
        candidate = base_name
        last_error = None
        for suffix in range(2, 100):
            try:
                return library.create_folder('', candidate)
            except LibraryError as error:
                if error.code != 'duplicate_name':
                    raise
                last_error = error
                candidate = f"{base_name} ({suffix})"
        raise YoutubeDownloadError(
            f"Could not find an available folder name for '{base_name}'."
        ) from last_error

    @staticmethod
    def _probe_title(url: str) -> str:
        """Fetch just enough metadata to name the destination folder, without downloading"""
        probe_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': 'in_playlist',
            'logger': _YtDlpLogger(),
        }
        try:
            with yt_dlp.YoutubeDL(probe_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as error:
            raise YoutubeDownloadError(str(error)) from error
        if not info:
            raise YoutubeDownloadError('Could not read video information from the given URL.')
        return info.get('title') or 'YouTube Download'

    def _run_ytdlp(self, url: str, target_dir, folder_relpath: str):
        ytdlp_logger = _YtDlpLogger()
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(target_dir / '%(title)s.%(ext)s'),
            'writethumbnail': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': self._audio_format,
                    'preferredquality': '192',
                },
                {'key': 'FFmpegMetadata'},
                {'key': 'EmbedThumbnail'},
            ],
            # 'only_download' lets a playlist skip a broken entry and continue with the
            # rest, but it also means yt-dlp reports success (return code 0) even when
            # every item failed - the return code below is what actually catches that.
            'ignoreerrors': 'only_download',
            'quiet': True,
            'no_warnings': True,
            'logger': ytdlp_logger,
            'progress_hooks': [lambda status: self._progress_hook(status, url, folder_relpath)],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return_code = ydl.download([url])
        if return_code:
            raise YoutubeDownloadError(
                ytdlp_logger.last_error or 'yt-dlp reported an error; see the Jukebox log for details.'
            )

    def _progress_hook(self, status: dict, url: str, folder_relpath: str):
        state = status.get('status')
        info = status.get('info_dict') or {}
        if state == 'downloading':
            now = time.monotonic()
            if now - self._last_progress_publish < _PROGRESS_THROTTLE_SEC:
                return
            self._last_progress_publish = now
            downloaded = status.get('downloaded_bytes') or 0
            total = status.get('total_bytes') or status.get('total_bytes_estimate')
            percent = round(downloaded * 100 / total, 1) if total else None
            self._publish_progress(
                state='downloading',
                percent=percent,
                title=info.get('title'),
                url=url,
                folder=folder_relpath,
            )
        elif state == 'finished':
            self._publish_progress(
                state='converting',
                percent=100,
                title=info.get('title'),
                url=url,
                folder=folder_relpath,
            )

    @staticmethod
    def _publish_progress(**payload):
        publishing.get_publisher().send(PROGRESS_TOPIC, payload)


# ---------------------------------------------------------------------------
# Plugin Initializer
# ---------------------------------------------------------------------------

youtube_ctrl: YoutubeDownload


@plugs.initialize
def initialize():
    global youtube_ctrl
    youtube_ctrl = YoutubeDownload()
    plugs.register(youtube_ctrl, name='ctrl')
