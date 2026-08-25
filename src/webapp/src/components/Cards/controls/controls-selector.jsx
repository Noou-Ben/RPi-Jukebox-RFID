import { useTranslation } from 'react-i18next';

import {
  Grid,
  Typography,
} from '@mui/material';

import SelectCommandAliases from './select-command-aliases';
import SelectPlayMusic from './actions/play-music';
import ActionTypeFields from './action-type-fields';
import { buildActionData } from '../utils';

const ControlsSelector = ({
  actionData,
  setActionData,
  cardId,
}) => {
  const { t } = useTranslation();

  const handleActionChange = (event) => {
    setActionData(
      buildActionData(event.target.value)
    );
  };

  const handleActionDataChange = (action, command, args) => {
    setActionData(
      buildActionData(action, command, args)
    );
  }

  return (
    <Grid container sx={{ flexDirection: 'column' }}>
      <Grid container sx={{ alignItems: 'center' }}>
        <Grid size={5}>
          <Typography>
            {t('cards.controls.controls-selector.label')}
          </Typography>
        </Grid>
        <Grid size={7}>
          <SelectCommandAliases
            actionData={actionData}
            handleActionChange={handleActionChange}
          />
        </Grid>
      </Grid>
      <Grid
        container
        sx={{
          alignItems: 'center',
          marginTop: '20px',
        }}
      >
        {actionData.action === 'play_music' &&
          <SelectPlayMusic
            actionData={actionData}
            cardId={cardId}
          />
        }

        {actionData.action !== 'play_music' &&
          <ActionTypeFields
            actionData={actionData}
            handleActionDataChange={handleActionDataChange}
          />
        }
      </Grid>
    </Grid>
  );
};

export default ControlsSelector;
