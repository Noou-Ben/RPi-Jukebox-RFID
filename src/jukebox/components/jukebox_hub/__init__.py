"""
Download playlists from an external "Jukebox Hub" server directly into the music library.

This mirrors the :mod:`components.youtube` component: a playlist's tracks are downloaded
via plain HTTP(S) from the configured Jukebox Hub instance (``jukebox_hub.url`` /
``jukebox_hub.api_key`` in the Jukebox configuration). Listing the available playlists is a
fast, synchronous RPC call. Downloading a playlist's tracks runs in a background thread so the
RPC call returns immediately; progress and the final result are published on the
``library.jukebox_hub.progress`` topic via the regular ZMQ publisher, so any subscriber (e.g.
the WebUI) can follow along.
"""

import logging
import mimetypes
import re
import threading

import requests

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.publishing as publishing
from jukebox.library import (
    LibraryError,
    create_music_library,
    resolve_library_path,
)

logger = logging.getLogger('jb.jukebox_hub')
cfg = jukebox.cfghandler.get_handler('jukebox')

#: Topic on which download progress / result is published
PROGRESS_TOPIC = 'library.jukebox_hub.progress'

_INVALID_FOLDER_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WHITESPACE_RE = re.compile(r'\s+')
_MAX_FOLDER_NAME_LENGTH = 120
_REQUEST_TIMEOUT_SEC = 10
_DOWNLOAD_TIMEOUT_SEC = 60
_DOWNLOAD_CHUNK_SIZE = 64 * 1024

# Fallback extension when neither the Content-Type header nor the original track title /
# download URL give us a usable one.
_DEFAULT_EXTENSION = 'mp3'


class JukeboxHubError(Exception):
    """Raised for download failures that are not already a :class:`LibraryError`"""


def _sanitize_folder_name(title: str) -> str:
    """Turn a playlist title into a safe, single-level folder name"""
    name = _INVALID_FOLDER_CHARS_RE.sub('_', title or '')
    name = _WHITESPACE_RE.sub(' ', name).strip().strip('.')
    return name[:_MAX_FOLDER_NAME_LENGTH] or 'Jukebox Hub Download'


def _sanitize_file_name(title: str) -> str:
    """Turn a track title into a safe file name component (no extension)"""
    name = _INVALID_FOLDER_CHARS_RE.sub('_', title or '')
    name = _WHITESPACE_RE.sub(' ', name).strip().strip('.')
    return name[:_MAX_FOLDER_NAME_LENGTH] or 'track'


def _build_url(base_url: str, path: str) -> str:
    """Join a Jukebox Hub base URL with an absolute path returned by the API"""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _extension_from_content_disposition(content_disposition: str):
    if not content_disposition:
        return None
    match = re.search(r'filename="?([^";]+)"?', content_disposition)
    if not match:
        return None
    filename = match.group(1)
    if '.' in filename:
        return filename.rsplit('.', 1)[-1].strip()
    return None


def _extension_from_content_type(content_type: str):
    if not content_type:
        return None
    # mimetypes also returns things like '.jpe' for some audio-adjacent types; good enough here
    guessed = mimetypes.guess_extension(content_type.split(';')[0].strip())
    return guessed.lstrip('.') if guessed else None


class JukeboxHubDownload:
    """Control class for downloading Jukebox Hub playlists into the music library"""

    def __init__(self):
        with cfg:
            self._enabled = cfg.setndefault('jukebox_hub', 'enable', value=False) is True
            self._url = cfg.setndefault('jukebox_hub', 'url', value='')
            self._api_key = cfg.setndefault('jukebox_hub', 'api_key', value='')
        if self._enabled:
            logger.info("Jukebox Hub download enabled")
        else:
            logger.info("Jukebox Hub download deactivated")
        # Only a single download at a time is supported for now
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        headers = {}
        if self._api_key:
            headers['X-Api-Key'] = self._api_key
        return headers

    def _get_json(self, path: str):
        url = _build_url(self._url, path)
        response = requests.get(url, headers=self._headers(), timeout=_REQUEST_TIMEOUT_SEC)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # RPC: configuration (get_status / set_config)
    # ------------------------------------------------------------------

    @plugs.tag
    def get_status(self) -> dict:
        """Return the current Jukebox Hub configuration, for the WebUI settings panel"""
        return {
            'enable': self._enabled,
            'url': self._url,
            'api_key': self._api_key,
        }

    @plugs.tag
    def set_config(self, enable=None, url=None, api_key=None) -> dict:
        """
        Persist Jukebox Hub configuration changes (WebUI settings panel).

        Any argument left as ``None`` is left unchanged. Takes effect immediately for
        subsequent :meth:`list_playlists` / :meth:`download_playlist` calls, no Jukebox
        Core restart required.
        """
        with cfg:
            if enable is not None:
                self._enabled = enable is True
                cfg.setn('jukebox_hub', 'enable', value=self._enabled)
            if url is not None:
                self._url = url
                cfg.setn('jukebox_hub', 'url', value=self._url)
            if api_key is not None:
                self._api_key = api_key
                cfg.setn('jukebox_hub', 'api_key', value=self._api_key)
            cfg.save(only_if_changed=True)
        return self.get_status()

    # ------------------------------------------------------------------
    # RPC: list_playlists
    # ------------------------------------------------------------------

    @plugs.tag
    def list_playlists(self) -> list:
        """
        List the playlists available on the configured Jukebox Hub server.

        This is a fast, synchronous call. Connection errors are logged and result in an
        empty list being returned rather than raising, so callers (e.g. the WebUI) can show
        a "could not reach the Hub" message instead of getting a failed RPC call.

        :return: A list of ``{id, name, track_count, updated_at}`` dicts, or an empty list
            if the Hub could not be reached or is disabled / not configured.
        """
        if not self._enabled:
            logger.warning("Jukebox Hub is disabled in the Jukebox configuration.")
            return []
        if not self._url:
            logger.warning("Jukebox Hub URL is not configured.")
            return []

        try:
            playlists = self._get_json('/api/box/playlists')
        except requests.exceptions.RequestException as error:
            logger.error(f"Could not reach Jukebox Hub at '{self._url}': {error}")
            return []
        except ValueError as error:
            # response.json() failed to parse
            logger.error(f"Jukebox Hub returned an invalid response: {error}")
            return []

        if not isinstance(playlists, list):
            logger.error("Jukebox Hub returned an unexpected playlists response.")
            return []
        return playlists

    # ------------------------------------------------------------------
    # RPC: download_playlist
    # ------------------------------------------------------------------

    @plugs.tag
    def download_playlist(self, playlist_id, folder: str = '') -> dict:
        """
        Download all tracks of a Jukebox Hub playlist into the music library.

        The call returns immediately; the download itself runs in a background thread.
        Subscribe to the topic :attr:`PROGRESS_TOPIC` to follow progress and completion /
        errors.

        :param playlist_id: id of the playlist on the Jukebox Hub server
        :param folder: Library folder (path relative to the music library) to download
            into. Leave empty to create a new folder named after the playlist's name.
        :return: ``{'accepted': True}`` if the download was started, or
            ``{'accepted': False, 'message': str}`` if it was rejected right away
        """
        if playlist_id is None or (isinstance(playlist_id, str) and not playlist_id.strip()):
            message = "A Jukebox Hub playlist id is required."
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return {'accepted': False, 'message': message}

        if not self._enabled:
            message = "Jukebox Hub download is disabled in the Jukebox configuration."
            logger.error(message)
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return {'accepted': False, 'message': message}

        if not self._url:
            message = "Jukebox Hub URL is not configured."
            logger.error(message)
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return {'accepted': False, 'message': message}

        if not self._lock.acquire(blocking=False):
            message = "A Jukebox Hub download is already in progress."
            logger.warning(message)
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return {'accepted': False, 'message': message}

        threading.Thread(
            target=self._download_worker,
            args=(playlist_id, folder),
            daemon=True,
            name='JukeboxHubDownload',
        ).start()
        return {'accepted': True}

    def _download_worker(self, playlist_id, folder: str):
        try:
            self._run_download(playlist_id, folder)
        except Exception as error:  # last resort so the background thread never dies silently
            logger.error(
                f"Jukebox Hub download failed: {error.__class__.__name__}: {error}", exc_info=True
            )
            self._publish_progress(state='error', message=str(error), playlist_id=playlist_id)
        finally:
            self._lock.release()

    def _run_download(self, playlist_id, folder: str):
        library = create_music_library()
        self._publish_progress(state='preparing', message='Fetching playlist information', playlist_id=playlist_id)

        try:
            playlist = self._get_json(f'/api/box/playlists/{playlist_id}')
        except requests.exceptions.RequestException as error:
            message = f"Could not fetch playlist from Jukebox Hub: {error}"
            logger.error(message)
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return
        except ValueError as error:
            message = f"Jukebox Hub returned an invalid playlist response: {error}"
            logger.error(message)
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return

        if not isinstance(playlist, dict):
            message = "Jukebox Hub returned an unexpected playlist response."
            logger.error(message)
            self._publish_progress(state='error', message=message, playlist_id=playlist_id)
            return

        playlist_name = playlist.get('name') or 'Jukebox Hub Download'
        tracks = playlist.get('tracks') or []

        if not tracks:
            message = f"Playlist '{playlist_name}' has no tracks."
            logger.error(message)
            self._publish_progress(
                state='error', message=message, playlist_id=playlist_id, playlist_name=playlist_name,
            )
            return

        try:
            target_dir, folder_relpath = self._resolve_target_directory(library, playlist_name, folder)
        except (LibraryError, JukeboxHubError, OSError) as error:
            message = error.message if isinstance(error, LibraryError) else str(error)
            logger.error(f"Could not prepare download folder for playlist '{playlist_name}': {message}")
            self._publish_progress(
                state='error', message=message, playlist_id=playlist_id, playlist_name=playlist_name,
            )
            return

        total = len(tracks)
        self._publish_progress(
            state='downloading',
            percent=0,
            current_track=0,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            folder=folder_relpath,
            message=f"Downloading 0 of {total} tracks",
        )

        for index, track in enumerate(tracks, start=1):
            try:
                self._download_track(target_dir, index, track)
            except (requests.exceptions.RequestException, OSError, JukeboxHubError) as error:
                message = f"Failed to download track '{track.get('title', '?')}': {error}"
                logger.error(message)
                self._publish_progress(
                    state='error',
                    message=message,
                    playlist_id=playlist_id,
                    playlist_name=playlist_name,
                    folder=folder_relpath,
                    current_track=index,
                )
                return

            percent = round(index * 100 / total, 1)
            self._publish_progress(
                state='downloading',
                percent=percent,
                current_track=index,
                playlist_id=playlist_id,
                playlist_name=playlist_name,
                folder=folder_relpath,
                message=f"Downloaded {index} of {total} tracks",
            )

        logger.info(f"Jukebox Hub download of playlist '{playlist_name}' finished into '{folder_relpath}'")
        # Refresh MPD's library so the new files show up immediately
        plugs.call_ignore_errors('player', 'ctrl', 'update')
        self._publish_progress(
            state='complete',
            percent=100,
            current_track=total,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            folder=folder_relpath,
            message='Download complete',
        )

    def _resolve_target_directory(self, library, playlist_name: str, folder: str):
        root = library.root
        # The WebUI's "library root" sentinel is './' (see ROOT_DIR in src/webapp/src/config.js),
        # not an empty string - treat it the same as "no folder given" so downloading from the
        # library root still gets its own new folder instead of landing directly in the root.
        if folder and folder.strip().strip('/') not in ('', '.'):
            target_dir = resolve_library_path(root, folder, require_exists=True)
            if not target_dir.is_dir():
                raise LibraryError(400, 'not_a_folder', 'The destination path is not a folder.')
            return target_dir, target_dir.relative_to(root).as_posix()

        relpath = self._create_unique_folder(library, _sanitize_folder_name(playlist_name))
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
        raise JukeboxHubError(
            f"Could not find an available folder name for '{base_name}'."
        ) from last_error

    def _download_track(self, target_dir, index: int, track: dict):
        download_url = track.get('download_url')
        if not download_url:
            raise JukeboxHubError(f"Track '{track.get('title', '?')}' has no download_url.")

        url = _build_url(self._url, download_url)
        with requests.get(
            url, headers=self._headers(), stream=True, timeout=_DOWNLOAD_TIMEOUT_SEC,
        ) as response:
            response.raise_for_status()

            extension = (
                _extension_from_content_disposition(response.headers.get('Content-Disposition', ''))
                or _extension_from_content_type(response.headers.get('Content-Type', ''))
                or _DEFAULT_EXTENSION
            )
            title = track.get('title') or f'Track {index}'
            file_name = f"{index:02d} - {_sanitize_file_name(title)}.{extension}"
            target_path = target_dir / file_name

            with open(target_path, 'wb') as file_handle:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        file_handle.write(chunk)

    @staticmethod
    def _publish_progress(**payload):
        publishing.get_publisher().send(PROGRESS_TOPIC, payload)


# ---------------------------------------------------------------------------
# Plugin Initializer
# ---------------------------------------------------------------------------

jukebox_hub_ctrl: JukeboxHubDownload


@plugs.initialize
def initialize():
    global jukebox_hub_ctrl
    jukebox_hub_ctrl = JukeboxHubDownload()
    plugs.register(jukebox_hub_ctrl, name='ctrl')
