import React, { useState, useEffect } from "react";

export default function VoiceSettings({
  userId,
  apiBaseUrl,
  currentSettings,
  onSettingsSaved,
  onTestVoice,
}) {
  const [settings, setSettings] = useState(currentSettings);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [dbStatus, setDbStatus] = useState(null);

  // Load real browser voices dynamically
  useEffect(() => {
    const updateVoices = () => {
      if (window.speechSynthesis) {
        const voices = window.speechSynthesis.getVoices();
        setAvailableVoices(voices);
      }
    };

    updateVoices();
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
  }, []);

  // Fetch persisted settings from MongoDB
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const resp = await fetch(`${apiBaseUrl}/api/settings`, {
          headers: { "X-User-ID": userId },
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.settings) {
            setSettings(data.settings);
            onSettingsSaved(data.settings);
          }
        }
      } catch (e) {
        console.warn("Could not fetch settings from backend:", e);
      }
    };

    const fetchDbStatus = async () => {
      try {
        const resp = await fetch(`${apiBaseUrl}/api/db-status`);
        if (resp.ok) {
          const data = await resp.json();
          setDbStatus(data);
        }
      } catch (e) {
        setDbStatus({ connected: false, message: "Backend offline" });
      }
    };

    fetchSettings();
    fetchDbStatus();
  }, [userId, apiBaseUrl]);

  const handleChange = (field, value) => {
    setSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveMessage("");

    try {
      const resp = await fetch(`${apiBaseUrl}/api/settings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId,
        },
        body: JSON.stringify(settings),
      });

      if (resp.ok) {
        const data = await resp.json();
        onSettingsSaved(data.settings);
        setSaveMessage("✅ Preferences saved successfully to MongoDB!");
        setTimeout(() => setSaveMessage(""), 3500);
      } else {
        setSaveMessage("⚠️ Could not save settings to database.");
      }
    } catch (err) {
      setSaveMessage("⚠️ Network error while saving preferences.");
    } finally {
      setSaving(false);
    }
  };

  const handleSampleVoice = () => {
    onTestVoice(settings);
  };

  return (
    <div className="settings-screen" role="region" aria-label="Voice & Guidance Settings">
      <div className="screen-header">
        <h2>⚙️ Voice & Guidance Settings</h2>
        <p className="screen-subtitle">Customize voice speed, pitch, alert frequency, and privacy</p>
      </div>

      {/* MongoDB Connection Status Pill */}
      {dbStatus && (
        <div className={`db-status-pill ${dbStatus.connected ? "db-online" : "db-fallback"}`}>
          <span className="status-indicator"></span>
          <span>
            <strong>Storage:</strong> {dbStatus.message}
            {dbStatus.connected && dbStatus.masked_uri && ` (${dbStatus.masked_uri})`}
          </span>
        </div>
      )}

      {saveMessage && <div className="success-banner">{saveMessage}</div>}

      <form onSubmit={handleSave} className="settings-form">
        {/* Voice Selection */}
        <div className="form-group">
          <label htmlFor="voice-select">
            <strong>Synthesizer Voice:</strong>
            <small>Populated from currently available browser voices</small>
          </label>
          <select
            id="voice-select"
            className="form-control"
            value={settings.voice_name || ""}
            onChange={(e) => handleChange("voice_name", e.target.value)}
          >
            <option value="">Default System Voice</option>
            {availableVoices.map((v, i) => (
              <option key={i} value={v.name}>
                {v.name} ({v.lang})
              </option>
            ))}
          </select>
        </div>

        {/* Speech Rate Slider */}
        <div className="form-group">
          <div className="slider-header">
            <label htmlFor="rate-slider">
              <strong>Speech Rate:</strong>
            </label>
            <span className="slider-value">{settings.speech_rate || 1.0}x</span>
          </div>
          <input
            id="rate-slider"
            type="range"
            min="0.5"
            max="1.8"
            step="0.1"
            className="range-slider"
            value={settings.speech_rate || 1.0}
            onChange={(e) => handleChange("speech_rate", parseFloat(e.target.value))}
          />
          <div className="slider-labels">
            <span>0.5x (Slow)</span>
            <span>1.0x (Normal)</span>
            <span>1.8x (Fast)</span>
          </div>
        </div>

        {/* Speech Pitch Slider */}
        <div className="form-group">
          <div className="slider-header">
            <label htmlFor="pitch-slider">
              <strong>Voice Pitch:</strong>
            </label>
            <span className="slider-value">{settings.speech_pitch || 1.0}</span>
          </div>
          <input
            id="pitch-slider"
            type="range"
            min="0.6"
            max="1.5"
            step="0.1"
            className="range-slider"
            value={settings.speech_pitch || 1.0}
            onChange={(e) => handleChange("speech_pitch", parseFloat(e.target.value))}
          />
          <div className="slider-labels">
            <span>0.6 (Lower)</span>
            <span>1.0 (Normal)</span>
            <span>1.5 (Higher)</span>
          </div>
        </div>

        {/* Alert Frequency */}
        <div className="form-group">
          <label htmlFor="frequency-select">
            <strong>Directional Alert Cooldown:</strong>
            <small>Minimum delay between repeating the same obstacle alert</small>
          </label>
          <select
            id="frequency-select"
            className="form-control"
            value={settings.alert_frequency || 4000}
            onChange={(e) => handleChange("alert_frequency", parseInt(e.target.value, 10))}
          >
            <option value={2000}>2 seconds (Frequent)</option>
            <option value={4000}>4 seconds (Balanced - Recommended)</option>
            <option value={6000}>6 seconds (Quiet)</option>
          </select>
        </div>

        {/* Toggles */}
        <div className="form-group checkbox-group">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={settings.alerts_muted || false}
              onChange={(e) => handleChange("alerts_muted", e.target.checked)}
            />
            <span className="toggle-text">
              <strong>Mute Background Automatic Voice Alerts</strong>
              <small>When muted, alerts will show on-screen without speaking aloud.</small>
            </span>
          </label>
        </div>

        <div className="form-group checkbox-group">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={settings.consent_save_history !== false}
              onChange={(e) => handleChange("consent_save_history", e.target.checked)}
            />
            <span className="toggle-text">
              <strong>Save Conversation History (User Consent)</strong>
              <small>Permit storing your voice question & answer transcripts in MongoDB.</small>
            </span>
          </label>
        </div>

        {/* Form Action Buttons */}
        <div className="settings-actions">
          <button
            type="button"
            className="control-btn secondary-btn"
            onClick={handleSampleVoice}
          >
            🔊 Test Voice
          </button>
          <button type="submit" className="control-btn primary-btn" disabled={saving}>
            {saving ? "Saving..." : "💾 Save Preferences"}
          </button>
        </div>
      </form>
    </div>
  );
}
