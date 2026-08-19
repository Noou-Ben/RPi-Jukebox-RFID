from unittest.mock import Mock

import pytest

import jukebox.publishing as publishing

from components.player.backends.spotify import PlayerSpotify, _map_state


def spotify_backend():
    return PlayerSpotify.__new__(PlayerSpotify)


def test_map_state_defaults_to_stop_without_session():
    assert _map_state(None) == 'stop'


def test_map_state_reflects_stopped_flag():
    assert _map_state({'stopped': True, 'paused': False}) == 'stop'


def test_map_state_reflects_paused_flag():
    assert _map_state({'stopped': False, 'paused': True}) == 'pause'


def test_map_state_defaults_to_play_when_active():
    assert _map_state({'stopped': False, 'paused': False}) == 'play'


def test_status_to_playerstatus_without_session_only_reports_provider_and_state():
    backend = spotify_backend()

    assert backend._status_to_playerstatus(None) == {'provider': 'spotify', 'state': 'stop'}


def test_status_to_playerstatus_maps_track_metadata():
    backend = spotify_backend()
    status = {
        'stopped': False,
        'paused': False,
        'shuffle_context': True,
        'repeat_context': False,
        'repeat_track': True,
        'track': {
            'uri': 'spotify:track:abc123',
            'name': 'Track Title',
            'artist_names': ['Artist One', 'Artist Two'],
            'album_name': 'Album Title',
            'position': 1500,
            'duration': 200000,
        },
    }

    assert backend._status_to_playerstatus(status) == {
        'provider': 'spotify',
        'state': 'play',
        'random': '1',
        'repeat': '1',
        'single': '1',
        'title': 'Track Title',
        'artist': 'Artist One, Artist Two',
        'album': 'Album Title',
        'file': 'spotify:track:abc123',
        'elapsed': 1.5,
        'duration': 200.0,
    }


def test_inactive_backend_does_not_publish_status(monkeypatch):
    publisher = Mock()
    monkeypatch.setattr(publishing, 'get_publisher', Mock(return_value=publisher))
    backend = spotify_backend()
    backend._active = False
    backend._last_status = None

    backend.set_active(False)
    publisher.send.assert_not_called()

    backend.set_active(True)
    publisher.send.assert_called_once_with('playerstatus', {'provider': 'spotify', 'state': 'stop'})


def test_pause_toggles_via_state_argument():
    backend = spotify_backend()
    backend.client = Mock()

    backend.pause(1)
    backend.client.pause.assert_called_once()

    backend.pause(0)
    backend.client.play.assert_called_once()


def test_seek_converts_seconds_to_milliseconds():
    backend = spotify_backend()
    backend.client = Mock()

    backend.seek(2.5)

    backend.client.seek.assert_called_once_with(2500)


@pytest.mark.parametrize('method_name,args', [
    ('play_folder', ('SomeFolder',)),
    ('play_album', ('Artist', 'Album')),
    ('get_folder_content', ('SomeFolder',)),
    ('list_songs_by_artist_and_album', ('Artist', 'Album')),
    ('get_song_by_url', ('spotify:track:abc',)),
    ('get_single_coverart', ('spotify:track:abc',)),
])
def test_library_browsing_methods_are_not_implemented(method_name, args):
    """Spotify catalog/library browsing needs the Spotify Web API (OAuth), which is
    explicitly out of scope for this first pass - see documentation/developers/status.md"""
    backend = spotify_backend()

    with pytest.raises(NotImplementedError):
        getattr(backend, method_name)(*args)


def test_list_albums_and_list_library_items_return_empty_instead_of_raising():
    # Unlike the single-item browsing methods above, these are called by
    # PlayerCoordinator's multi-backend aggregation and must not blow up when Spotify
    # is registered but not the explicitly-requested provider.
    backend = spotify_backend()

    assert backend.list_albums() == []
    assert backend.list_library_items() == []


def test_enable_spawns_process_and_resumes_polling():
    backend = spotify_backend()
    backend._start_librespot = Mock()
    backend.status_thread = Mock()

    backend.enable()

    assert backend._enabled is True
    backend._start_librespot.assert_called_once()
    backend.status_thread.start.assert_called_once_with(restart=False)


def test_disable_stops_process_and_pauses_polling_without_closing_the_timer():
    backend = spotify_backend()
    backend._stop_librespot = Mock()
    backend.status_thread = Mock()
    backend._last_status = {'username': 'someone'}

    backend.disable()

    assert backend._enabled is False
    assert backend._last_status is None
    backend._stop_librespot.assert_called_once()
    backend.status_thread.cancel.assert_called_once()
    backend.status_thread.close.assert_not_called()


def test_get_connection_status_reports_process_and_session_state():
    backend = spotify_backend()
    backend.is_running = Mock(return_value=True)
    backend._enabled = True
    backend._last_status = {'username': 'someone'}
    backend._last_error = None
    backend.device_name = 'Phoniebox'
    backend.credentials_type = 'zeroconf'

    status = backend.get_connection_status()

    assert status == {
        'enabled': True,
        'process_running': True,
        'session_active': True,
        'device_name': 'Phoniebox',
        'username': 'someone',
        'credentials_type': 'zeroconf',
        'last_error': None,
    }
