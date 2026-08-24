import { createRoot } from 'react-dom/client';
import { StyledEngineProvider } from '@mui/material/styles';

import '@fontsource/manrope/400.css';
import '@fontsource/manrope/500.css';
import '@fontsource/manrope/600.css';
import '@fontsource/manrope/700.css';
import '@fontsource/manrope/800.css';
import '@fontsource/fraunces/600-italic.css';

import App from './App';
import ColorModeProvider from './context/colormode';
import { i18nReady } from './i18n';

const root = createRoot(document.querySelector('#root'));

i18nReady.then(() => {
  root.render(
    <StyledEngineProvider injectFirst>
      <ColorModeProvider>
        <App />
      </ColorModeProvider>
    </StyledEngineProvider>,
  );
});
