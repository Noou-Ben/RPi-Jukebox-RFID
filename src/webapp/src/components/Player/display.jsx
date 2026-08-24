import { useContext } from 'react';
import { useTranslation } from 'react-i18next';

import PlayerContext from '../../context/player/context';

import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

const Display = () => {
  const { t } = useTranslation();
  const { state: { playerstatus } } = useContext(PlayerContext);
  const theme = useTheme();

  const dontBreak = {
    whiteSpace: 'nowrap',
    width: '100%',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  };

  const titleStyle = {
    ...dontBreak,
    fontFamily: theme.typography.fontFamilyDisplay,
    fontStyle: 'italic',
    fontWeight: 600,
  };

  return (
    <Grid container>
      <Typography sx={titleStyle} component="h5" variant="h5">
        {playerstatus?.songid
          ? (playerstatus?.title || t('player.display.unknown-title'))
          : t('player.display.no-song-in-queue')
        }
      </Typography>
      <Typography sx={dontBreak} variant="subtitle1" color="textSecondary">
        {playerstatus?.songid && (playerstatus?.artist || t('player.display.unknown-artist')) }
        <span style={{ marginLeft: '5px', marginRight: '5px' }}>&bull;</span>
        {playerstatus?.songid && (playerstatus?.album || playerstatus?.file) }
      </Typography>
    </Grid>
  );
};

export default Display;
