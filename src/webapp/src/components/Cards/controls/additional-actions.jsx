import { useTranslation } from 'react-i18next';

import {
  Button,
  Divider,
  Grid,
  IconButton,
  Typography,
} from '@mui/material';

import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';

import SelectCommandAliases from './select-command-aliases';
import ActionTypeFields from './action-type-fields';
import { buildActionData } from '../utils';

// `play_music` is excluded: selecting it navigates away to the Library page,
// which would lose the state of this row (and every other unsaved row).
const EXCLUDED_ACTIONS = ['play_music'];

const AdditionalActions = ({
  actionData,
  setActionData,
}) => {
  const { t } = useTranslation();
  const postActions = actionData.postActions || [];

  const updatePostAction = (index, updatedRow) => {
    const nextPostActions = postActions.map(
      (row, i) => (i === index ? updatedRow : row)
    );

    setActionData({ ...actionData, postActions: nextPostActions });
  };

  const handleAdd = () => {
    setActionData({ ...actionData, postActions: [...postActions, {}] });
  };

  const handleRemove = (index) => {
    setActionData({
      ...actionData,
      postActions: postActions.filter((_, i) => i !== index),
    });
  };

  return (
    <Grid container sx={{ flexDirection: 'column', marginTop: '30px' }}>
      <Typography>
        {t('cards.controls.additional-actions.label')}
      </Typography>

      {postActions.map((postAction, index) => (
        <Grid
          container
          key={index}
          sx={{ alignItems: 'center', marginTop: '20px' }}
        >
          <Grid size={5}>
            <SelectCommandAliases
              actionData={postAction}
              excludeActions={EXCLUDED_ACTIONS}
              handleActionChange={(event) =>
                updatePostAction(index, buildActionData(event.target.value))
              }
            />
          </Grid>
          <Grid size={6}>
            <ActionTypeFields
              actionData={postAction}
              handleActionDataChange={(action, command, args) =>
                updatePostAction(index, buildActionData(action, command, args))
              }
            />
          </Grid>
          <Grid size={1} sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <IconButton
              aria-label={t('cards.controls.additional-actions.remove')}
              onClick={() => handleRemove(index)}
              size="small"
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Grid>
          <Grid size={12}>
            <Divider sx={{ marginTop: '20px' }} />
          </Grid>
        </Grid>
      ))}

      <Grid size={12} sx={{ marginTop: '20px' }}>
        <Button
          variant="text"
          onClick={handleAdd}
          startIcon={<AddIcon />}
        >
          {t('cards.controls.additional-actions.add')}
        </Button>
      </Grid>
    </Grid>
  );
};

export default AdditionalActions;
