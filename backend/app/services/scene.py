import os
import cv2
import numpy as np
import httpx
from dotenv import load_dotenv
from .detect import detect_image

load_dotenv()

def analyze_scene_heuristics(img_bgr, detections):
    """Analyze image using computer vision and YOLO detections to describe the scene."""
    height, width = img_bgr.shape[:2]
    total_area = width * height

    # 1. Color and lighting analysis
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    brightness = np.mean(hsv[:, :, 2])
    if brightness < 35:
        return "The environment is very dark. I cannot identify the surroundings clearly right now."

    # Analyze upper third for sky/outdoor lighting
    upper_third = hsv[:int(height * 0.35), :]
    # Sky detection (blue/cyan hues or bright uniform overcast)
    blue_sky_mask = cv2.inRange(upper_third, np.array([90, 50, 70]), np.array([130, 255, 255]))
    bright_sky_mask = cv2.inRange(upper_third, np.array([0, 0, 180]), np.array([180, 40, 255]))
    sky_ratio = (np.count_nonzero(blue_sky_mask) + np.count_nonzero(bright_sky_mask)) / (width * int(height * 0.35))
    is_outdoor = sky_ratio > 0.15

    # 2. Categorize detections
    categories = {
        "vehicles": [],
        "people": [],
        "indoor_furniture": [],
        "outdoor_structures": [],
        "personal_items": []
    }

    vehicle_classes = {"car", "bus", "truck", "motorcycle", "bicycle"}
    indoor_classes = {"chair", "couch", "bed", "dining table", "tv", "laptop", "refrigerator", "microwave", "oven", "sink"}
    outdoor_classes = {"traffic light", "fire hydrant", "stop sign", "parking meter", "bench"}
    item_classes = {"bottle", "backpack", "umbrella", "handbag", "suitcase", "cell phone", "book"}

    for det in detections:
        label = det["label"].lower()
        if det.get("confidence", 0) < 0.35:
            continue
        x1, y1, x2, y2 = det["bbox"]
        centerX = (x1 + x2) / 2
        zone = "in front of you"
        if centerX < width / 3:
            zone = "on your left"
        elif centerX > 2 * width / 3:
            zone = "on your right"

        info = f"{label} {zone}"

        if label in vehicle_classes:
            categories["vehicles"].append(info)
            is_outdoor = True
        elif label == "person":
            categories["people"].append(zone)
        elif label in indoor_classes:
            categories["indoor_furniture"].append(info)
        elif label in outdoor_classes:
            categories["outdoor_structures"].append(info)
            is_outdoor = True
        elif label in item_classes:
            categories["personal_items"].append(info)

    # 3. Construct scene description
    parts = []
    if is_outdoor:
        env_type = "Outdoor environment"
        if categories["vehicles"]:
            parts.append(f"Vehicles present: {', '.join(categories['vehicles'][:2])}")
        if categories["outdoor_structures"]:
            parts.append(f"Roadside objects: {', '.join(categories['outdoor_structures'][:2])}")
        if categories["people"]:
            count = len(categories["people"])
            plural = "person" if count == 1 else "people"
            parts.append(f"{count} {plural} nearby ({categories['people'][0]})")
        if not parts:
            parts.append("Road or open pathway ahead with no immediate large obstacles detected.")
    else:
        env_type = "Indoor setting"
        if categories["indoor_furniture"]:
            parts.append(f"Furniture detected: {', '.join(categories['indoor_furniture'][:2])}")
        if categories["people"]:
            count = len(categories["people"])
            plural = "person" if count == 1 else "people"
            parts.append(f"{count} {plural} in the room")
        if categories["personal_items"]:
            parts.append(f"Objects: {', '.join(categories['personal_items'][:2])}")
        if not parts:
            parts.append("Indoor space with clear walking path ahead.")

    return f"{env_type}. " + ". ".join(parts) + "."

async def describe_scene(image_bytes: bytes) -> dict:
    """Analyze the complete scene using YOLO + CV heuristics or external Vision API if key available."""
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return {"scene_description": "I cannot identify the surroundings clearly right now.", "source": "error"}

    detections = detect_image(image_bytes)

    # Check if Gemini API key is provided for deep scene understanding
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            import base64
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "You are assisting a visually impaired user walking outside or inside. In 1 to 2 clear, concise sentences, describe the immediate environment: roads, buildings, shops, sidewalks, people, or obstacles. Never mention crossing roads. Be objective and factual."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}
                    ]
                }]
            }
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    desc = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return {"scene_description": desc, "source": "gemini_vision", "detections": detections}
        except Exception as e:
            # Fall back to CV heuristics gracefully
            pass

    # Local Scene Synthesis via YOLO + OpenCV
    local_desc = analyze_scene_heuristics(img_bgr, detections)
    return {
        "scene_description": local_desc,
        "source": "local_scene_engine",
        "detections": detections
    }
