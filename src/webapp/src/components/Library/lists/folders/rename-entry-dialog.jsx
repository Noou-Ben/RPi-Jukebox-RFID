import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from '@mui/material';

import {
  refreshLibrary,
  renameLibraryEntry,
  translateLibraryError,
} from '../../../../utils/library-api';

const RenameEntryDialog = ({
  entry,
  onClose,
  onRenamed,
  open,
}) => {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) setName(entry?.name || '');
  }, [open, entry]);

  const close = () => {
    if (isSaving) return;
    setError('');
    onClose();
  };

  const renameEntry = async (event) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName || !entry) return;

    setError('');
    setIsSaving(true);
    try {
      await renameLibraryEntry(entry.relpath, trimmedName);
    }
    catch (requestError) {
      setError(translateLibraryError(t, requestError));
      setIsSaving(false);
      return;
    }

    let refreshWarning = '';
    try {
      await refreshLibrary();
    }
    catch (requestError) {
      refreshWarning = translateLibraryError(t, requestError);
    }
    setIsSaving(false);
    onRenamed(refreshWarning);
  };

  return (
    <Dialog fullWidth maxWidth="xs" onClose={close} open={open}>
      <form onSubmit={renameEntry}>
        <DialogTitle>{t('library.folders.manager.rename.title')}</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ marginBottom: 2 }}>{error}</Alert>}
          <TextField
            autoFocus
            disabled={isSaving}
            fullWidth
            label={t('library.folders.manager.rename.name')}
            margin="dense"
            onChange={(event) => setName(event.target.value)}
            required
            slotProps={{
              htmlInput: { maxLength: 255 },
            }}
            value={name}
          />
        </DialogContent>
        <DialogActions>
          <Button disabled={isSaving} onClick={close} sx={{ minHeight: 44 }}>
            {t('general.buttons.cancel')}
          </Button>
          <Button
            disabled={isSaving || !name.trim()}
            sx={{ minHeight: 44 }}
            type="submit"
            variant="contained"
          >
            {t('library.folders.manager.rename.confirm')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default RenameEntryDialog;
