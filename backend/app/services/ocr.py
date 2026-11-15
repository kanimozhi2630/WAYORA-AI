import os
import cv2
import numpy as np
import httpx
from dotenv import load_dotenv

load_dotenv()

def detect_text_regions_opencv(img_bgr):
    """Detect candidate rectangular signboards or text regions in image."""
    height, width = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Edge detection & gradient
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, -1)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, -1)
    grad = cv2.subtract(grad_x, grad_y)
    grad = cv2.convertScaleAbs(grad)

    # Blur and threshold
    blurred = cv2.GaussianBlur(grad, (9, 9), 0)
    _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological closing to connect text components horizontally
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidate_boxes = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        aspect = w / float(h)
        area = w * h
        # Typical signboard/text banner characteristics
        if aspect > 1.5 and area > 1200 and area < (width * height * 0.7):
            candidate_boxes.append((x, y, w, h))

    return candidate_boxes

async def read_signboard(image_bytes: bytes) -> dict:
    """Extract text from signboard using Vision API if key available, or OpenCV region detector."""
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return {"text": "I cannot read any text clearly right now.", "has_text": False}

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            import base64
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Read the visible signboards, shop names, street signs, or large printed text in this image. Return ONLY the exact text read from the signs. If no sign or text is visible, reply with 'NO_TEXT_FOUND'. Do not invent missing words."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}
                    ]
                }]
            }
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    extracted = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if extracted and "NO_TEXT_FOUND" not in extracted:
                        return {"text": f"The signboard reads: {extracted}", "has_text": True, "source": "gemini_ocr"}
        except Exception:
            pass

    # Local OpenCV Text Region Detection
    boxes = detect_text_regions_opencv(img_bgr)
    if boxes:
        return {
            "text": "Signboard detected in view. Set GEMINI_API_KEY in backend/.env to read exact shop text.",
            "has_text": True,
            "source": "opencv_detector",
            "regions_count": len(boxes)
        }
    else:
        return {
            "text": "No visible signboards or text detected in front of you.",
            "has_text": False,
            "source": "opencv_detector"
        }
