import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import AetherisVisualLab from './aetheris/AetherisVisualLab';
import './index.css';

const showAetherisLab = new URLSearchParams(window.location.search).get('aetherisLab') === '1';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {showAetherisLab ? <AetherisVisualLab /> : <App />}
  </React.StrictMode>,
);
