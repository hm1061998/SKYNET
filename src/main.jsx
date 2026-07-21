import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { AGENT_NAME } from './agentConfig.js';

document.title = AGENT_NAME;
createRoot(document.getElementById('root')).render(<App />);
