import React, { useState, useEffect } from "react";

export default function DetectionHistory({ userId, apiBaseUrl }) {
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  const fetchDetections = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${apiBaseUrl}/api/detections`, {
        headers: { "X-User-ID": userId },
      });
      if (resp.ok) {
        const data = await resp.json();
        setDetections(data.detections || []);
      } else {
        setError("Failed to load detection history.");
      }
    } catch (e) {
      setError("Cannot reach backend server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetections();
  }, [userId]);

  const handleDelete = async (id) => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/detections/${id}`, {
        method: "DELETE",
        headers: { "X-User-ID": userId },
      });
      if (resp.ok) {
        setDetections((prev) => prev.filter((d) => d.id !== id));
        setActionMsg("Detection record deleted.");
        setTimeout(() => setActionMsg(""), 2500);
      }
    } catch (e) {
      setError("Failed to delete detection record.");
    }
  };

  const handleClearAll = async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/detections`, {
        method: "DELETE",
        headers: { "X-User-ID": userId },
      });
      if (resp.ok) {
        setDetections([]);
        setShowClearConfirm(false);
        setActionMsg("All detection history cleared.");
        setTimeout(() => setActionMsg(""), 2500);
      }
    } catch (e) {
      setError("Failed to clear detection history.");
    }
  };

  return (
    <div className="history-screen" role="region" aria-label="Object Detection History">
      <div className="screen-header">
        <h2>🎯 Object Detection History</h2>
        <p className="screen-subtitle">Logged YOLOv8 obstacle and object observations</p>
      </div>

      <div className="privacy-card">
        <span className="privacy-note">
          🔒 <strong>Privacy Guaranteed:</strong> Only structured object names, confidence levels, and directions are stored. No camera images or video frames are ever uploaded or saved.
        </span>
      </div>

      {actionMsg && <div className="success-banner">{actionMsg}</div>}
      {error && <div className="error-badge">{error}</div>}

      <div className="history-toolbar">
        <span className="history-count">
          {detections.length} obstacle observation{detections.length === 1 ? "" : "s"} logged
        </span>
        <div className="toolbar-actions">
          <button className="query-btn" onClick={fetchDetections} disabled={loading}>
            🔄 Refresh
          </button>
          {detections.length > 0 && (
            <button
              className="control-btn stop-btn btn-sm"
              onClick={() => setShowClearConfirm(true)}
            >
              🗑️ Clear All Detections
            </button>
          )}
        </div>
      </div>

      {showClearConfirm && (
        <div className="confirm-dialog" role="dialog" aria-modal="true">
          <div className="confirm-box">
            <h3>Clear All Detection Records?</h3>
            <p>This will permanently erase all logged obstacle and object records from MongoDB.</p>
            <div className="confirm-buttons">
              <button className="control-btn stop-btn" onClick={handleClearAll}>
                Yes, Delete All
              </button>
              <button
                className="control-btn secondary-btn"
                onClick={() => setShowClearConfirm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-state">Loading detection history from MongoDB...</div>
      ) : detections.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">👁️</span>
          <h3>No Detection Records Logged Yet</h3>
          <p>Start the camera on Live Assistance to automatically log deduplicated obstacles.</p>
        </div>
      ) : (
        <div className="detections-history-grid">
          {detections.map((item) => (
            <div
              key={item.id}
              className={`detection-history-card zone-border-${(item.direction || "center").toLowerCase()}`}
            >
              <div className="det-card-top">
                <span className="det-card-name">
                  {item.label ? item.label.charAt(0).toUpperCase() + item.label.slice(1) : "Object"}
                </span>
                <button
                  className="delete-item-btn"
                  onClick={() => handleDelete(item.id)}
                  title="Delete record"
                  aria-label="Delete this detection record"
                >
                  ✕
                </button>
              </div>

              <div className="det-card-details">
                <span className={`zone-badge zone-${(item.direction || "center").toLowerCase()}`}>
                  {item.direction || "CENTER"}
                </span>
                <span className="conf-badge">
                  {(item.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>

              <div className="det-card-time">
                🕒 {item.timestamp ? new Date(item.timestamp).toLocaleString() : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
