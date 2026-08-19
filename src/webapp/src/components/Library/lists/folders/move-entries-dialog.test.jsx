import {
  act,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  beforeEach,
  expect,
  test,
  vi,
} from 'vitest';

import {
  listLibraryEntries,
  moveLibraryEntries,
  refreshLibrary,
} from '../../../../utils/library-api';
import MoveEntriesDialog from './move-entries-dialog';

vi.mock('../../../../utils/library-api', () => ({
  listLibraryEntries: vi.fn(),
  moveLibraryEntries: vi.fn(),
  refreshLibrary: vi.fn(),
  translateLibraryError: (t, error) => error.message,
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, options = {}) => {
      const labels = {
        'general.buttons.cancel': 'Cancel',
        'library.folders.manager.move.confirm': 'Move here',
        'library.folders.manager.move.current-folder': `Current folder: ${options.folder}`,
        'library.folders.manager.move.no-subfolders': 'No subfolders',
        'library.folders.manager.move.title': `Move ${options.count} items`,
      };
      return labels[key] || key;
    },
  }),
}));

const entries = [
  { name: 'track.mp3', relpath: 'track.mp3', type: 'file' },
];

beforeEach(() => {
  vi.clearAllMocks();
});

test('browses into a subfolder and moves the selection there', async () => {
  listLibraryEntries.mockImplementation((folder) => {
    if (folder === '.') {
      return Promise.resolve([
        { name: 'Album', relpath: 'Album', type: 'directory' },
        { name: 'track.mp3', relpath: 'track.mp3', type: 'file' },
      ]);
    }
    return Promise.resolve([]);
  });
  moveLibraryEntries.mockResolvedValue({ moved: ['Album/track.mp3'] });
  refreshLibrary.mockResolvedValue({ update_id: '1' });
  const onMoved = vi.fn();
  const user = userEvent.setup();

  render(
    <MoveEntriesDialog
      entries={entries}
      initialFolder="."
      onClose={vi.fn()}
      onMoved={onMoved}
      open
    />,
  );

  expect(await screen.findByText('Current folder: .')).toBeVisible();
  await user.click(await screen.findByRole('button', { name: 'Album' }));
  expect(await screen.findByText('Current folder: Album')).toBeVisible();

  await act(async () => {
    await user.click(screen.getByRole('button', { name: 'Move here' }));
    await Promise.resolve();
    await Promise.resolve();
  });

  await waitFor(() => {
    expect(moveLibraryEntries).toHaveBeenCalledWith(['track.mp3'], 'Album');
    expect(refreshLibrary).toHaveBeenCalled();
    expect(onMoved).toHaveBeenCalledWith('');
  });
});

test('disables moving into the folder currently being browsed', async () => {
  listLibraryEntries.mockResolvedValue([]);

  render(
    <MoveEntriesDialog
      entries={entries}
      initialFolder="."
      onClose={vi.fn()}
      onMoved={vi.fn()}
      open
    />,
  );

  expect(await screen.findByText('Current folder: .')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Move here' })).toBeDisabled();
});
