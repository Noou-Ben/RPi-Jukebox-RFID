import { createContext } from 'react';

const ColorModeContext = createContext({
  mode: 'dark',
  toggleMode: () => {},
});

export default ColorModeContext;
