from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import uvicorn

from .services.detect import detect_image
from .services.scene import describe_scene
from .services.ocr import read_signboard
from .services.chat import ChatRequest, handle_chat_message
from .services import database as db

app = FastAPI(title="WAYORA AI Backend - Intelligent Walking Companion with MongoDB")

origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn.error")

def get_current_user(x_user_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """Extract and validate the unique user identity for data isolation."""
    if isinstance(x_user_id, str) and x_user_id.strip():
        return x_user_id.strip()
    if isinstance(user_id, str) and user_id.strip():
        return user_id.strip()
    return "default_user"

# ==========================================
# Core Perception & Health Endpoints
# ==========================================

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "WAYORA AI Backend"}

@app.get("/api/db-status")
async def db_status():
    """Get MongoDB Atlas connection status."""
    return db.get_db_status()

@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    """Real-time YOLOv8 object detection endpoint."""
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        detections = detect_image(contents)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scene")
async def scene(file: UploadFile = File(...)):
    """Scene understanding and environment description endpoint."""
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        scene_info = await describe_scene(contents)
        return scene_info
    except Exception as e:
        logger.error(f"Scene understanding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    """Signboard and text reading endpoint."""
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        ocr_info = await read_signboard(contents)
        return ocr_info
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, x_user_id: Optional[str] = Header(None)):
    """Conversational natural AI voice interaction endpoint."""
    try:
        response = await handle_chat_message(request)
        uid = get_current_user(x_user_id)
        # Check user consent before storing conversation text
        user_settings = db.get_user_settings(uid)
        if user_settings.get("consent_save_history", True):
            db.save_conversation(uid, request.message, response.get("reply", ""))
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# Feature 1: Voice Conversation History API
# ==========================================

class SaveConversationRequest(BaseModel):
    question: str
    response: str

@app.get("/api/conversations")
async def get_conversations(x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    items = db.get_conversations(uid)
    return {"conversations": items, "count": len(items)}

@app.post("/api/conversations")
async def add_conversation(req: SaveConversationRequest, x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    saved = db.save_conversation(uid, req.question, req.response)
    return {"status": "saved", "conversation": saved}

@app.delete("/api/conversations/{conv_id}")
async def delete_single_conversation(conv_id: str, x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    success = db.delete_conversation(uid, conv_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation record not found")
    return {"status": "deleted", "id": conv_id}

@app.delete("/api/conversations")
async def clear_all_conversations(x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    deleted_count = db.clear_conversations(uid)
    return {"status": "cleared", "deleted_count": deleted_count}

# ==========================================
# Feature 2: Object Detection History API
# ==========================================

class SaveDetectionRequest(BaseModel):
    label: str
    confidence: float
    direction: str

@app.get("/api/detections")
async def get_detections(x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    items = db.get_detections(uid)
    return {"detections": items, "count": len(items)}

@app.post("/api/detections")
async def add_detection(req: SaveDetectionRequest, x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    saved = db.save_detection(uid, req.label, req.confidence, req.direction)
    return {"status": "saved", "detection": saved}

@app.delete("/api/detections/{det_id}")
async def delete_single_detection(det_id: str, x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    success = db.delete_detection(uid, det_id)
    if not success:
        raise HTTPException(status_code=404, detail="Detection record not found")
    return {"status": "deleted", "id": det_id}

@app.delete("/api/detections")
async def clear_all_detections(x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    deleted_count = db.clear_detections(uid)
    return {"status": "cleared", "deleted_count": deleted_count}

# ==========================================
# Feature 3: Voice Settings Preferences API
# ==========================================

class VoiceSettingsRequest(BaseModel):
    voice_name: Optional[str] = ""
    speech_rate: Optional[float] = 1.0
    speech_pitch: Optional[float] = 1.0
    language: Optional[str] = "en-US"
    alert_frequency: Optional[int] = 4000
    alerts_muted: Optional[bool] = False
    consent_save_history: Optional[bool] = True

@app.get("/api/settings")
async def get_settings(x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    settings = db.get_user_settings(uid)
    return {"settings": settings}

@app.post("/api/settings")
async def update_settings(req: VoiceSettingsRequest, x_user_id: Optional[str] = Header(None), user_id: Optional[str] = Query(None)):
    uid = get_current_user(x_user_id, user_id)
    updated = db.save_user_settings(uid, req.dict())
    return {"status": "updated", "settings": updated}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
