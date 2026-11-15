import React, { useState, useEffect } from "react";

export default function ConversationHistory({ userId, apiBaseUrl, consentSave, onToggleConsent }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  const fetchConversations = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${apiBaseUrl}/api/conversations`, {
        headers: { "X-User-ID": userId },
      });
      if (resp.ok) {
        const data = await resp.json();
        setConversations(data.conversations || []);
      } else {
        setError("Failed to load conversation history.");
      }
    } catch (e) {
      setError("Cannot reach backend server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [userId]);

  const handleDelete = async (id) => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/conversations/${id}`, {
        method: "DELETE",
        headers: { "X-User-ID": userId },
      });
      if (resp.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== id));
        setActionMsg("Conversation deleted.");
        setTimeout(() => setActionMsg(""), 2500);
      }
    } catch (e) {
      setError("Failed to delete record.");
    }
  };

  const handleClearAll = async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/conversations`, {
        method: "DELETE",
        headers: { "X-User-ID": userId },
      });
      if (resp.ok) {
        setConversations([]);
        setShowClearConfirm(false);
        setActionMsg("All conversation history cleared.");
        setTimeout(() => setActionMsg(""), 2500);
      }
    } catch (e) {
      setError("Failed to clear history.");
    }
  };

  // Group conversations by date (Newest first)
  const groupedConversations = conversations.reduce((groups, item) => {
    const date = item.date || (item.timestamp ? item.timestamp.split("T")[0] : "Recent");
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(item);
    return groups;
  }, {});

  return (
    <div className="history-screen" role="region" aria-label="Voice Conversation History">
      <div className="screen-header">
        <h2>💬 Voice Conversation History</h2>
        <p className="screen-subtitle">Your conversational dialogues with WAYORA AI</p>
      </div>

      {/* Privacy and Consent Controls */}
      <div className="privacy-card">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={consentSave}
            onChange={(e) => onToggleConsent(e.target.checked)}
          />
          <span className="toggle-text">
            <strong>Save Voice Conversations (User Consent)</strong>
            <small>Only text transcripts are stored for your session; no audio recordings are kept.</small>
          </span>
        </label>
      </div>

      {actionMsg && <div className="success-banner">{actionMsg}</div>}
      {error && <div className="error-badge">{error}</div>}

      {/* Action Toolbar */}
      <div className="history-toolbar">
        <span className="history-count">
          {conversations.length} conversation{conversations.length === 1 ? "" : "s"} logged
        </span>
        <div className="toolbar-actions">
          <button className="query-btn" onClick={fetchConversations} disabled={loading}>
            🔄 Refresh
          </button>
          {conversations.length > 0 && (
            <button
              className="control-btn stop-btn btn-sm"
              onClick={() => setShowClearConfirm(true)}
            >
              🗑️ Clear All History
            </button>
          )}
        </div>
      </div>

      {/* Clear All Confirmation Modal */}
      {showClearConfirm && (
        <div className="confirm-dialog" role="dialog" aria-modal="true">
          <div className="confirm-box">
            <h3>Clear All Conversation History?</h3>
            <p>This will permanently delete all your stored voice conversation records from MongoDB.</p>
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

      {/* Conversation List Grouped by Date */}
      {loading ? (
        <div className="loading-state">Loading history from MongoDB...</div>
      ) : conversations.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">💭</span>
          <h3>No Conversation History Yet</h3>
          <p>Talk with WAYORA using voice on the Live Assistance tab to see conversations here.</p>
        </div>
      ) : (
        <div className="grouped-history-list">
          {Object.entries(groupedConversations).map(([date, items]) => (
            <div key={date} className="date-group">
              <div className="date-header">📅 {date}</div>
              <div className="cards-list">
                {items.map((item) => (
                  <div key={item.id} className="conversation-card">
                    <div className="card-header">
                      <span className="timestamp">
                        🕒 {item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : ""}
                      </span>
                      <button
                        className="delete-item-btn"
                        onClick={() => handleDelete(item.id)}
                        title="Delete conversation"
                        aria-label="Delete this conversation"
                      >
                        ✕
                      </button>
                    </div>
                    <div className="dialogue-flow">
                      <div className="user-line">
                        <span className="speaker-tag user-tag">You:</span> {item.question}
                      </div>
                      <div className="assistant-line">
                        <span className="speaker-tag ai-tag">WAYORA:</span> {item.response}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
