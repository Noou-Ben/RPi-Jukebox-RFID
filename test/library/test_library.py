import os

import pytest

from jukebox.library import LibraryError, MusicLibrary


@pytest.fixture
def music_library(tmp_path):
    root = tmp_path / 'music'
    root.mkdir()
    updates = []
    library = MusicLibrary(lambda: str(root), lambda: updates.append('update') or 'job-1')
    return library, root, updates


def test_upload_is_published_atomically_and_rejects_duplicates(music_library):
    library, root, _ = music_library
    album = root / 'Album'
    album.mkdir()

    upload = library.start_upload('Album', 'song.mp3')
    assert (album / 'song.mp3').read_bytes() == b''
    upload.write(b'audio data')
    upload.finish()

    assert (album / 'song.mp3').read_bytes() == b'audio data'
    assert not list(album.glob('.phoniebox-upload-*'))

    with pytest.raises(LibraryError) as error:
        library.start_upload('Album', 'song.mp3')
    assert error.value.status == 409
    assert error.value.code == 'duplicate_name'
    assert (album / 'song.mp3').read_bytes() == b'audio data'


def test_cancelled_upload_removes_temporary_and_reserved_files(music_library):
    library, root, _ = music_library

    upload = library.start_upload('.', 'cancelled.flac')
    upload.write(b'partial')
    upload.abort()

    assert not (root / 'cancelled.flac').exists()
    assert not list(root.glob('.phoniebox-upload-*'))


@pytest.mark.parametrize('name', [
    'track.MP3',
    'playlist.m3u8',
    'station.livestream.txt',
    'show.podcast.txt',
    'cover.webp',
])
def test_supported_library_file_types_are_accepted(music_library, name):
    library, root, _ = music_library

    upload = library.start_upload('.', name)
    upload.abort()

    assert not (root / name).exists()


@pytest.mark.parametrize('name', ['notes.txt', 'archive.zip', '.hidden.mp3', '../track.mp3'])
def test_unsupported_or_invalid_file_names_are_rejected(music_library, name):
    library, _, _ = music_library

    with pytest.raises(LibraryError) as error:
        library.start_upload('.', name)

    assert error.value.status in (400, 415)


def test_create_folder_and_delete_non_empty_folder(music_library):
    library, root, _ = music_library

    path = library.create_folder('.', 'New Album')
    (root / path / 'track.mp3').write_bytes(b'audio')
    nested = root / path / 'Disc 2'
    nested.mkdir()
    (nested / 'track.mp3').write_bytes(b'audio')

    assert path == 'New Album'
    assert library.delete_entries([path]) == [path]
    assert not (root / path).exists()


def test_list_entries_includes_manageable_files_and_skips_external_symlinks(music_library, tmp_path):
    library, root, _ = music_library
    (root / 'Album').mkdir()
    (root / 'track.mp3').touch()
    (root / 'cover.jpg').touch()
    (root / 'station.livestream.txt').touch()
    (root / 'notes.pdf').touch()
    (root / '.phoniebox-upload-part').touch()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'external').symlink_to(outside, target_is_directory=True)

    assert library.list_entries('.') == [
        {'name': 'Album', 'relpath': 'Album', 'type': 'directory'},
        {'name': 'cover.jpg', 'relpath': 'cover.jpg', 'type': 'image'},
        {'name': 'notes.pdf', 'relpath': 'notes.pdf', 'type': 'other'},
        {
            'name': 'station.livestream.txt',
            'relpath': 'station.livestream.txt',
            'type': 'stream',
        },
        {'name': 'track.mp3', 'relpath': 'track.mp3', 'type': 'file'},
    ]


def test_delete_validates_all_paths_before_removing_anything(music_library):
    library, root, _ = music_library
    existing = root / 'keep.mp3'
    existing.write_bytes(b'audio')

    with pytest.raises(LibraryError) as error:
        library.delete_entries(['keep.mp3', '../outside.mp3'])

    assert error.value.code == 'invalid_path'
    assert existing.exists()


def test_root_and_symlink_escape_are_rejected(music_library, tmp_path):
    library, root, _ = music_library
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'track.mp3').write_bytes(b'outside')
    (root / 'outside').symlink_to(outside, target_is_directory=True)

    with pytest.raises(LibraryError) as root_error:
        library.delete_entries(['.'])
    assert root_error.value.code == 'invalid_path'

    with pytest.raises(LibraryError) as upload_error:
        library.start_upload('outside', 'new.mp3')
    assert upload_error.value.code == 'invalid_path'

    with pytest.raises(LibraryError) as delete_error:
        library.delete_entries(['outside'])
    assert delete_error.value.code == 'invalid_path'
    assert (outside / 'track.mp3').exists()


def test_upload_does_not_replace_file_created_during_transfer(music_library):
    library, root, _ = music_library
    upload = library.start_upload('.', 'race.mp3')
    upload.write(b'upload')

    reserved = root / 'race.mp3'
    reserved.unlink()
    reserved.write_bytes(b'other writer')

    with pytest.raises(LibraryError) as error:
        upload.finish()

    assert error.value.code == 'duplicate_name'
    assert reserved.read_bytes() == b'other writer'
    assert not list(root.glob('.phoniebox-upload-*'))


def test_update_returns_mpd_job_identifier(music_library):
    library, _, updates = music_library

    assert library.update() == 'job-1'
    assert updates == ['update']


def test_uploaded_file_mode_is_shared_writable(music_library):
    library, root, _ = music_library
    upload = library.start_upload('.', 'track.wav')
    upload.write(b'audio')
    upload.finish()

    assert os.stat(root / 'track.wav').st_mode & 0o777 == 0o666


def test_rename_entry_renames_file_and_folder(music_library):
    library, root, _ = music_library
    (root / 'track.mp3').write_bytes(b'audio')
    (root / 'Album').mkdir()

    assert library.rename_entry('track.mp3', 'renamed.mp3') == 'renamed.mp3'
    assert (root / 'renamed.mp3').read_bytes() == b'audio'
    assert not (root / 'track.mp3').exists()

    assert library.rename_entry('Album', 'Renamed Album') == 'Renamed Album'
    assert (root / 'Renamed Album').is_dir()
    assert not (root / 'Album').exists()


def test_rename_entry_to_same_name_is_a_noop(music_library):
    library, root, _ = music_library
    (root / 'track.mp3').write_bytes(b'audio')

    assert library.rename_entry('track.mp3', 'track.mp3') == 'track.mp3'
    assert (root / 'track.mp3').read_bytes() == b'audio'


def test_rename_entry_rejects_collisions_and_missing_entries(music_library):
    library, root, _ = music_library
    (root / 'track.mp3').write_bytes(b'audio')
    (root / 'other.mp3').write_bytes(b'audio')

    with pytest.raises(LibraryError) as error:
        library.rename_entry('track.mp3', 'other.mp3')
    assert error.value.code == 'duplicate_name'

    with pytest.raises(LibraryError) as error:
        library.rename_entry('missing.mp3', 'new.mp3')
    assert error.value.code == 'entry_not_found'


def test_rename_entry_rejects_invalid_and_unsupported_names(music_library):
    library, root, _ = music_library
    (root / 'track.mp3').write_bytes(b'audio')
    (root / 'Album').mkdir()

    with pytest.raises(LibraryError) as error:
        library.rename_entry('track.mp3', 'archive.zip')
    assert error.value.code == 'unsupported_file_type'

    with pytest.raises(LibraryError) as error:
        library.rename_entry('Album', '../Escaped')
    assert error.value.code == 'invalid_folder_name'


def test_move_entries_moves_files_and_folders(music_library):
    library, root, _ = music_library
    (root / 'track.mp3').write_bytes(b'audio')
    (root / 'Destination').mkdir()

    assert library.move_entries(['track.mp3'], 'Destination') == ['Destination/track.mp3']
    assert (root / 'Destination' / 'track.mp3').read_bytes() == b'audio'
    assert not (root / 'track.mp3').exists()


def test_move_entries_rejects_folder_into_itself_or_descendant(music_library):
    library, root, _ = music_library
    album = root / 'Album'
    album.mkdir()
    nested = album / 'Nested'
    nested.mkdir()

    with pytest.raises(LibraryError) as error:
        library.move_entries(['Album'], 'Album')
    assert error.value.code == 'invalid_destination'

    with pytest.raises(LibraryError) as error:
        library.move_entries(['Album'], 'Album/Nested')
    assert error.value.code == 'invalid_destination'


def test_move_entries_rejects_destination_collisions(music_library):
    library, root, _ = music_library
    (root / 'track.mp3').write_bytes(b'audio')
    destination = root / 'Destination'
    destination.mkdir()
    (destination / 'track.mp3').write_bytes(b'existing')

    with pytest.raises(LibraryError) as error:
        library.move_entries(['track.mp3'], 'Destination')
    assert error.value.code == 'duplicate_name'
    assert (destination / 'track.mp3').read_bytes() == b'existing'
    assert (root / 'track.mp3').exists()


def test_move_entries_skips_nested_selections_covered_by_their_parent(music_library):
    library, root, _ = music_library
    album = root / 'Album'
    album.mkdir()
    (album / 'track.mp3').write_bytes(b'audio')
    destination = root / 'Destination'
    destination.mkdir()

    moved = library.move_entries(['Album', 'Album/track.mp3'], 'Destination')

    assert moved == ['Destination/Album']
    assert (destination / 'Album' / 'track.mp3').read_bytes() == b'audio'
    assert not album.exists()
