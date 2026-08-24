import { useEffect, useMemo, useState } from 'react';
import { dropLast } from 'ramda';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';

import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import FolderIcon from '@mui/icons-material/Folder';

import {
  listLibraryEntries,
  moveLibraryEntries,
  refreshLibrary,
  translateLibraryError,
} from '../../../../utils/library-api';

import { ROOT_DIR } from '../../../../config';

const getParentFolder = (folder) => {
  if (folder === ROOT_DIR) return undefined;

  const parentFolder = dropLast(1, folder.split('/')).join('/') || ROOT_DIR;
  return parentFolder;
};

const MoveEntriesDialog = ({
  entries,
  initialFolder,
  onClose,
  onMoved,
  open,
}) => {
  const { t } = useTranslation();
  const [browseFolder, setBrowseFolder] = useState(ROOT_DIR);
  const [subfolders, setSubfolders] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [error, setError] = useState('');
  const [isMoving, setIsMoving] = useState(false);

  const selectedPaths = useMemo(
    () => new Set(entries.map(({ relpath }) => relpath)),
    [entries],
  );
  const selectedFolderPaths = useMemo(
    () => entries.filter(({ type }) => type === 'directory').map(({ relpath }) => relpath),
    [entries],
  );

  useEffect(() => {
    if (open) setBrowseFolder(initialFolder || ROOT_DIR);
  }, [open, initialFolder]);

  useEffect(() => {
    if (!open) return undefined;
    let isCurrent = true;
    setIsLoading(true);
    setLoadError(null);
    listLibraryEntries(browseFolder)
      .then((result) => {
        if (isCurrent) setSubfolders(result.filter(({ type }) => type === 'directory'));
      })
      .catch((requestError) => {
        if (isCurrent) setLoadError(requestError);
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => {
      isCurrent = false;
    };
  }, [browseFolder, open]);

  const close = () => {
    if (isMoving) return;
    setError('');
    onClose();
  };

  const parentFolder = getParentFolder(browseFolder);
  const visibleFolders = subfolders.filter(({ relpath }) => !selectedPaths.has(relpath));
  const isOwnDestination = selectedFolderPaths.some((relpath) => (
    browseFolder === relpath || browseFolder.startsWith(`${relpath}/`)
  ));
  const isMoveDisabled = isMoving || isLoading || isOwnDestination || browseFolder === initialFolder;

  const moveEntries = async () => {
    setError('');
    setIsMoving(true);
    try {
      await moveLibraryEntries(entries.map(({ relpath }) => relpath), browseFolder);
    }
    catch (requestError) {
      setError(translateLibraryError(t, requestError));
      setIsMoving(false);
      return;
    }

    let refreshWarning = '';
    try {
      await refreshLibrary();
    }
    catch (requestError) {
      refreshWarning = translateLibraryError(t, requestError);
    }
    setIsMoving(false);
    onMoved(refreshWarning);
  };

  return (
    <Dialog fullWidth maxWidth="sm" onClose={close} open={open}>
      <DialogTitle>
        {t('library.folders.manager.move.title', { count: entries.length })}
      </DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ marginBottom: 2 }}>{error}</Alert>}
        <DialogContentText sx={{ marginBottom: 1 }}>
          {t('library.folders.manager.move.current-folder', { folder: browseFolder })}
        </DialogContentText>
        {loadError &&
          <Alert severity="error" sx={{ marginBottom: 2 }}>
            {translateLibraryError(t, loadError)}
          </Alert>
        }
        {isLoading && <CircularProgress />}
        {!isLoading && !loadError &&
          <List dense sx={{ maxHeight: 280, overflowY: 'auto' }}>
            {parentFolder &&
              <ListItem disablePadding>
                <ListItemButton
                  disabled={isMoving}
                  onClick={() => setBrowseFolder(parentFolder)}
                  sx={{ minHeight: 44 }}
                >
                  <ListItemIcon><ArrowBackIcon /></ListItemIcon>
                  <ListItemText primary=".." />
                </ListItemButton>
              </ListItem>
            }
            {visibleFolders.length === 0 && !parentFolder &&
              <ListItem>
                <ListItemText primary={t('library.folders.manager.move.no-subfolders')} />
              </ListItem>
            }
            {visibleFolders.map((folder) =>
              <ListItem disablePadding key={folder.relpath}>
                <ListItemButton
                  disabled={isMoving}
                  onClick={() => setBrowseFolder(folder.relpath)}
                  sx={{ minHeight: 44 }}
                >
                  <ListItemIcon><FolderIcon /></ListItemIcon>
                  <ListItemText primary={folder.name} />
                </ListItemButton>
              </ListItem>
            )}
          </List>
        }
      </DialogContent>
      <DialogActions>
        <Button disabled={isMoving} onClick={close} sx={{ minHeight: 44 }}>
          {t('general.buttons.cancel')}
        </Button>
        <Button
          disabled={isMoveDisabled}
          onClick={moveEntries}
          sx={{ minHeight: 44 }}
          variant="contained"
        >
          {t('library.folders.manager.move.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default MoveEntriesDialog;
