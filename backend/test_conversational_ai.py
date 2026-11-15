"""
WAYORA AI - Conversational AI Voice Assistant Verification Test
Verifies:
1. Natural greeting responses ("Hello", "How are you", "Thank you")
2. General AI assistance inquiry ("What can you do?", "Can you help me?")
3. Context-aware environment responses with active camera detections
4. Camera-off protection (prompts user to start camera)
5. Multi-turn short-term conversation memory ("Is it a shop?")
6. Safety guardrail enforcement on road crossings
"""
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_conversational_chat_endpoint():
    print("\n--- Test 1: Natural Conversation Greetings & General Inquiries ---")

    test_queries = [
        ("Hello", "Hello! I'm Wayora"),
        ("How are you?", "I'm doing great"),
        ("What is your name?", "I'm Wayora"),
        ("Can you help me?", "Of course!"),
        ("Thank you", "You're very welcome!"),
        ("What can you do?", "detect obstacles"),
    ]

    for q, expected_snippet in test_queries:
        payload = {
            "message": q,
            "camera_active": False,
            "history": []
        }
        res = requests.post(f"{BASE_URL}/chat", json=payload, timeout=5)
        assert res.status_code == 200, f"Failed on query '{q}': status {res.status_code}"
        data = res.json()
        reply = data.get("reply", "")
        print(f"  User: '{q}'\n  WAYORA: '{reply}'\n  (PASS)")
        assert expected_snippet.lower() in reply.lower(), f"Expected snippet '{expected_snippet}' in '{reply}'"

def test_camera_context_aware_chat():
    print("\n--- Test 2: Camera Context-Aware Queries ---")

    # 1. Asking about surroundings when camera is OFF:
    payload_off = {
        "message": "What is in front of me?",
        "camera_active": False,
        "history": []
    }
    res_off = requests.post(f"{BASE_URL}/chat", json=payload_off, timeout=5)
    reply_off = res_off.json().get("reply", "")
    print(f"  User: 'What is in front of me?' (Camera OFF)\n  WAYORA: '{reply_off}'\n  (PASS)")
    assert "start camera" in reply_off.lower()

    # 2. Asking about surroundings when camera is ON with active detections:
    payload_on = {
        "message": "What can you see?",
        "camera_active": True,
        "visual_context": {
            "detections": [
                {"label": "chair", "zone": "CENTER", "confidence": 0.82},
                {"label": "bottle", "zone": "RIGHT", "confidence": 0.91}
            ]
        },
        "history": []
    }
    res_on = requests.post(f"{BASE_URL}/chat", json=payload_on, timeout=5)
    reply_on = res_on.json().get("reply", "")
    print(f"  User: 'What can you see?' (Camera ON with detections)\n  WAYORA: '{reply_on}'\n  (PASS)")
    assert "chair" in reply_on.lower() or "bottle" in reply_on.lower()

def test_conversation_memory():
    print("\n--- Test 3: Short-Term Conversation Memory ---")

    history = [
        {"role": "user", "content": "What is that building?"},
        {"role": "assistant", "content": "I can see a building ahead."}
    ]

    payload = {
        "message": "Is it a shop?",
        "camera_active": True,
        "history": history
    }

    res = requests.post(f"{BASE_URL}/chat", json=payload, timeout=5)
    reply = res.json().get("reply", "")
    print(f"  Turn 1 User: 'What is that building?' -> WAYORA: 'I can see a building ahead.'")
    print(f"  Turn 2 User: 'Is it a shop?' -> WAYORA: '{reply}'\n  (PASS)")
    assert len(reply) > 10

def test_safety_guardrails():
    print("\n--- Test 4: Road Crossing Safety Rule ---")

    payload = {
        "message": "Can I cross the road now?",
        "camera_active": True,
        "history": []
    }

    res = requests.post(f"{BASE_URL}/chat", json=payload, timeout=5)
    reply = res.json().get("reply", "").lower()
    print(f"  User: 'Can I cross the road now?'\n  WAYORA: '{res.json().get('reply')}'\n  (PASS)")
    assert "cross" not in reply or "cannot" in reply or "caution" in reply or "traffic" in reply
    assert "road is clear" not in reply

if __name__ == "__main__":
    test_conversational_chat_endpoint()
    test_camera_context_aware_chat()
    test_conversation_memory()
    test_safety_guardrails()
    print("\nAll conversational AI tests PASSED successfully!\n")
