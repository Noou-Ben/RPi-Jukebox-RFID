import { createTheme } from '@mui/material/styles';

const shape = {
  borderRadius: 14,
};

const typography = {
  fontFamily: '"Manrope", "Helvetica", "Arial", sans-serif',
  fontFamilyDisplay: '"Fraunces", "Georgia", serif',
  button: {
    textTransform: 'none',
    fontWeight: 700,
  },
  h1: { fontWeight: 800 },
  h2: { fontWeight: 800 },
  h3: { fontWeight: 800 },
  h4: { fontWeight: 800 },
  h5: { fontWeight: 800 },
  h6: { fontWeight: 800 },
};

const lightPalette = {
  mode: 'light',
  primary: {
    main: '#2B5C34',
    contrastText: '#FFFFFF',
  },
  background: {
    default: '#F4EFDC',
    paper: '#FCFAF1',
  },
  text: {
    primary: '#1B241C',
    secondary: '#6E7568',
  },
  divider: '#E3DBC2',
  surfaceAlt: '#EAE3C8',
};

const darkPalette = {
  mode: 'dark',
  primary: {
    main: '#4F9463',
    contrastText: '#131C10',
  },
  background: {
    default: '#141B12',
    paper: '#1E2818',
  },
  text: {
    primary: '#F1EAD4',
    secondary: '#96A088',
  },
  divider: '#2C3627',
  surfaceAlt: '#28331F',
};

const components = {
  MuiPaper: {
    styleOverrides: {
      root: {
        backgroundImage: 'none',
      },
    },
  },
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: 18,
      },
    },
  },
  MuiButton: {
    styleOverrides: {
      root: {
        borderRadius: 12,
      },
      contained: {
        boxShadow: 'none',
        '&:hover': { boxShadow: 'none' },
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        fontWeight: 700,
      },
    },
  },
  MuiTab: {
    styleOverrides: {
      root: {
        textTransform: 'none',
        fontWeight: 700,
      },
    },
  },
  MuiSlider: {
    styleOverrides: {
      root: {
        height: 4,
      },
      thumb: {
        width: 14,
        height: 14,
      },
    },
  },
  MuiBottomNavigation: {
    styleOverrides: {
      root: ({ theme }) => ({
        backgroundColor: theme.palette.background.paper,
        borderTop: `1px solid ${theme.palette.divider}`,
      }),
    },
  },
  MuiBottomNavigationAction: {
    styleOverrides: {
      root: ({ theme }) => ({
        color: theme.palette.text.secondary,
        '&.Mui-selected': {
          color: theme.palette.primary.main,
        },
      }),
      label: {
        fontSize: '11px',
        fontWeight: 700,
        '&.Mui-selected': {
          fontSize: '11px',
        },
      },
    },
  },
};

const getTheme = (mode) => createTheme({
  palette: mode === 'light' ? lightPalette : darkPalette,
  shape,
  typography,
  components,
});

export default getTheme;
