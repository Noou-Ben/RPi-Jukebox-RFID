import { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from '@mui/material';

import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';

import PubSubContext from '../../../../context/pubsub/context';
import request from '../../../../utils/request';

const inProgressStates = new Set(['submitting', 'preparing', 'downloading']);

const JukeboxHubDialog = ({
  folder,
  onClose,
  onLibraryChanged,
  open,
  registerMusicToCard,
}) => {
  const { t } = useTranslation();
  const { state: pubsubState = {} } = useContext(PubSubContext);

  // Step 1: list of remote playlists to pick from
  const [listPhase, setListPhase] = useState('loading'); // loading | loaded | empty | error
  const [playlists, setPlaylists] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  // Step 2: download + progress, once a playlist has been submitted
  const [submittedId, setSubmittedId] = useState(null);
  const [phase, setPhase] = useState('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [playlistName, setPlaylistName] = useState('');
  const [percent, setPercent] = useState(0);
  const [currentTrack, setCurrentTrack] = useState(0);
  const [resultFolder, setResultFolder] = useState('');

  const progress = pubsubState['library.jukebox_hub.progress'];

  const fetchPlaylists = async () => {
    setListPhase('loading');
    const { result, error } = await request('jukebox_hub_list_playlists');
    if (error || !Array.isArray(result)) {
      setListPhase('error');
      return;
    }
    if (!result.length) {
      setListPhase('empty');
      return;
    }
    setPlaylists(result);
    setListPhase('loaded');
  };

  useEffect(() => {
    if (!open) return;
    setSelectedId(null);
    setSubmittedId(null);
    setPhase('idle');
    setErrorMessage('');
    setPlaylistName('');
    setPercent(0);
    setCurrentTrack(0);
    setResultFolder('');
    fetchPlaylists();
  }, [open]);

  useEffect(() => {
    if (!submittedId || !progress || String(progress.playlist_id) !== String(submittedId)) return;

    setPhase(progress.state);
    if (progress.playlist_name) setPlaylistName(progress.playlist_name);
    if (typeof progress.percent === 'number') setPercent(progress.percent);
    if (typeof progress.current_track === 'number') setCurrentTrack(progress.current_track);
    if (progress.folder) setResultFolder(progress.folder);

    if (progress.state === 'error') {
      setErrorMessage(progress.message || t('library.folders.manager.jukebox-hub-dialog.generic-error'));
    }
    else if (progress.state === 'complete') {
      onLibraryChanged();
      if (registerMusicToCard) {
        registerMusicToCard('play_folder', { folder: progress.folder, recursive: true });
      }
    }
  }, [onLibraryChanged, progress, registerMusicToCard, submittedId, t]);

  const isRunning = inProgressStates.has(phase);
  const selectedPlaylist = playlists.find(({ id }) => String(id) === String(selectedId));

  const submit = async (event) => {
    event.preventDefault();
    if (!selectedId || isRunning) return;

    setPhase('submitting');
    setErrorMessage('');
    const { result, error } = await request('jukebox_hub_download_playlist', {
      playlist_id: selectedId,
      folder,
    });

    if (error || !result?.accepted) {
      setPhase('error');
      setErrorMessage(
        result?.message || t('library.folders.manager.jukebox-hub-dialog.generic-error'),
      );
      return;
    }
    setPlaylistName(selectedPlaylist?.name || '');
    setSubmittedId(selectedId);
  };

  const startOver = () => {
    setSelectedId(null);
    setSubmittedId(null);
    setPhase('idle');
    setErrorMessage('');
    setPlaylistName('');
    setPercent(0);
    setCurrentTrack(0);
    setResultFolder('');
    fetchPlaylists();
  };

  const statusText = () => {
    if (phase === 'downloading') {
      return t('library.folders.manager.jukebox-hub-dialog.status.downloading', {
        current: currentTrack,
        total: selectedPlaylist?.track_count ?? '?',
      });
    }
    if (phase === 'error') return errorMessage;
    return t(`library.folders.manager.jukebox-hub-dialog.status.${phase}`, {
      defaultValue: '',
    });
  };

  return (
    <Dialog fullWidth maxWidth="sm" onClose={isRunning ? undefined : onClose} open={open}>
      <form onSubmit={submit}>
        <DialogTitle>{t('library.folders.manager.jukebox-hub-dialog.title')}</DialogTitle>
        <DialogContent>
          {!submittedId &&
            <>
              <Typography color="text.secondary" sx={{ marginBottom: 2 }} variant="body2">
                {t('library.folders.manager.jukebox-hub-dialog.description')}
              </Typography>
              {listPhase === 'loading' &&
                <Box sx={{ display: 'flex', justifyContent: 'center', padding: 2 }}>
                  <LinearProgress sx={{ width: '100%' }} />
                </Box>
              }
              {listPhase === 'error' &&
                <Alert severity="error">
                  {t('library.folders.manager.jukebox-hub-dialog.list-error')}
                </Alert>
              }
              {listPhase === 'empty' &&
                <Alert severity="info">
                  {t('library.folders.manager.jukebox-hub-dialog.list-empty')}
                </Alert>
              }
              {listPhase === 'loaded' &&
                <List sx={{ maxHeight: 320, overflowY: 'auto' }}>
                  {playlists.map(({ id, name, track_count: trackCount }) => (
                    <ListItemButton
                      key={id}
                      onClick={() => setSelectedId(id)}
                      selected={String(selectedId) === String(id)}
                      sx={{ minHeight: 44 }}
                    >
                      <ListItemText
                        primary={name}
                        secondary={t('library.folders.manager.jukebox-hub-dialog.track-count', {
                          count: trackCount,
                        })}
                      />
                    </ListItemButton>
                  ))}
                </List>
              }
              {phase === 'error' &&
                <Alert severity="error" sx={{ marginTop: 2 }}>{errorMessage}</Alert>
              }
            </>
          }
          {submittedId &&
            <Box>
              <Typography sx={{ overflowWrap: 'anywhere' }} variant="subtitle2">
                {playlistName || submittedId}
              </Typography>
              <Typography
                color={phase === 'error' ? 'error' : 'text.secondary'}
                component="div"
                sx={{ alignItems: 'center', display: 'flex', gap: 0.5, marginTop: 0.5 }}
                variant="body2"
              >
                {phase === 'error' && <ErrorIcon fontSize="inherit" />}
                {phase === 'complete' && <CheckCircleIcon color="success" fontSize="inherit" />}
                {statusText()}
              </Typography>
              {(phase === 'downloading' || phase === 'preparing' || phase === 'submitting') &&
                <LinearProgress
                  sx={{ marginTop: 1.5 }}
                  value={phase === 'downloading' ? percent : undefined}
                  variant={phase === 'downloading' && percent > 0 ? 'determinate' : 'indeterminate'}
                />
              }
              {phase === 'complete' &&
                <Typography color="text.secondary" sx={{ marginTop: 1 }} variant="body2">
                  {t('library.folders.manager.jukebox-hub-dialog.redirecting-to-card', {
                    folder: resultFolder,
                  })}
                </Typography>
              }
            </Box>
          }
        </DialogContent>
        <DialogActions>
          {(phase === 'error') &&
            <Button onClick={startOver} sx={{ minHeight: 44 }}>
              {t('library.folders.manager.jukebox-hub-dialog.try-again')}
            </Button>
          }
          <Button onClick={onClose} sx={{ minHeight: 44 }}>
            {t('general.buttons.close')}
          </Button>
          {!submittedId &&
            <Button
              disabled={!selectedId || phase === 'submitting'}
              sx={{ minHeight: 44 }}
              type="submit"
              variant="contained"
            >
              {t('library.folders.manager.jukebox-hub-dialog.confirm')}
            </Button>
          }
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default JukeboxHubDialog;
