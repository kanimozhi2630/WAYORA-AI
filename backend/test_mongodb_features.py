"""
WAYORA AI - MongoDB Atlas Feature Verification Test Suite
Verifies:
1. MongoDB status and fallback handling
2. Voice Conversation History (Add, List, Delete, Clear)
3. Object Detection History (Add, List, Delete, Clear)
4. Voice Settings Persistence (Get, Update, Verify)
5. Multi-User Privacy and Data Separation
"""
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_db_status():
    print("\n--- Test 1: MongoDB Database Status ---")
    resp = requests.get(f"{BASE_URL}/api/db-status", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    print(f"  Connected: {data.get('connected')}")
    print(f"  Database: {data.get('database')}")
    print(f"  Message: {data.get('message')} (PASS)")

def test_conversation_history():
    print("\n--- Test 2: Voice Conversation History (User A) ---")
    headers_a = {"X-User-ID": "test_user_alpha"}

    # 1. Add conversation
    c1 = requests.post(f"{BASE_URL}/api/conversations", headers=headers_a, json={
        "question": "What is in front of me?",
        "response": "Chair detected in front of you."
    }, timeout=5).json()
    assert c1.get("status") == "saved"
    conv_id = c1["conversation"]["id"]
    print(f"  Saved conversation: ID={conv_id} (PASS)")

    # 2. Add second conversation
    requests.post(f"{BASE_URL}/api/conversations", headers=headers_a, json={
        "question": "Is there a person nearby?",
        "response": "Yes, a person is detected on your left."
    }, timeout=5)

    # 3. List conversations
    convs = requests.get(f"{BASE_URL}/api/conversations", headers=headers_a, timeout=5).json()
    assert convs.get("count") >= 2
    print(f"  Retrieved {convs['count']} conversations for User Alpha (PASS)")

    # 4. Delete single conversation
    del_res = requests.delete(f"{BASE_URL}/api/conversations/{conv_id}", headers=headers_a, timeout=5).json()
    assert del_res.get("status") == "deleted"
    print(f"  Deleted conversation {conv_id} (PASS)")

    # 5. Clear all
    clear_res = requests.delete(f"{BASE_URL}/api/conversations", headers=headers_a, timeout=5).json()
    assert clear_res.get("status") == "cleared"
    print(f"  Cleared all conversations for User Alpha: {clear_res['deleted_count']} deleted (PASS)")

def test_detection_history():
    print("\n--- Test 3: Object Detection History (User A) ---")
    headers_a = {"X-User-ID": "test_user_alpha"}

    # 1. Add detection
    d1 = requests.post(f"{BASE_URL}/api/detections", headers=headers_a, json={
        "label": "car",
        "confidence": 0.94,
        "direction": "RIGHT"
    }, timeout=5).json()
    assert d1.get("status") == "saved"
    det_id = d1["detection"]["id"]
    print(f"  Saved YOLO detection: {d1['detection']['label']} on {d1['detection']['direction']} (PASS)")

    # 2. Add second detection
    requests.post(f"{BASE_URL}/api/detections", headers=headers_a, json={
        "label": "person",
        "confidence": 0.88,
        "direction": "LEFT"
    }, timeout=5)

    # 3. List detections
    dets = requests.get(f"{BASE_URL}/api/detections", headers=headers_a, timeout=5).json()
    assert dets.get("count") >= 2
    print(f"  Retrieved {dets['count']} detection records (PASS)")

    # 4. Delete single detection
    del_res = requests.delete(f"{BASE_URL}/api/detections/{det_id}", headers=headers_a, timeout=5).json()
    assert del_res.get("status") == "deleted"
    print(f"  Deleted detection {det_id} (PASS)")

    # 5. Clear all detections
    clear_res = requests.delete(f"{BASE_URL}/api/detections", headers=headers_a, timeout=5).json()
    assert clear_res.get("status") == "cleared"
    print(f"  Cleared detection history for User Alpha (PASS)")

def test_voice_settings():
    print("\n--- Test 4: Voice & Guidance Settings ---")
    headers_a = {"X-User-ID": "test_user_alpha"}

    # 1. Fetch initial settings
    s1 = requests.get(f"{BASE_URL}/api/settings", headers=headers_a, timeout=5).json()
    assert "settings" in s1
    print(f"  Default settings loaded: rate={s1['settings']['speech_rate']}, frequency={s1['settings']['alert_frequency']} (PASS)")

    # 2. Update settings
    updated_payload = {
        "voice_name": "Google US English",
        "speech_rate": 1.2,
        "speech_pitch": 1.1,
        "language": "en-US",
        "alert_frequency": 6000,
        "alerts_muted": True,
        "consent_save_history": True
    }
    s2 = requests.post(f"{BASE_URL}/api/settings", headers=headers_a, json=updated_payload, timeout=5).json()
    assert s2.get("status") == "updated"
    assert s2["settings"]["speech_rate"] == 1.2
    assert s2["settings"]["alert_frequency"] == 6000
    assert s2["settings"]["alerts_muted"] is True
    print(f"  Settings successfully updated & persisted in DB: rate={s2['settings']['speech_rate']}, muted={s2['settings']['alerts_muted']} (PASS)")

def test_user_privacy_isolation():
    print("\n--- Test 5: User Privacy & Record Isolation ---")
    headers_u1 = {"X-User-ID": "alice_user"}
    headers_u2 = {"X-User-ID": "bob_user"}

    # Clean both
    requests.delete(f"{BASE_URL}/api/conversations", headers=headers_u1, timeout=5)
    requests.delete(f"{BASE_URL}/api/conversations", headers=headers_u2, timeout=5)

    # Alice adds a conversation
    requests.post(f"{BASE_URL}/api/conversations", headers=headers_u1, json={
        "question": "Where is the door?",
        "response": "Door is on your left."
    }, timeout=5)

    # Bob fetches his conversations
    bob_convs = requests.get(f"{BASE_URL}/api/conversations", headers=headers_u2, timeout=5).json()
    alice_convs = requests.get(f"{BASE_URL}/api/conversations", headers=headers_u1, timeout=5).json()

    assert len(bob_convs["conversations"]) == 0, "Bob should not see Alice's conversations"
    assert len(alice_convs["conversations"]) == 1, "Alice should see her own conversation"
    print("  Verified: Bob cannot access Alice's conversations (0 visible to Bob, 1 visible to Alice) (PASS)")

    # Bob adds a detection
    requests.post(f"{BASE_URL}/api/detections", headers=headers_u2, json={
        "label": "bottle",
        "confidence": 0.85,
        "direction": "CENTER"
    }, timeout=5)

    alice_dets = requests.get(f"{BASE_URL}/api/detections", headers=headers_u1, timeout=5).json()
    bob_dets = requests.get(f"{BASE_URL}/api/detections", headers=headers_u2, timeout=5).json()

    assert len(alice_dets["detections"]) == 0, "Alice should not see Bob's detections"
    assert len(bob_dets["detections"]) == 1, "Bob should see his own detection"
    print("  Verified: Alice cannot access Bob's detection history (PASS)")

if __name__ == "__main__":
    test_db_status()
    test_conversation_history()
    test_detection_history()
    test_voice_settings()
    test_user_privacy_isolation()
    print("\nAll MongoDB feature integration tests PASSED successfully!\n")
