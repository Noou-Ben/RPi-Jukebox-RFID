import { useContext } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Grid,
  Switch,
  Typography,
} from '@mui/material';

import ColorModeContext from '../../../context/colormode/context';

const DarkMode = () => {
  const { t } = useTranslation();
  const { mode, toggleMode } = useContext(ColorModeContext);

  return (
    <Grid
      container
      sx={{
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <Grid
        container
        sx={{
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Typography>
          {t('settings.general.dark_mode.title')}
        </Typography>
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          marginLeft: '0',
        }}>
          <Switch
            checked={mode === 'dark'}
            onChange={toggleMode}
          />
        </Box>
      </Grid>
    </Grid>
  );
};

export default DarkMode;
