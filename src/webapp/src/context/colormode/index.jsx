import { useMemo, useState } from 'react';

import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';

import ColorModeContext from './context';
import getTheme from '../../theme';

const STORAGE_KEY = 'phoniebox-color-mode';

const getInitialMode = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // localStorage unavailable (private browsing, disabled storage, ...)
  }
  return 'dark';
};

const ColorModeProvider = ({ children }) => {
  const [mode, setMode] = useState(getInitialMode);

  const toggleMode = () => {
    setMode((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // ignore write failures, mode still works for this session
      }
      return next;
    });
  };

  const theme = useMemo(() => getTheme(mode), [mode]);
  const context = useMemo(() => ({ mode, toggleMode }), [mode]);

  return (
    <ColorModeContext.Provider value={context}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
};

export default ColorModeProvider;
