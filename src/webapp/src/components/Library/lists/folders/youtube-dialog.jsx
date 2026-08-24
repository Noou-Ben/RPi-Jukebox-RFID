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
  TextField,
  Typography,
} from '@mui/material';

import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';

import PubSubContext from '../../../../context/pubsub/context';
import request from '../../../../utils/request';

const inProgressStates = new Set(['submitting', 'preparing', 'downloading', 'converting']);

const YoutubeDialog = ({
  folder,
  onClose,
  onLibraryChanged,
  open,
}) => {
  const { t } = useTranslation();
  const { state: pubsubState = {} } = useContext(PubSubContext);
  const [url, setUrl] = useState('');
  const [submittedUrl, setSubmittedUrl] = useState(null);
  const [phase, setPhase] = useState('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [title, setTitle] = useState('');
  const [percent, setPercent] = useState(0);

  const progress = pubsubState['library.youtube.progress'];

  useEffect(() => {
    if (!open) return;
    setUrl('');
    setSubmittedUrl(null);
    setPhase('idle');
    setErrorMessage('');
    setTitle('');
    setPercent(0);
  }, [open]);

  useEffect(() => {
    if (!submittedUrl || !progress || progress.url !== submittedUrl) return;

    setPhase(progress.state);
    if (progress.title) setTitle(progress.title);
    if (typeof progress.percent === 'number') setPercent(progress.percent);

    if (progress.state === 'error') {
      setErrorMessage(progress.message || t('library.folders.manager.youtube-dialog.generic-error'));
    }
    else if (progress.state === 'complete') {
      onLibraryChanged();
    }
  }, [onLibraryChanged, progress, submittedUrl, t]);

  const isRunning = inProgressStates.has(phase);

  const submit = async (event) => {
    event.preventDefault();
    const trimmedUrl = url.trim();
    if (!trimmedUrl || isRunning) return;

    setPhase('submitting');
    setErrorMessage('');
    const { result, error } = await request('youtube_download', { url: trimmedUrl, folder });

    if (error || !result?.accepted) {
      setPhase('error');
      setErrorMessage(
        result?.message || t('library.folders.manager.youtube-dialog.generic-error'),
      );
      return;
    }
    setSubmittedUrl(trimmedUrl);
  };

  const startOver = () => {
    setUrl('');
    setSubmittedUrl(null);
    setPhase('idle');
    setErrorMessage('');
    setTitle('');
    setPercent(0);
  };

  const statusText = () => {
    if (phase === 'downloading') {
      return t('library.folders.manager.youtube-dialog.status.downloading', {
        percent: Math.round(percent),
      });
    }
    if (phase === 'error') return errorMessage;
    return t(`library.folders.manager.youtube-dialog.status.${phase}`, {
      defaultValue: '',
    });
  };

  return (
    <Dialog fullWidth maxWidth="sm" onClose={isRunning ? undefined : onClose} open={open}>
      <form onSubmit={submit}>
        <DialogTitle>{t('library.folders.manager.youtube-dialog.title')}</DialogTitle>
        <DialogContent>
          {!submittedUrl &&
            <>
              <Typography color="text.secondary" sx={{ marginBottom: 2 }} variant="body2">
                {t('library.folders.manager.youtube-dialog.description')}
              </Typography>
              <TextField
                autoFocus
                disabled={phase === 'submitting'}
                fullWidth
                label={t('library.folders.manager.youtube-dialog.url-label')}
                margin="dense"
                onChange={(event) => setUrl(event.target.value)}
                placeholder={t('library.folders.manager.youtube-dialog.url-placeholder')}
                required
                type="url"
                value={url}
              />
              {phase === 'error' &&
                <Alert severity="error" sx={{ marginTop: 2 }}>{errorMessage}</Alert>
              }
            </>
          }
          {submittedUrl &&
            <Box>
              <Typography sx={{ overflowWrap: 'anywhere' }} variant="subtitle2">
                {title || submittedUrl}
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
              {(phase === 'downloading' || phase === 'preparing' || phase === 'converting') &&
                <LinearProgress
                  sx={{ marginTop: 1.5 }}
                  value={phase === 'downloading' ? percent : undefined}
                  variant={phase === 'downloading' && percent > 0 ? 'determinate' : 'indeterminate'}
                />
              }
            </Box>
          }
        </DialogContent>
        <DialogActions>
          {(phase === 'complete' || phase === 'error') &&
            <Button onClick={startOver} sx={{ minHeight: 44 }}>
              {t('library.folders.manager.youtube-dialog.download-another')}
            </Button>
          }
          <Button onClick={onClose} sx={{ minHeight: 44 }}>
            {t('general.buttons.close')}
          </Button>
          {!submittedUrl &&
            <Button
              disabled={!url.trim() || phase === 'submitting'}
              sx={{ minHeight: 44 }}
              type="submit"
              variant="contained"
            >
              {t('library.folders.manager.youtube-dialog.confirm')}
            </Button>
          }
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default YoutubeDialog;
