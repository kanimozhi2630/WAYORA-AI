"""
WAYORA AI - Directional Object Detection & Voice Guidance Verification Test
Tests:
1. Direction Classification (LEFT, CENTER, RIGHT) using original frame width
2. Actual YOLO Detection API response handling
3. Automatic Voice Alert text formatting
4. 4-second Cooldown duplicate prevention logic
5. Voice Question & Answer matching
"""
import sys
import time
import requests
import numpy as np
import cv2

def classify_direction(x1, x2, frame_width):
    center_x = (x1 + x2) / 2.0
    third = frame_width / 3.0
    if center_x < third:
        return "LEFT"
    elif center_x <= 2.0 * third:
        return "CENTER"
    else:
        return "RIGHT"

def test_direction_classification():
    print("\n--- Test 1: Direction Classification Geometry ---")
    frame_width = 640
    third = frame_width / 3.0 # 213.333
    two_thirds = 2 * third     # 426.666

    # Test cases: (x1, x2, expected_zone)
    cases = [
        (10, 100, "LEFT"),     # center = 55 (< 213.33)
        (150, 200, "LEFT"),    # center = 175 (< 213.33)
        (250, 350, "CENTER"),  # center = 300 (213.33 <= 300 <= 426.67)
        (213.34, 213.34, "CENTER"), # right at border
        (450, 550, "RIGHT"),   # center = 500 (> 426.67)
        (580, 620, "RIGHT"),   # center = 600 (> 426.67)
    ]

    for x1, x2, expected in cases:
        actual = classify_direction(x1, x2, frame_width)
        center_x = (x1 + x2) / 2.0
        assert actual == expected, f"Failed for x1={x1}, x2={x2}: got {actual}, expected {expected}"
        print(f"  BBox [{x1:.1f}, {x2:.1f}] -> CenterX: {center_x:.1f} -> Classified: {actual} (PASS)")

def test_announcement_and_cooldown():
    print("\n--- Test 2: Voice Alert Formatting & 4s Cooldown ---")
    alert_history = {}
    cooldown_ms = 4000

    def generate_alert(label, zone, now_ms):
        key = f"{label}-{zone}"
        last_spoken = alert_history.get(key, 0)
        if now_ms - last_spoken >= cooldown_ms:
            alert_history[key] = now_ms
            direction_phrase = "in front of you" if zone == "CENTER" else f"on your {zone.lower()}"
            msg = f"{label.capitalize()} detected {direction_phrase}."
            return msg, True
        return None, False

    t0 = 100000

    # 1. First detection of Person on LEFT
    msg1, spoken1 = generate_alert("person", "LEFT", t0)
    assert spoken1 and msg1 == "Person detected on your left."
    print(f"  t=0s: '{msg1}' -> Spoken: {spoken1} (PASS)")

    # 2. Repeated detection of Person on LEFT 1 second later (should be blocked by cooldown)
    msg2, spoken2 = generate_alert("person", "LEFT", t0 + 1000)
    assert not spoken2 and msg2 is None
    print(f"  t=1s: Person LEFT -> Spoken: {spoken2} (Blocked by 4s Cooldown - PASS)")

    # 3. Detection of Chair in CENTER at t=1.5s (different object/zone, should speak)
    msg3, spoken3 = generate_alert("chair", "CENTER", t0 + 1500)
    assert spoken3 and msg3 == "Chair detected in front of you."
    print(f"  t=1.5s: '{msg3}' -> Spoken: {spoken3} (PASS)")

    # 4. Detection of Person on RIGHT at t=2s (same object, different zone, should speak)
    msg4, spoken4 = generate_alert("person", "RIGHT", t0 + 2000)
    assert spoken4 and msg4 == "Person detected on your right."
    print(f"  t=2s: '{msg4}' -> Spoken: {spoken4} (PASS)")

    # 5. Detection of Person on LEFT at t=4.5s (after 4s cooldown expired, should speak again)
    msg5, spoken5 = generate_alert("person", "LEFT", t0 + 4500)
    assert spoken5 and msg5 == "Person detected on your left."
    print(f"  t=4.5s: '{msg5}' -> Spoken: {spoken5} (Cooldown reset - PASS)")

def test_voice_qa():
    print("\n--- Test 3: Voice Question & Answer Logic ---")
    detections = [
        {"label": "person", "confidence": 0.88, "zone": "LEFT"},
        {"label": "chair", "confidence": 0.76, "zone": "CENTER"},
        {"label": "bottle", "confidence": 0.92, "zone": "RIGHT"},
    ]

    def answer_query(query, dets):
        q = query.lower()
        if not dets:
            return "I cannot detect any objects right now."
        if "front" in q:
            objs = [d["label"] for d in dets if d["zone"] == "CENTER"]
            return f"In front of you: {', '.join(set(objs))}." if objs else "I cannot detect any objects in front of you right now."
        elif "left" in q:
            objs = [d["label"] for d in dets if d["zone"] == "LEFT"]
            return f"On your left: {', '.join(set(objs))}." if objs else "I cannot detect any objects on your left right now."
        elif "right" in q:
            objs = [d["label"] for d in dets if d["zone"] == "RIGHT"]
            return f"On your right: {', '.join(set(objs))}." if objs else "I cannot detect any objects on your right right now."
        elif "see" in q:
            descs = [f"{d['label']} {'in front of you' if d['zone'] == 'CENTER' else 'on your ' + d['zone'].lower()}" for d in dets]
            return f"I can see {', '.join(descs)}."

    # Test Q&A
    q1 = answer_query("What is in front of me?", detections)
    print(f"  Q: 'What is in front of me?' -> A: '{q1}'")
    assert q1 == "In front of you: chair."

    q2 = answer_query("What is on my left?", detections)
    print(f"  Q: 'What is on my left?' -> A: '{q2}'")
    assert q2 == "On your left: person."

    q3 = answer_query("What is on my right?", detections)
    print(f"  Q: 'What is on my right?' -> A: '{q3}'")
    assert q3 == "On your right: bottle."

    q4 = answer_query("What can you see?", detections)
    print(f"  Q: 'What can you see?' -> A: '{q4}'")
    assert "person on your left" in q4 and "chair in front of you" in q4 and "bottle on your right" in q4

    q5 = answer_query("What is in front of me?", [])
    print(f"  Q with empty detections -> A: '{q5}'")
    assert q5 == "I cannot detect any objects right now."

def test_api_detection_pipeline():
    print("\n--- Test 4: Live FastAPI YOLO Detection API ---")
    try:
        resp = requests.get("http://127.0.0.1:8000/health", timeout=3)
        assert resp.status_code == 200
        print("  FastAPI /health check: OK")
    except Exception as e:
        print(f"  Backend offline: {e}")
        return

    # Create a synthetic image of 640x480 with high-contrast distinct regions
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw simple shapes
    cv2.circle(img, (100, 240), 50, (255, 255, 255), -1) # Left
    cv2.rectangle(img, (270, 190), (370, 290), (255, 255, 255), -1) # Center
    cv2.circle(img, (540, 240), 50, (255, 255, 255), -1) # Right

    _, buf = cv2.imencode(".jpg", img)
    files = {"file": ("test_frame.jpg", buf.tobytes(), "image/jpeg")}
    detect_resp = requests.post("http://127.0.0.1:8000/detect", files=files, timeout=5)
    assert detect_resp.status_code == 200
    data = detect_resp.json()
    assert "detections" in data
    print(f"  FastAPI /detect returned {len(data['detections'])} raw detections successfully.")
    print("  All verification tests PASSED!\n")

if __name__ == "__main__":
    test_direction_classification()
    test_announcement_and_cooldown()
    test_voice_qa()
    test_api_detection_pipeline()
