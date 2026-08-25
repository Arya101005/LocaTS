import React, { useState, useEffect } from 'react';
import ReportForm from './components/ReportForm';
import ReportHistory from './components/ReportHistory';
import { initDB, saveReport, getAllReports, syncReports, getSyncStatus } from './services/db';
import './App.css';

function App() {
  const [reports, setReports] = useState([]);
  const [syncStatus, setSyncStatus] = useState({ pending: 0, synced: 0, conflict: 0 });
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [activeTab, setActiveTab] = useState('report');

  useEffect(() => {
    initDB().then(() => loadReports());

    const handleOnline = () => {
      setIsOnline(true);
      syncReports().then(() => loadReports());
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const loadReports = async () => {
    const allReports = await getAllReports();
    setReports(allReports);
    const status = await getSyncStatus();
    setSyncStatus(status);
  };

  const handleSubmit = async (report) => {
    await saveReport(report);
    await loadReports();
  };

  return (
    <div className="pwa-app">
      <header className="pwa-header">
        <h1>LocaTS Report</h1>
        <div className="status-bar">
          <span className={`online-indicator ${isOnline ? 'online' : 'offline'}`}>
            {isOnline ? 'ONLINE' : 'OFFLINE'}
          </span>
          {syncStatus.pending > 0 && (
            <span className="sync-badge">{syncStatus.pending} pending sync</span>
          )}
        </div>
      </header>

      <nav className="pwa-nav">
        <button
          className={activeTab === 'report' ? 'active' : ''}
          onClick={() => setActiveTab('report')}
        >
          Report Hazard
        </button>
        <button
          className={activeTab === 'history' ? 'active' : ''}
          onClick={() => setActiveTab('history')}
        >
          My Reports ({reports.length})
        </button>
      </nav>

      <main className="pwa-content">
        {activeTab === 'report' ? (
          <ReportForm onSubmit={handleSubmit} />
        ) : (
          <ReportHistory reports={reports} syncStatus={syncStatus} />
        )}
      </main>
    </div>
  );
}

export default App;
