# -*- coding: utf-8 -*-
"""
Optional Spotify Connect component

Registers a `go-librespot`-backed playback backend (see
:mod:`components.player.backends.spotify`) with the shared player coordinator, and
exposes Spotify-specific RPCs (enable/disable, auth/connection status) directly under
the `spotify` package.

The backend is *registered* unconditionally so it can be enabled at runtime from the
web UI without a restart, but it is only *started* (spawning the go-librespot process
and status polling) if `spotify.enable` is `true` in `jukebox.yaml`, or after an
explicit `spotify.ctrl.enable()` RPC call. A freshly-registered-but-not-started backend
spawns no process and opens no sockets, so this does not affect MPD-only installs.
Following the same pattern as `components.mqtt`, the module is always loaded (see
`resources/default-settings/jukebox.default.yaml`).

Must be loaded *after* the `player` module (see `modules.named` ordering in
`jukebox.yaml`), since it reaches into the already-registered player coordinator to
add itself as a backend.
"""
import logging

import jukebox.cfghandler
import jukebox.plugs as plugs

from components.player.backends.spotify import PlayerSpotify

logger = logging.getLogger('jb.spotify')
cfg = jukebox.cfghandler.get_handler('jukebox')

spotify_backend: PlayerSpotify = None


@plugs.initialize
def initialize():
    global spotify_backend

    spotify_backend = PlayerSpotify()

    # Wire the new backend into the shared player coordinator so playback control
    # (play/pause/next/prev/volume/...) works through the same generic 'player.ctrl'
    # RPC surface as MPD, once selected with player.ctrl.select_backend('spotify').
    # This registration is cheap/inert: PlayerSpotify does not spawn go-librespot or
    # start polling until enable() is called (see below).
    player_ctrl = plugs.get('player', 'ctrl')
    player_ctrl.register_backend('spotify', spotify_backend)

    # Also register the same instance under its own 'spotify' package so
    # Spotify-specific RPCs (enable/disable, auth/connection status) have a stable
    # home that does not depend on Spotify being the currently active player backend.
    plugs.register(spotify_backend, name='ctrl', package=plugs.loaded_as(__name__))

    if cfg.setndefault('spotify', 'enable', value=False):
        logger.info("Starting Spotify Connect backend (go-librespot) - spotify.enable = true")
        spotify_backend.enable()
    else:
        logger.info("Spotify support is registered but not started (spotify.enable = false)")


@plugs.register
def enable():
    """Enable Spotify support: persist the setting and start go-librespot now

    Unlike most other Jukebox settings, this genuinely takes effect immediately (no
    Jukebox Core restart required): the underlying player backend was already
    registered at startup, inert, and this simply starts it.
    """
    cfg.setn('spotify', 'enable', value=True)
    cfg.save(only_if_changed=True)
    spotify_backend.enable()
    return spotify_backend.get_connection_status()


@plugs.register
def disable():
    """Disable Spotify support: persist the setting and stop go-librespot now"""
    cfg.setn('spotify', 'enable', value=False)
    cfg.save(only_if_changed=True)
    spotify_backend.disable()
    return spotify_backend.get_connection_status()


@plugs.atexit
def atexit(**ignored_kwargs):
    # The player coordinator's own atexit handler (components.player.plugin.atexit)
    # already calls exit() on every registered backend, including this one - nothing
    # further to do here.
    return None
