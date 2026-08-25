import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// Error boundary to catch render crashes
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorInfo: null };
  }
  componentDidCatch(error, errorInfo) {
    console.error('[LOCATS ERROR]', error.message, error.stack);
    this.setState({ error, errorInfo });
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, fontFamily: 'monospace', whiteSpace: 'pre-wrap', background: '#fff', minHeight: '100vh' }}>
          <h1 style={{ color: '#DC2626', fontSize: 20 }}>App Error</h1>
          <p style={{ color: '#EF4444' }}>{this.state.error.message}</p>
          <pre style={{ fontSize: 11, color: '#666', overflow: 'auto' }}>{this.state.errorInfo?.componentStack || this.state.error.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
