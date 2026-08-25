import React, { useState, useRef } from 'react';

const HAZARD_TYPES = [
  { value: 'flood', label: 'Flood / Water Rising', icon: '~' },
  { value: 'landslide', label: 'Landslide / Soil Movement', icon: '\\' },
  { value: 'seismic', label: 'Earthquake / Tremors', icon: 'S' },
  { value: 'cyclone', label: 'Cyclone / Heavy Wind', icon: '@' },
];

const SEVERITY_LABELS = [
  { value: 0.2, label: 'Low - Some water/dust visible' },
  { value: 0.4, label: 'Moderate - Roads partially affected' },
  { value: 0.6, label: 'High - Immediate danger nearby' },
  { value: 0.8, label: 'Very High - Area becoming unsafe' },
  { value: 1.0, label: 'Critical - Evacuation needed NOW' },
];

export default function ReportForm({ onSubmit }) {
  const [hazardType, setHazardType] = useState('flood');
  const [severity, setSeverity] = useState(0.5);
  const [description, setDescription] = useState('');
  const [photo, setPhoto] = useState(null);
  const [location, setLocation] = useState(null);
  const [locationStatus, setLocationStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const fileInputRef = useRef(null);

  const getLocation = () => {
    setLocationStatus('Getting location...');
    if (!navigator.geolocation) {
      setLocationStatus('Geolocation not supported');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocationStatus(`Location: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      },
      (err) => {
        setLocationStatus('Location unavailable - report will use approximate location');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handlePhoto = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => setPhoto(ev.target.result);
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    const report = {
      id: `rpt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      reporter_id: `user-${navigator.userAgent.slice(0, 8).replace(/\s/g, '')}`,
      hazard_type: hazardType,
      severity_estimate: severity,
      description,
      location: location || { lat: 28.6, lon: 77.2 },  // Default to Delhi if no location
      photo: photo,
      photo_hash: photo ? await hashString(photo) : null,
      timestamp: new Date().toISOString(),
      sync_status: navigator.onLine ? 'synced' : 'pending',
      client_timestamp: Date.now(),
    };

    await onSubmit(report);
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      setDescription('');
      setPhoto(null);
      setSeverity(0.5);
    }, 2000);
  };

  if (submitted) {
    return (
      <div className="success-message">
        <div className="success-icon">!</div>
        <h2>Report Submitted</h2>
        <p>Your hazard report has been recorded. Thank you for helping keep your community safe.</p>
        {!navigator.onLine && (
          <p className="pending-note">Report will sync when connection is restored.</p>
        )}
      </div>
    );
  }

  return (
    <form className="report-form" onSubmit={handleSubmit}>
      <h2>Report a Hazard</h2>
      <p className="form-subtitle">Your report helps authorities identify danger zones.</p>

      <div className="form-group">
        <label>Type of Hazard</label>
        <div className="hazard-type-grid">
          {HAZARD_TYPES.map((ht) => (
            <button
              key={ht.value}
              type="button"
              className={`hazard-type-btn ${hazardType === ht.value ? 'selected' : ''}`}
              onClick={() => setHazardType(ht.value)}
            >
              <span className="hazard-icon">{ht.icon}</span>
              <span className="hazard-label">{ht.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label>Severity Level</label>
        <input
          type="range"
          min="0.1"
          max="1.0"
          step="0.1"
          value={severity}
          onChange={(e) => setSeverity(parseFloat(e.target.value))}
          className="severity-slider"
        />
        <div className="severity-label">
          {SEVERITY_LABELS.reduce((closest, label) =>
            Math.abs(label.value - severity) < Math.abs(closest.value - severity) ? label : closest
          ).label}
        </div>
      </div>

      <div className="form-group">
        <label>Description (optional)</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe what you see: water level, damage, people affected..."
          rows={3}
        />
      </div>

      <div className="form-group">
        <label>Photo (optional)</label>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handlePhoto}
          ref={fileInputRef}
          className="file-input"
        />
        {photo && <img src={photo} alt="Report photo" className="photo-preview" />}
      </div>

      <div className="form-group">
        <label>Location</label>
        <button type="button" className="btn-location" onClick={getLocation}>
          Get My Location
        </button>
        <span className="location-status">{locationStatus}</span>
      </div>

      <button type="submit" className="btn-submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit Report'}
      </button>
    </form>
  );
}

async function hashString(str) {
  const encoder = new TextEncoder();
  const data = encoder.encode(str);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}
