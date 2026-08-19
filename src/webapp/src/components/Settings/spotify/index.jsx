import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  FormGroup,
  FormControlLabel,
  Grid,
  Link,
  Typography,
} from '@mui/material';

import { SwitchWithLoader } from '../../general';

import request from '../../../utils/request';

const helpUrl = 'https://github.com/MiczFlor/RPi-Jukebox-RFID/blob/future3/main/documentation/builders/spotify.md';

// Connection status only meaningfully changes on the order of seconds (process
// start-up, pairing from the Spotify app, ...), so a slow poll is enough and avoids
// adding a dedicated websocket subscription for this one settings panel.
const POLL_INTERVAL_MS = 5000;

const SettingsSpotify = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const pollRef = useRef(null);

  const fetchStatus = async () => {
    const { result, error } = await request('getSpotifyStatus');

    if (error) return console.error(error);
    setStatus(result);
  };

  const toggleSpotify = async () => {
    setIsLoading(true);
    const command = status?.enabled ? 'disableSpotify' : 'enableSpotify';
    const { result, error } = await request(command);

    if (error) console.error(error);
    if (result) setStatus(result);
    else await fetchStatus();

    setIsLoading(false);
  };

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      await fetchStatus();
      setIsLoading(false);
    })();

    pollRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(pollRef.current);
  }, []);

  const enabled = status?.enabled ?? false;
  const sessionActive = status?.session_active ?? false;
  const deviceName = status?.device_name ?? '';

  return (
    <Card>
      <CardHeader
        title={t('settings.spotify.title')}
        subheader={
          <>
            {t('settings.spotify.description')}
            {' '}
            <Link href={helpUrl} target="_blank" rel="noreferrer">
              {t('settings.spotify.help')}
            </Link>
          </>
        }
      />
      <Divider />
      <CardContent>
        <Grid container sx={{ flexDirection: 'column' }}>
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
                    onChange={() => toggleSpotify()}
                  />
                }
                label={t('settings.spotify.control-label')}
                labelPlacement="start"
              />
            </FormGroup>
          </Grid>
          {enabled && (
            <Grid>
              <Typography variant="body2">
                {sessionActive
                  ? t('settings.spotify.connected', { device: deviceName })
                  : t('settings.spotify.waiting-for-connection', { device: deviceName })}
              </Typography>
              {status?.last_error && (
                <Typography variant="body2" color="error">
                  {status.last_error}
                </Typography>
              )}
              {!status?.process_running && !status?.last_error && (
                <Typography variant="body2" color="error">
                  {t('settings.spotify.process-not-running')}
                </Typography>
              )}
            </Grid>
          )}
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsSpotify;
