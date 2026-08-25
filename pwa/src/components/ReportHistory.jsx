import React from 'react';

const ALERT_ICONS = {
  flood: '~',
  landslide: '\\',
  seismic: 'S',
  cyclone: '@',
};

const SEVERITY_COLORS = {
  low: '#22c55e',
  moderate: '#eab308',
  high: '#f97316',
  very_high: '#ef4444',
  critical: '#dc2626',
};

function getSeverityColor(severity) {
  if (severity < 0.3) return SEVERITY_COLORS.low;
  if (severity < 0.5) return SEVERITY_COLORS.moderate;
  if (severity < 0.7) return SEVERITY_COLORS.high;
  if (severity < 0.9) return SEVERITY_COLORS.very_high;
  return SEVERITY_COLORS.critical;
}

export default function ReportHistory({ reports, syncStatus }) {
  return (
    <div className="report-history">
      <div className="sync-summary">
        <span className="sync-stat synced">{syncStatus.synced} synced</span>
        <span className="sync-stat pending">{syncStatus.pending} pending</span>
        {syncStatus.conflict > 0 && (
          <span className="sync-stat conflict">{syncStatus.conflict} conflicts</span>
        )}
      </div>

      {reports.length === 0 ? (
        <div className="no-reports">
          <p>No reports yet. Submit your first hazard report to help your community.</p>
        </div>
      ) : (
        <div className="reports-list">
          {reports.map((report) => (
            <div key={report.id} className="report-card">
              <div className="report-header">
                <span className="report-icon">{ALERT_ICONS[report.hazard_type] || '?'}</span>
                <span className="report-type">{report.hazard_type}</span>
                <span
                  className="report-severity"
                  style={{ color: getSeverityColor(report.severity_estimate) }}
                >
                  {Math.round(report.severity_estimate * 100)}%
                </span>
                <span className={`report-sync ${report.sync_status}`}>
                  {report.sync_status}
                </span>
              </div>
              {report.description && (
                <p className="report-desc">{report.description}</p>
              )}
              <div className="report-meta">
                <span>{new Date(report.timestamp).toLocaleString()}</span>
                {report.location && (
                  <span>
                    {report.location.lat.toFixed(3)}, {report.location.lon.toFixed(3)}
                  </span>
                )}
              </div>
              {report.photo && (
                <img src={report.photo} alt="Report" className="report-photo" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
