import { useTranslation } from 'react-i18next';

import {
  Grid,
  Slider,
  Stack,
  Typography,
} from '@mui/material';

import VolumeDownIcon from '@mui/icons-material/VolumeDown';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';

import {
  getActionAndCommand,
  getArgsValues,
} from '../../../utils';

const marks = [0, 25, 50, 75, 100].map(
  (value) => ({ value, label: value })
);

const SliderSetVolume = ({
  actionData,
  handleActionDataChange,
}) => {
  const { t } = useTranslation();

  const { action, command } = getActionAndCommand(actionData);
  const [volume] = getArgsValues(actionData);

  const onChange = (event, volume) => {
    handleActionDataChange(action, command, { volume })
  };

  return (
    <Grid
      container
      sx={{
        alignItems: 'center',
        marginTop: '20px',
      }}
    >
      <Grid size={12}>
        <Typography>
          {t('cards.controls.actions.audio.set-volume.title')}
        </Typography>
        <Stack
          spacing={2}
          sx={{
            alignItems: 'center',
            flexDirection: 'row',
          }}
        >
          <VolumeDownIcon />
          <Slider
            aria-label={t('cards.controls.actions.audio.set-volume.title')}
            value={volume || 0}
            marks={marks}
            step={1}
            min={0}
            max={100}
            valueLabelDisplay="auto"
            onChange={onChange}
          />
          <VolumeUpIcon />
        </Stack>
      </Grid>
    </Grid>
  );
};

export default SliderSetVolume;
