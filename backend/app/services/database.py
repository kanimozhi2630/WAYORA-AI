import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Explicitly search and load .env from backend and root directories
current_dir = Path(__file__).resolve().parent
backend_env = Path(__file__).resolve().parents[2] / ".env"
root_env = Path(__file__).resolve().parents[3] / ".env"

env_loaded_from = None
if backend_env.exists():
    load_dotenv(backend_env, override=True)
    env_loaded_from = str(backend_env)
elif root_env.exists():
    load_dotenv(root_env, override=True)
    env_loaded_from = str(root_env)
else:
    load_dotenv()

logger = logging.getLogger("uvicorn.error")

# Fallback in-memory storage for when MongoDB Atlas is firewalled or temporarily offline
in_memory_db = {
    "conversations": [],
    "detections": [],
    "settings": {}
}

mongo_client = None
mongo_db = None
is_mongo_connected = False
last_connection_error = None

def init_mongo():
    global mongo_client, mongo_db, is_mongo_connected, last_connection_error
    uri = os.getenv("MONGODB_URI")
    if not uri:
        logger.info("MONGODB_URI not configured. Operating in resilient fallback mode.")
        is_mongo_connected = False
        last_connection_error = "MONGODB_URI is not set in .env"
        return

    try:
        from pymongo import MongoClient
        import certifi

        # Connect with certifi CA bundle and 4s timeout so startup is smooth
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000,
            tlsCAFile=certifi.where()
        )
        # Test connection
        client.admin.command('ping')
        mongo_client = client
        try:
            mongo_db = client.get_default_database()
        except Exception:
            mongo_db = client.get_database("detect-system")
        is_mongo_connected = True
        last_connection_error = None
        logger.info(f"Successfully connected to MongoDB Atlas database '{mongo_db.name}'!")
    except Exception as e:
        last_connection_error = str(e)
        logger.warning(f"Could not connect to MongoDB Atlas ({e}). Operating in resilient fallback mode.")
        is_mongo_connected = False

# Try initializing on module load
init_mongo()

def get_db_status() -> Dict[str, Any]:
    global is_mongo_connected, last_connection_error
    uri = os.getenv("MONGODB_URI")
    masked_uri = None
    if uri:
        # Mask password for security
        parts = uri.split("@")
        masked_uri = "mongodb+srv://****@" + parts[-1] if len(parts) > 1 else "configured"
    
    return {
        "connected": is_mongo_connected,
        "configured": bool(uri),
        "env_file_loaded": bool(backend_env.exists() or root_env.exists()),
        "env_path": env_loaded_from or "system_environment",
        "database": mongo_db.name if is_mongo_connected and mongo_db is not None else "in_memory_fallback",
        "masked_uri": masked_uri,
        "last_error": last_connection_error,
        "message": (
            "Connected to MongoDB Atlas"
            if is_mongo_connected
            else (
                "Atlas IP Access List required (whitelist 0.0.0.0/0 in MongoDB Atlas -> Network Access). Safe fallback storage is active."
                if uri
                else "Using safe fallback storage (Set MONGODB_URI in .env)"
            )
        )
    }

# ==========================================
# 1. Voice Conversation History Operations
# ==========================================

def save_conversation(user_id: str, question: str, response: str) -> Dict[str, Any]:
    now = datetime.utcnow()
    item = {
        "user_id": user_id,
        "question": question,
        "response": response,
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
    }
    
    if is_mongo_connected and mongo_db is not None:
        try:
            res = mongo_db.conversations.insert_one(item)
            item["id"] = str(res.inserted_id)
            if "_id" in item:
                del item["_id"]
            return item
        except Exception as e:
            logger.error(f"MongoDB save_conversation error: {e}")

    # Fallback storage
    import uuid
    item["id"] = str(uuid.uuid4())
    in_memory_db["conversations"].append(item)
    return item

def get_conversations(user_id: str) -> List[Dict[str, Any]]:
    if is_mongo_connected and mongo_db is not None:
        try:
            cursor = mongo_db.conversations.find({"user_id": user_id}).sort("timestamp", -1).limit(100)
            results = []
            for doc in cursor:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"MongoDB get_conversations error: {e}")

    # Fallback
    user_convs = [c for c in in_memory_db["conversations"] if c["user_id"] == user_id]
    return sorted(user_convs, key=lambda x: x["timestamp"], reverse=True)

def delete_conversation(user_id: str, conv_id: str) -> bool:
    if is_mongo_connected and mongo_db is not None:
        try:
            from bson import ObjectId
            try:
                oid = ObjectId(conv_id)
                res = mongo_db.conversations.delete_one({"_id": oid, "user_id": user_id})
                return res.deleted_count > 0
            except Exception:
                res = mongo_db.conversations.delete_one({"id": conv_id, "user_id": user_id})
                return res.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDB delete_conversation error: {e}")

    # Fallback
    initial_len = len(in_memory_db["conversations"])
    in_memory_db["conversations"] = [
        c for c in in_memory_db["conversations"]
        if not (c.get("id") == conv_id and c["user_id"] == user_id)
    ]
    return len(in_memory_db["conversations"]) < initial_len

def clear_conversations(user_id: str) -> int:
    if is_mongo_connected and mongo_db is not None:
        try:
            res = mongo_db.conversations.delete_many({"user_id": user_id})
            return res.deleted_count
        except Exception as e:
            logger.error(f"MongoDB clear_conversations error: {e}")

    # Fallback
    before = len(in_memory_db["conversations"])
    in_memory_db["conversations"] = [c for c in in_memory_db["conversations"] if c["user_id"] != user_id]
    return before - len(in_memory_db["conversations"])

# ==========================================
# 2. Object Detection History Operations
# ==========================================

def save_detection(user_id: str, label: str, confidence: float, direction: str) -> Dict[str, Any]:
    now = datetime.utcnow()
    item = {
        "user_id": user_id,
        "label": label,
        "confidence": round(float(confidence), 2),
        "direction": direction.upper(),
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
    }

    if is_mongo_connected and mongo_db is not None:
        try:
            res = mongo_db.detections.insert_one(item)
            item["id"] = str(res.inserted_id)
            if "_id" in item:
                del item["_id"]
            return item
        except Exception as e:
            logger.error(f"MongoDB save_detection error: {e}")

    import uuid
    item["id"] = str(uuid.uuid4())
    in_memory_db["detections"].append(item)
    return item

def get_detections(user_id: str) -> List[Dict[str, Any]]:
    if is_mongo_connected and mongo_db is not None:
        try:
            cursor = mongo_db.detections.find({"user_id": user_id}).sort("timestamp", -1).limit(100)
            results = []
            for doc in cursor:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"MongoDB get_detections error: {e}")

    user_dets = [d for d in in_memory_db["detections"] if d["user_id"] == user_id]
    return sorted(user_dets, key=lambda x: x["timestamp"], reverse=True)

def delete_detection(user_id: str, det_id: str) -> bool:
    if is_mongo_connected and mongo_db is not None:
        try:
            from bson import ObjectId
            try:
                oid = ObjectId(det_id)
                res = mongo_db.detections.delete_one({"_id": oid, "user_id": user_id})
                return res.deleted_count > 0
            except Exception:
                res = mongo_db.detections.delete_one({"id": det_id, "user_id": user_id})
                return res.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDB delete_detection error: {e}")

    initial_len = len(in_memory_db["detections"])
    in_memory_db["detections"] = [
        d for d in in_memory_db["detections"]
        if not (d.get("id") == det_id and d["user_id"] == user_id)
    ]
    return len(in_memory_db["detections"]) < initial_len

def clear_detections(user_id: str) -> int:
    if is_mongo_connected and mongo_db is not None:
        try:
            res = mongo_db.detections.delete_many({"user_id": user_id})
            return res.deleted_count
        except Exception as e:
            logger.error(f"MongoDB clear_detections error: {e}")

    before = len(in_memory_db["detections"])
    in_memory_db["detections"] = [d for d in in_memory_db["detections"] if d["user_id"] != user_id]
    return before - len(in_memory_db["detections"])

# ==========================================
# 3. Voice Settings Preferences Operations
# ==========================================

DEFAULT_SETTINGS = {
    "voice_name": "",
    "speech_rate": 1.0,
    "speech_pitch": 1.0,
    "language": "en-US",
    "alert_frequency": 4000,
    "alerts_muted": False,
    "consent_save_history": True,
}

def get_user_settings(user_id: str) -> Dict[str, Any]:
    if is_mongo_connected and mongo_db is not None:
        try:
            doc = mongo_db.voice_settings.find_one({"user_id": user_id})
            if doc:
                if "_id" in doc:
                    del doc["_id"]
                return doc
        except Exception as e:
            logger.error(f"MongoDB get_user_settings error: {e}")

    return in_memory_db["settings"].get(user_id, {"user_id": user_id, **DEFAULT_SETTINGS})

def save_user_settings(user_id: str, settings_data: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**DEFAULT_SETTINGS, **settings_data, "user_id": user_id, "updated_at": datetime.utcnow().isoformat()}

    if is_mongo_connected and mongo_db is not None:
        try:
            mongo_db.voice_settings.update_one(
                {"user_id": user_id},
                {"$set": merged},
                upsert=True
            )
            return merged
        except Exception as e:
            logger.error(f"MongoDB save_user_settings error: {e}")

    in_memory_db["settings"][user_id] = merged
    return merged
