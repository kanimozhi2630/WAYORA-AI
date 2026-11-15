import os
import httpx
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    camera_active: bool = False
    visual_context: Optional[Dict[str, Any]] = None

SYSTEM_PROMPT = """You are WAYORA, an intelligent AI walking companion and environmental awareness assistant designed to empower visually impaired individuals.
Key Personality & Principles:
- Warm, polite, concise, and helpful.
- Keep spoken responses short and direct (1 to 2 sentences ideally) because responses are spoken aloud via Text-to-Speech to a user who is walking.
- When the user asks general questions ("hello", "how are you", "who are you", "can you help me", "what can you do"), respond naturally, empathetically, and conversationally.
- When answering about the environment, rely STRICTLY on the provided visual context from the camera. Never fabricate objects, shop names, or surroundings.
- If the camera is stopped and the user asks what is around them, remind them to say "start camera" or tap Start Camera.
- CRITICAL SAFETY: NEVER state "the road is clear", "no vehicles are coming", "you can cross safely", or "go ahead and cross". A phone camera cannot verify safe road crossings. Remind users to use caution, pedestrian audio signals, and standard mobility aids.
"""

def generate_local_conversational_response(message: str, history: List[ChatMessage], camera_active: bool, visual_context: Optional[Dict[str, Any]]) -> str:
    """Intelligent fallback conversational generator when no external API key is configured."""
    msg = message.lower().strip()

    # Greetings
    if any(w in msg for w in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
        return "Hello! I'm Wayora, your intelligent walking companion. How can I help you today?"

    # Well-being
    if "how are you" in msg or "how's it going" in msg:
        return "I'm doing great and ready to assist you! How can I help you navigate right now?"

    # Identity
    if "your name" in msg or "who are you" in msg:
        return "I'm Wayora, an AI-powered walking companion designed to assist with object detection, environmental awareness, and directional guidance."

    # Help inquiry
    if "can you help" in msg or "help me" in msg:
        return "Of course! I can guide you by detecting obstacles, announcing approaching vehicles, reading signboards, and describing your surroundings."

    # Capabilities
    if "what can you do" in msg or "features" in msg or "abilities" in msg:
        return "I can detect obstacles and people, track approaching vehicles, provide left and right directional guidance, read signboards, and describe your surroundings."

    # Gratitude
    if "thank" in msg:
        return "You're very welcome! I'm always here to assist you."

    # Environment questions when camera is off
    if not camera_active and any(w in msg for w in ["see", "front", "left", "right", "around", "shop", "building", "person", "vehicle"]):
        return "The camera is currently stopped. Please say 'start camera' or press Start Camera so I can observe your surroundings."

    # Follow-up reference handling with history
    if history and len(history) > 0:
        last_turn = history[-1].content.lower()
        if "it" in msg or "that" in msg:
            if "building" in last_turn and "shop" in msg:
                return "Based on the camera feed, I can see a structure ahead. You can ask me to read the signboard to check if it's a specific shop."

    # Environment questions with visual context
    if visual_context:
        detections = visual_context.get("detections", [])
        if any(w in msg for w in ["what do you see", "what can you see", "look"]):
            if detections:
                items = [f"{d['label']} on your {d.get('zone', 'path').lower()}" for d in detections[:3]]
                return f"I can see {', '.join(items)}."
            else:
                return "I don't detect any immediate obstacles in front of the camera right now."

    # General fallback
    return (
        "I understand! I'm here as your walking companion. You can ask me what is around you, "
        "have me read signboards, or ask about obstacles in front of you."
    )

async def handle_chat_message(request: ChatRequest) -> Dict[str, Any]:
    """Process natural language conversational interaction via Gemini or intelligent local engine."""
    user_msg = request.message.strip()
    gemini_key = os.getenv("GEMINI_API_KEY")

    if gemini_key:
        try:
            # Build conversation contents for Gemini
            contents = []

            # Include visual context in system preamble if camera active
            context_note = ""
            if request.camera_active and request.visual_context:
                dets = request.visual_context.get("detections", [])
                det_summary = ", ".join([f"{d['label']} in {d.get('zone', 'center')} (confidence: {d.get('confidence', 0):.2f})" for d in dets])
                context_note = f"\n[Active Camera Context: Camera is ON. Currently detected objects: {det_summary or 'None'}]."
            elif not request.camera_active:
                context_note = "\n[Active Camera Context: Camera is OFF. If user asks about physical surroundings, tell them to start camera]."

            # Build history turns
            for h in request.history[-6:]:
                role = "user" if h.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": h.content}]})

            # Append current user prompt with system prompt context
            full_prompt = f"{SYSTEM_PROMPT}{context_note}\n\nUser: {user_msg}"
            contents.append({"role": "user", "parts": [{"text": full_prompt}]})

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 150,
                }
            }

            async with httpx.AsyncClient(timeout=4.5) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    ai_reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return {
                        "reply": ai_reply,
                        "source": "gemini_model",
                        "model": "gemini-2.0-flash"
                    }
        except Exception as e:
            # Fall back to local conversational engine seamlessly
            pass

    # Use local conversational engine
    local_reply = generate_local_conversational_response(
        user_msg,
        request.history or [],
        request.camera_active,
        request.visual_context
    )

    return {
        "reply": local_reply,
        "source": "local_companion_engine",
        "api_key_configured": bool(gemini_key),
        "note": "To enable Gemini 2.0 conversational AI, set GEMINI_API_KEY in backend/.env" if not gemini_key else ""
    }
