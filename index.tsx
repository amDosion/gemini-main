import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './styles/tailwind.css';
import App from './frontend/App';
import { GlobalErrorBoundary } from './frontend/components/common/GlobalErrorBoundary';
import { startFrontendTelemetry, startTelemetrySpan } from './frontend/services/frontendTelemetry';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
startFrontendTelemetry();
const bootstrapSpan = startTelemetrySpan('app.bootstrap', {
  route: typeof window !== 'undefined' ? window.location.pathname : '/',
});

root.render(
  <React.StrictMode>
    <GlobalErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </GlobalErrorBoundary>
  </React.StrictMode>
);

if (typeof window !== 'undefined') {
  const finalizeBootstrap = () => {
    bootstrapSpan.end('ok');
  };
  if (typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(finalizeBootstrap);
  } else {
    window.setTimeout(finalizeBootstrap, 0);
  }
}
