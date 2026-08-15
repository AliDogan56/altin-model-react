import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.scss';
import './chart.scss';

const root = document.getElementById('root');

if (!root) {
  throw new Error('React kök elementi bulunamadı.');
}

createRoot(root).render(<React.StrictMode><App /></React.StrictMode>);
