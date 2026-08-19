# -*- coding: utf-8 -*-
"""
Player backend for Spotify Connect playback via `go-librespot`

Design decision: librespot flavor
----------------------------------
Spotify playback support in v2 ("+Spotify Edition") is built on Mopidy +
`mopidy-spotify`, which in turn wraps `libspotify`. `libspotify` was
deprecated by Spotify years ago, is unmaintained, and `mopidy-spotify`'s
successor (using `librespot`) has never reached a stable release. Pulling
in the whole Mopidy/MPD-alternative stack just for Spotify would also be a
heavy, largely unmaintained dependency for v3.

Instead this backend drives `go-librespot` (https://github.com/devgianlu/go-librespot),
an actively maintained, open-source Spotify Connect client written in Go. It was chosen
over the original Rust `librespot` and over `librespot-python` because it is the only
option of the three that ships a local REST API + WebSocket event stream for playback
control and status (`server.enabled` in its config) -- exactly the kind of "JSON API"
integration point this backend needs. (This module only uses the REST API, polled on
an interval like the existing MPD backend does, to keep the implementation close to
the established pattern in this codebase; the WebSocket event stream would be a lower-
latency alternative for a future iteration.) It is a single self-contained binary (no
Python extension building, no libspotify), and its default authentication mode is Spotify
Connect "Zeroconf" discovery: the box simply advertises itself on the local network and
the user picks it as a playback target from the official Spotify app, the same way they
would pick a Sonos speaker or a Chromecast. No Spotify Developer app registration, no
OAuth client secret, and -- unlike a stored username/password -- no Spotify account
credentials are ever entered into or stored by the Jukebox.

The trade-off: playback is *received* via Spotify Connect. The Spotify app (or Desktop
client) on the user's phone/computer remains the primary transport control. This backend
still forwards play/pause/next/prev/seek/volume from the Jukebox UI to `go-librespot`'s
REST API (so RFID card actions like "pause" or physical buttons keep working while a
Spotify session is active), but there is currently no way to *start* a specific playlist
or track from an RFID card without the Spotify Web API (OAuth), which is out of scope for
this first pass -- see `documentation/developers/status.md`.

This backend spawns no process and opens no sockets until its `enable()` method is
called - see `components/spotify/__init__.py`, which calls it at startup only if
`spotify.enable` is `true` in `jukebox.yaml` (default: `false`), and also exposes it as
a runtime-toggleable RPC so Spotify support can be turned on/off from the Web UI without
restarting the Jukebox Core.

> [!WARNING]
> This implementation could not be tested against a live Spotify session (no Spotify
> Premium account / no real device was available while writing it). The REST API shapes
> below are transcribed from `go-librespot`'s published OpenAPI spec
> (https://github.com/devgianlu/go-librespot/blob/master/api-spec.yml) as of 2026, not
> verified against a running instance. Treat this as a best-effort starting point.
"""
import logging
import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from ruamel.yaml import YAML

import jukebox.cfghandler
import jukebox.multitimer as multitimer
import jukebox.plugs as plugs
import jukebox.publishing as publishing

logger = logging.getLogger('jb.PlayerSpotify')
cfg = jukebox.cfghandler.get_handler('jukebox')


class GoLibrespotError(Exception):
    """Raised when the go-librespot REST API cannot be reached or returns an error"""


class GoLibrespotClient:
    """Thin REST client for the `go-librespot` local API

    API reference: https://github.com/devgianlu/go-librespot/blob/master/api-spec.yml
    """

    def __init__(self, host: str, port: int, timeout: float = 2.0):
        self.base_url = f'http://{host}:{port}'
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> Optional[requests.Response]:
        try:
            response = requests.request(method, f'{self.base_url}{path}', timeout=self.timeout, **kwargs)
        except requests.exceptions.RequestException as e:
            raise GoLibrespotError(f"Could not reach go-librespot API at {self.base_url}: {e}") from e
        if response.status_code >= 400:
            raise GoLibrespotError(f"go-librespot API returned {response.status_code} for {method} {path}")
        return response

    def status(self) -> Optional[Dict[str, Any]]:
        """Return the current player status, or None if there is no active session (HTTP 204)"""
        response = self._request('GET', '/status')
        if response is None or response.status_code == 204 or not response.content:
            return None
        return response.json()

    def play(self):
        self._request('POST', '/player/resume')

    def pause(self):
        self._request('POST', '/player/pause')

    def playpause(self):
        self._request('POST', '/player/playpause')

    def stop(self):
        self._request('POST', '/player/stop')

    def next(self):
        self._request('POST', '/player/next')

    def prev(self):
        self._request('POST', '/player/prev')

    def seek(self, position_ms: int):
        self._request('POST', '/player/seek', json={'position': int(position_ms)})

    def get_volume(self) -> Dict[str, Any]:
        response = self._request('GET', '/player/volume')
        return response.json()

    def set_volume(self, volume: int, relative: bool = False):
        self._request('POST', '/player/volume', json={'volume': int(volume), 'relative': relative})

    def shuffle_context(self, enabled: bool):
        self._request('POST', '/player/shuffle_context', json={'shuffle_context': enabled})

    def repeat_context(self, enabled: bool):
        self._request('POST', '/player/repeat_context', json={'repeat_context': enabled})

    def repeat_track(self, enabled: bool):
        self._request('POST', '/player/repeat_track', json={'repeat_track': enabled})

    def play_uri(self, uri: str):
        self._request('POST', '/player/play', json={'uri': uri})


def _write_go_librespot_config(config_dir: str, options: Dict[str, Any]) -> None:
    """Generate the `config.yml` consumed by `go-librespot` from Jukebox settings

    Only a subset of the full go-librespot configuration schema is exposed through
    `jukebox.yaml`; everything else keeps go-librespot's own defaults. Advanced users
    can still hand-edit the generated file, but it will be overwritten on next startup.
    """
    os.makedirs(config_dir, exist_ok=True)
    config_path = Path(config_dir) / 'config.yml'

    document = {
        'device_name': options['device_name'],
        'device_type': 'speaker',
        'audio_backend': options['audio_backend'],
        'audio_device': options['audio_device'],
        'zeroconf_enabled': True,
        'credentials': {
            'type': options['credentials_type'],
            'zeroconf': {
                'persist_credentials': options['persist_credentials'],
            },
        },
        'server': {
            'enabled': True,
            'address': options['api_host'],
            'port': options['api_port'],
        },
    }

    yaml = YAML()
    yaml.default_flow_style = False
    with open(config_path, 'w') as f:
        yaml.dump(document, f)
    logger.debug(f"Wrote go-librespot config to '{config_path}'")


def _map_state(status: Optional[Dict[str, Any]]) -> str:
    if status is None:
        return 'stop'
    if status.get('stopped'):
        return 'stop'
    if status.get('paused'):
        return 'pause'
    return 'play'


class PlayerSpotify:
    """Interface to a Spotify Connect session, managed via a local `go-librespot` process

    Implements the subset of the provider-neutral player backend interface (see
    :mod:`components.player.coordinator`) that maps onto Spotify Connect playback.
    Library/folder-browsing methods that have no Spotify Connect equivalent
    (they would require the Spotify Web API) raise :class:`NotImplementedError`.
    """

    def __init__(self):
        self.device_name = cfg.setndefault('spotify', 'device_name', value='Phoniebox')
        self.binary_path = os.path.expanduser(
            cfg.setndefault('spotify', 'binary_path', value='../../shared/spotify/bin/go-librespot'))
        self.config_dir = os.path.expanduser(
            cfg.setndefault('spotify', 'config_dir', value='../../shared/spotify'))
        self.api_host = cfg.setndefault('spotify', 'api_host', value='127.0.0.1')
        self.api_port = cfg.setndefault('spotify', 'api_port', value=3678)
        self.audio_backend = cfg.setndefault('spotify', 'audio_backend', value='pulseaudio')
        self.audio_device = cfg.setndefault('spotify', 'audio_device', value='default')
        # 'zeroconf' (default): no credentials ever touch the Jukebox, user pairs the
        # device from the Spotify app, exactly like a Chromecast/Sonos speaker.
        # 'spotify_token'/'interactive' are supported by go-librespot but not wired up
        # here yet - see documentation/developers/status.md.
        self.credentials_type = cfg.setndefault('spotify', 'credentials_type', value='zeroconf')
        self.persist_credentials = cfg.setndefault('spotify', 'persist_credentials', value=False)
        self.status_poll_interval = cfg.setndefault('spotify', 'status_poll_interval_sec', value=1.0)

        self.client = GoLibrespotClient(self.api_host, self.api_port)
        self._process: Optional[subprocess.Popen] = None
        self._process_lock = threading.RLock()
        self._active = False
        self._enabled = False
        self._last_status: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None

        # Constructing a PlayerSpotify instance does *not* spawn go-librespot or start
        # polling: this only happens once enable() is called. This is what lets
        # components.spotify register the backend unconditionally (harmless, inert)
        # while still gating the actual process/thread on spotify.enable - and lets the
        # web UI toggle Spotify support on/off at runtime without restarting the
        # Jukebox Core, by calling enable()/disable() again later.
        #
        # Named enable()/disable() (rather than start()/stop()) to avoid colliding with
        # the playback-transport stop() method below, which stops Spotify *playback*,
        # not the go-librespot process itself.
        self.status_thread = multitimer.GenericEndlessTimerClass(
            'spotify.timer_status', self.status_poll_interval, self._status_poll)

    # -----------------------------------------------------------------
    # Process management
    # -----------------------------------------------------------------
    @plugs.tag
    def enable(self) -> None:
        """Spawn go-librespot and start polling its status. Safe to call repeatedly."""
        self._enabled = True
        self._start_librespot()
        self.status_thread.start(restart=False)

    @plugs.tag
    def disable(self) -> None:
        """Stop go-librespot and pause status polling, without tearing down this backend.

        Unlike exit(), the backend stays registered with the player coordinator and can
        be enabled again later with enable() (e.g. from the enable toggle in the web
        UI), so it deliberately does not close() the underlying timer thread.
        """
        self._enabled = False
        self.status_thread.cancel()
        self._stop_librespot()
        self._last_status = None

    def _start_librespot(self) -> None:
        with self._process_lock:
            if self.is_running():
                return
            if not os.path.isfile(self.binary_path) or not os.access(self.binary_path, os.X_OK):
                self._last_error = (
                    f"go-librespot binary not found (or not executable) at '{self.binary_path}'. "
                    "Run the Spotify install routine or set 'spotify.binary_path' in jukebox.yaml.")
                logger.error(self._last_error)
                return

            _write_go_librespot_config(self.config_dir, {
                'device_name': self.device_name,
                'audio_backend': self.audio_backend,
                'audio_device': self.audio_device,
                'credentials_type': self.credentials_type,
                'persist_credentials': self.persist_credentials,
                'api_host': self.api_host,
                'api_port': self.api_port,
            })

            try:
                self._process = subprocess.Popen(
                    [self.binary_path, '-config_dir', self.config_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                logger.info(f"Started go-librespot (pid={self._process.pid}) as '{self.device_name}'")
                self._last_error = None
            except OSError as e:
                self._last_error = f"Failed to start go-librespot: {e}"
                logger.error(self._last_error)
                self._process = None

    def _stop_librespot(self, timeout: float = 5.0) -> None:
        with self._process_lock:
            if self._process is None:
                return
            if self._process.poll() is None:
                try:
                    self._process.send_signal(signal.SIGTERM)
                    self._process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    logger.warning("go-librespot did not terminate in time, killing it")
                    self._process.kill()
                    self._process.wait(timeout=timeout)
            self._process = None

    def is_running(self) -> bool:
        with self._process_lock:
            return self._process is not None and self._process.poll() is None

    # -----------------------------------------------------------------
    # Status polling / publishing
    # -----------------------------------------------------------------
    def _status_poll(self):
        try:
            status = self.client.status()
            self._last_status = status
            self._last_error = None
        except GoLibrespotError as e:
            # Expected whenever go-librespot is not (yet) running or has no session -
            # do not spam the log on every poll tick.
            self._last_error = str(e)
            status = None

        if self._active:
            payload = self._status_to_playerstatus(status)
            publishing.get_publisher().send('playerstatus', payload)

    def _status_to_playerstatus(self, status: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            'provider': 'spotify',
            'state': _map_state(status),
        }
        if status is None:
            return payload

        payload['random'] = '1' if status.get('shuffle_context') else '0'
        payload['repeat'] = '1' if (status.get('repeat_context') or status.get('repeat_track')) else '0'
        payload['single'] = '1' if status.get('repeat_track') else '0'

        track = status.get('track')
        if track:
            payload['title'] = track.get('name')
            payload['artist'] = ', '.join(track.get('artist_names') or [])
            payload['album'] = track.get('album_name')
            payload['file'] = track.get('uri')
            if track.get('position') is not None:
                payload['elapsed'] = track['position'] / 1000.0
            if track.get('duration') is not None:
                payload['duration'] = track['duration'] / 1000.0
        return payload

    # -----------------------------------------------------------------
    # Backend interface used by components.player.coordinator.PlayerCoordinator
    # -----------------------------------------------------------------
    def set_active(self, active: bool):
        self._active = active
        if active:
            publishing.get_publisher().send('playerstatus', self._status_to_playerstatus(self._last_status))

    @plugs.tag
    def get_player_type_and_version(self):
        return 'go-librespot (Spotify Connect)'

    @plugs.tag
    def play(self):
        self.client.play()

    @plugs.tag
    def stop(self):
        self.client.stop()

    @plugs.tag
    def pause(self, state: int = 1):
        if state:
            self.client.pause()
        else:
            self.client.play()

    @plugs.tag
    def prev(self):
        self.client.prev()

    @plugs.tag
    def next(self):
        self.client.next()

    @plugs.tag
    def seek(self, new_time):
        # new_time follows MPD's convention of seconds; go-librespot wants milliseconds
        self.client.seek(int(float(new_time) * 1000))

    @plugs.tag
    def rewind(self):
        """Restart the current track from the beginning"""
        self.client.seek(0)

    @plugs.tag
    def replay(self):
        self.client.seek(0)
        self.client.play()

    @plugs.tag
    def toggle(self):
        self.client.playpause()

    @plugs.tag
    def replay_if_stopped(self):
        status = self._last_status
        if _map_state(status) == 'stop':
            self.client.play()

    @plugs.tag
    def shuffle(self, option='toggle'):
        if option == 'enable':
            self.client.shuffle_context(True)
        elif option == 'disable':
            self.client.shuffle_context(False)
        elif option == 'toggle':
            currently_on = bool((self._last_status or {}).get('shuffle_context'))
            self.client.shuffle_context(not currently_on)
        else:
            logger.error(f"'{option}' does not exist for 'shuffle'")

    @plugs.tag
    def repeat(self, option='toggle'):
        status = self._last_status or {}
        if option == 'enable_repeat':
            self.client.repeat_context(True)
            self.client.repeat_track(False)
        elif option == 'enable_repeat_single':
            self.client.repeat_track(True)
        elif option == 'disable':
            self.client.repeat_context(False)
            self.client.repeat_track(False)
        elif option in ('toggle', 'toggle_repeat', 'toggle_repeat_single'):
            if option == 'toggle_repeat_single':
                self.client.repeat_track(not status.get('repeat_track', False))
            else:
                self.client.repeat_context(not status.get('repeat_context', False))
        else:
            logger.error(f"'{option}' does not exist for 'repeat'")

    @plugs.tag
    def get_current_song(self, param=None):
        return self._last_status or {}

    @plugs.tag
    def playerstatus(self):
        return self._status_to_playerstatus(self._last_status)

    @plugs.tag
    def play_single(self, song_url):
        """Play a single Spotify URI (e.g. 'spotify:track:...')

        Unlike MPD's play_single, this does not manage a local playlist - go-librespot /
        the Spotify Connect session owns the play queue.
        """
        self.client.play_uri(song_url)

    @plugs.tag
    def resume(self):
        self.client.play()

    def get_volume(self):
        try:
            return int(self.client.get_volume().get('value', 0))
        except GoLibrespotError as e:
            logger.warning(f"Could not read Spotify volume: {e}")
            return 0

    def set_volume(self, volume):
        self.client.set_volume(int(volume))
        return self.get_volume()

    # -----------------------------------------------------------------
    # Not (yet) implemented: these require the Spotify Web API (OAuth) to browse the
    # user's library/catalog, which is explicitly out of scope for this first pass.
    # -----------------------------------------------------------------
    @plugs.tag
    def update(self):
        raise NotImplementedError("Spotify backend has no local library to update")

    @plugs.tag
    def update_wait(self):
        raise NotImplementedError("Spotify backend has no local library to update")

    @plugs.tag
    def map_filename_to_playlist_pos(self, filename):
        raise NotImplementedError

    @plugs.tag
    def remove(self):
        raise NotImplementedError

    @plugs.tag
    def move(self):
        raise NotImplementedError

    @plugs.tag
    def get_single_coverart(self, song_url):
        raise NotImplementedError("Spotify cover art requires the Spotify Web API (not yet implemented)")

    @plugs.tag
    def get_album_coverart(self, albumartist: str, album: str):
        raise NotImplementedError("Spotify cover art requires the Spotify Web API (not yet implemented)")

    @plugs.tag
    def flush_coverart_cache(self):
        return None

    @plugs.tag
    def get_folder_content(self, folder: str):
        raise NotImplementedError("Spotify has no folder-based library")

    @plugs.tag
    def play_folder(self, folder: str, recursive: bool = False) -> None:
        raise NotImplementedError(
            "Spotify Connect cannot start playback from an RFID-mapped folder yet; "
            "use play_single() with a Spotify URI, or control playback from the Spotify app")

    @plugs.tag
    def play_album(self, albumartist: str, album: str):
        raise NotImplementedError("Spotify has no local album database")

    @plugs.tag
    def queue_load(self, folder):
        raise NotImplementedError

    @plugs.tag
    def playlistinfo(self):
        raise NotImplementedError("Spotify Connect's queue is not exposed by go-librespot's API")

    @plugs.tag
    def list_all_dirs(self):
        raise NotImplementedError

    @plugs.tag
    def list_albums(self):
        # Returning an empty list (rather than raising) lets PlayerCoordinator's
        # multi-backend aggregation in list_albums()/list_library_items() skip Spotify
        # silently when it is not the explicitly-requested provider.
        return []

    def list_library_items(self, content_types=None):
        return []

    @plugs.tag
    def list_songs_by_artist_and_album(self, albumartist, album):
        raise NotImplementedError

    @plugs.tag
    def get_song_by_url(self, song_url):
        raise NotImplementedError

    def is_second_swipe(self, folder: str) -> bool:
        return False

    def play_second_swipe(self):
        raise NotImplementedError

    # -----------------------------------------------------------------
    # Spotify-specific status / connection info, also exposed directly under the
    # 'spotify' RPC package (see components/spotify/__init__.py)
    # -----------------------------------------------------------------
    @plugs.tag
    def get_connection_status(self) -> Dict[str, Any]:
        """Report whether go-librespot is running and whether a Spotify session is active

        This is best-effort: it cannot distinguish "no one has connected yet" from
        "credentials rejected" beyond what go-librespot's own logs would show, since
        those are not currently piped back into the Jukebox log.
        """
        status = self._last_status
        return {
            'enabled': self._enabled,
            'process_running': self.is_running(),
            'session_active': status is not None,
            'device_name': self.device_name,
            'username': (status or {}).get('username'),
            'credentials_type': self.credentials_type,
            'last_error': self._last_error,
        }

    @plugs.tag
    def restart(self):
        """Restart the go-librespot process (e.g. after changing device_name)"""
        self._stop_librespot()
        self._start_librespot()

    @plugs.tag
    def exit(self):
        logger.debug("Exit routine of Spotify player backend started")
        self.status_thread.close()
        self._stop_librespot()
        return self.status_thread.timer_thread
