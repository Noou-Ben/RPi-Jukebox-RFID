import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Button,
  Card,
  CardContent,
  CardHeader,
  Collapse,
  Divider,
  FormGroup,
  FormControlLabel,
  Grid,
  TextField,
  Typography,
} from '@mui/material';

import { SwitchWithLoader } from '../../general';

import request from '../../../utils/request';

const SettingsJukeboxHub = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [url, setUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [savedMessage, setSavedMessage] = useState(false);

  const fetchStatus = async () => {
    const { result, error } = await request('getJukeboxHubStatus');
    if (error) return console.error(error);
    setStatus(result);
    setUrl(result?.url ?? '');
    setApiKey(result?.api_key ?? '');
  };

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      await fetchStatus();
      setIsLoading(false);
    })();
  }, []);

  const enabled = status?.enable ?? false;

  const saveConfig = async (overrides = {}) => {
    setIsLoading(true);
    setSavedMessage(false);
    const { result, error } = await request('setJukeboxHubConfig', {
      enable: enabled,
      url,
      api_key: apiKey,
      ...overrides,
    });

    if (error) console.error(error);
    if (result) {
      setStatus(result);
      setSavedMessage(true);
    }
    else {
      await fetchStatus();
    }
    setIsLoading(false);
  };

  const toggleEnabled = () => saveConfig({ enable: !enabled });

  return (
    <Card>
      <CardHeader
        title={t('settings.jukebox-hub.title')}
        subheader={t('settings.jukebox-hub.description')}
      />
      <Divider />
      <CardContent>
        <Grid container sx={{ flexDirection: 'column', gap: 2 }}>
          <Grid>
            <FormGroup>
              <FormControlLabel
                sx={{
                  justifyContent: 'space-between',
                  marginLeft: '0',
                }}
                control={
                  <SwitchWithLoader
                    isLoading={isLoading}
                    checked={enabled}
                    onChange={toggleEnabled}
                  />
                }
                label={t('settings.jukebox-hub.control-label')}
                labelPlacement="start"
              />
            </FormGroup>
          </Grid>
          <Collapse in={enabled}>
            <Grid container sx={{ flexDirection: 'column', gap: 2 }}>
              <Grid>
                <TextField
                  fullWidth
                  label={t('settings.jukebox-hub.url-label')}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder={t('settings.jukebox-hub.url-placeholder')}
                  value={url}
                />
              </Grid>
              <Grid>
                <TextField
                  fullWidth
                  label={t('settings.jukebox-hub.api-key-label')}
                  onChange={(event) => setApiKey(event.target.value)}
                  type="password"
                  value={apiKey}
                />
              </Grid>
              <Grid sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Button
                  disabled={isLoading}
                  onClick={() => saveConfig()}
                  sx={{ minHeight: 44 }}
                  variant="contained"
                >
                  {t('settings.jukebox-hub.save')}
                </Button>
                {savedMessage &&
                  <Typography color="text.secondary" variant="body2">
                    {t('settings.jukebox-hub.saved')}
                  </Typography>
                }
              </Grid>
            </Grid>
          </Collapse>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsJukeboxHub;
