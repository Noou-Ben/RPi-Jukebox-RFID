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
  refreshLibrary,
  renameLibraryEntry,
} from '../../../../utils/library-api';
import RenameEntryDialog from './rename-entry-dialog';

vi.mock('../../../../utils/library-api', () => ({
  refreshLibrary: vi.fn(),
  renameLibraryEntry: vi.fn(),
  translateLibraryError: (t, error) => error.message,
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => {
      const labels = {
        'general.buttons.cancel': 'Cancel',
        'library.folders.manager.rename.confirm': 'Rename',
        'library.folders.manager.rename.name': 'Name',
        'library.folders.manager.rename.title': 'Rename',
      };
      return labels[key] || key;
    },
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test('prefills the current name and renames the entry', async () => {
  renameLibraryEntry.mockResolvedValue({ path: 'New Name' });
  refreshLibrary.mockResolvedValue({ update_id: '1' });
  const onRenamed = vi.fn();
  const user = userEvent.setup();

  render(
    <RenameEntryDialog
      entry={{ name: 'Old Name', relpath: 'Old Name', type: 'directory' }}
      onClose={vi.fn()}
      onRenamed={onRenamed}
      open
    />,
  );

  const input = screen.getByRole('textbox', { name: /Name/ });
  expect(input).toHaveValue('Old Name');

  await user.clear(input);
  await user.type(input, 'New Name');
  await act(async () => {
    await user.click(screen.getByRole('button', { name: 'Rename' }));
    await Promise.resolve();
    await Promise.resolve();
  });

  await waitFor(() => {
    expect(renameLibraryEntry).toHaveBeenCalledWith('Old Name', 'New Name');
    expect(refreshLibrary).toHaveBeenCalled();
    expect(onRenamed).toHaveBeenCalledWith('');
  });
});

test('shows a translated error and keeps the dialog open on failure', async () => {
  renameLibraryEntry.mockRejectedValue({ code: 'duplicate_name', message: 'Already exists.' });
  const onRenamed = vi.fn();
  const user = userEvent.setup();

  render(
    <RenameEntryDialog
      entry={{ name: 'track.mp3', relpath: 'track.mp3', type: 'file' }}
      onClose={vi.fn()}
      onRenamed={onRenamed}
      open
    />,
  );

  await act(async () => {
    await user.click(screen.getByRole('button', { name: 'Rename' }));
    await Promise.resolve();
    await Promise.resolve();
  });

  expect(await screen.findByText('Already exists.')).toBeVisible();
  expect(onRenamed).not.toHaveBeenCalled();
});
