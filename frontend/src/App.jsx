import React, { useState, useEffect, useRef } from "react";
import "./styles/theme.css";
import { MultiObjectTracker } from "./services/tracker";
import ConversationHistory from "./components/ConversationHistory";
import DetectionHistory from "./components/DetectionHistory";
import VoiceSettings from "./components/VoiceSettings";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// Ensure persistent unique client identity for privacy and user separation
function getOrCreateUserId() {
  let uid = localStorage.getItem("wayora_user_id");
  if (!uid) {
    uid = "usr_" + Math.random().toString(36).substring(2, 9) + Date.now().toString(36);
    localStorage.setItem("wayora_user_id", uid);
  }
  return uid;
}

export default function App() {
  const [userId] = useState(getOrCreateUserId);
  const [activeTab, setActiveTab] = useState("live"); // "live", "conversation_history", "detection_history", "settings"

  // ---------- Core UI & Voice State ----------
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [assistantState, setAssistantState] = useState("idle"); // "idle", "listening", "processing", "speaking"
  const [voiceError, setVoiceError] = useState("");
  const [lastCommand, setLastCommand] = useState("");
  const [aiResponse, setAiResponse] = useState("");

  // ---------- Camera State ----------
  const [cameraActive, setCameraActive] = useState(false);
  const [activeCamera, setActiveCamera] = useState(null); // "front", "back", or "default"
  const [statusMsg, setStatusMsg] = useState("Camera ready. Say 'Start camera' or tap Start.");
  const [cameraError, setCameraError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [isAnalyzingScene, setIsAnalyzingScene] = useState(false);

  // ---------- Directional & Environmental Alert State ----------
  const [alertEnabled, setAlertEnabled] = useState(true);
  const [alertDisplay, setAlertDisplay] = useState("");
  const [activeDetections, setActiveDetections] = useState([]);
  const alertHistoryRef = useRef({});
  const APPROACH_COOLDOWN = 3500;

  // ---------- Voice & Privacy Settings State ----------
  const [voiceSettings, setVoiceSettings] = useState({
    voice_name: "",
    speech_rate: 1.0,
    speech_pitch: 1.0,
    language: "en-US",
    alert_frequency: 4000,
    alerts_muted: false,
    consent_save_history: true,
  });

  // Load initial settings from backend
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/settings`, {
      headers: { "X-User-ID": userId },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.settings) {
          setVoiceSettings(data.settings);
          if (data.settings.alerts_muted) {
            setAlertEnabled(false);
          }
        }
      })
      .catch((err) => console.warn("Initial settings fetch:", err));
  };
 [userId]);

  // ---------- Conversational Memory & Refs ----------
  const chatHistoryRef = useRef([]);
  const trackerRef = useRef(new MultiObjectTracker());
  const latestDetectionsRef = useRef([]);
  const isVoiceEnabledRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const commandLock = useRef(false);
  const lastProcessedTimeRef = useRef(0);
  const restartTimeoutRef = useRef(null);

  // ---------- DOM Refs ----------
  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const captureIntervalRef = useRef(null);
  const recognizerRef = useRef(null);
  const processingRef = useRef(false);

  useEffect(() => {
    isVoiceEnabledRef.current = voiceEnabled;
  };
 [voiceEnabled]);

  useEffect(() => {
    processingRef.current = processing;
  };
 [processing]);

  // ---------- Speech Synthesis Helper with User Preferences ----------
  const speak = (msg, interrupt = false, onComplete = null) => {
    if (!window.speechSynthesis) return;

    if (interrupt) {
      window.speechSynthesis.cancel();
      isSpeakingRef.current = false;
    } else if (isSpeakingRef.current || window.speechSynthesis.speaking) {
      return;
    }

    const utter = new SpeechSynthesisUtterance(msg);
    utter.rate = voiceSettings.speech_rate || 1.0;
    utter.pitch = voiceSettings.speech_pitch || 1.0;
    utter.lang = voiceSettings.language || "en-US";

    if (voiceSettings.voice_name) {
      const voices = window.speechSynthesis.getVoices();
      const matched = voices.find((v) => v.name === voiceSettings.voice_name);
      if (matched) {
        utter.voice = matched;
      }
    }

    utter.onstart = () => {
      isSpeakingRef.current = true;
      setAssistantState("speaking");

    utter.onend = () => {
      isSpeakingRef.current = false;
      if (isVoiceEnabledRef.current) {
        setAssistantState("listening");
      } else {
        setAssistantState("idle");
      }
      if (onComplete) onComplete();

    utter.onerror = () => {
      isSpeakingRef.current = false;
      if (isVoiceEnabledRef.current) {
        setAssistantState("listening");
      } else {
        setAssistantState("idle");
      }

    window.speechSynthesis.speak(utter);


  // Helper to log actual deduplicated YOLO detection to MongoDB
  const logDetectionToDatabase = async (label, confidence, direction) => {
    try {
      await fetch(API_BASE_URL + '/api/detections', {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId,
        };

        body: JSON.stringify({
          label,
          confidence,
          direction,
        }),
      });
    } catch (e) {
      // Background non-blocking log
    }


  // ---------- Conversational AI Client (/chat) ----------
  const sendToChatAI = async (userMessage) => {
    setAssistantState("processing");
    setStatusMsg("Thinking...");

    try {
      const payload = {
        message: userMessage,
        history: chatHistoryRef.current.slice(-6),
        camera_active: cameraActive,
        visual_context: {
          detections: latestDetectionsRef.current.map((d) => ({
            label: d.label,
            zone: d.zone,
            confidence: d.confidence,
            isApproaching: d.isApproaching || false,
          })),
        };

  
      const resp = await fetch(API_BASE_URL + '/chat', {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId,
        };

        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        throw new Error(`Chat API error (${resp.status})`);
      }

      const data = await resp.json();
      const reply = data.reply || "I'm here to help you navigate your surroundings.";

      // Maintain short-term conversational session memory
      chatHistoryRef.current.push({ role: "user", content: userMessage });
      chatHistoryRef.current.push({ role: "assistant", content: reply });
      if (chatHistoryRef.current.length > 8) {
        chatHistoryRef.current = chatHistoryRef.current.slice(-8);
      }

      setAiResponse(reply);
      setStatusMsg("Speaking response...");
      speak(reply, true);
    } catch (err) {
      console.error("Chat communication error:", err);
      const fallbackReply =
        "I'm here as your walking companion. You can ask what is around you, read signboards, or start the camera.";
      setAiResponse(fallbackReply);
      speak(fallbackReply, true);
    }


  // ---------- Camera Controls ----------
  const stopCurrentStream = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }
    clearOverlay();
    setActiveDetections([]);
    latestDetectionsRef.current = [];
    trackerRef.current.reset();


  const startCamera = async (facingModeConstraint = null, label = "default") => {
  // Determine which camera to request. Default is rear (environment).
  const effectiveFacingMode = facingModeConstraint || "environment";

  // Verify getUserMedia support
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const errMsg = "Camera API (getUserMedia) not supported in this browser.";
    setCameraError(errMsg);
    setStatusMsg(errMsg);
    speak("Camera is not supported on this browser.", true);
    return;
  }

  // Stop any previous stream before opening a new one
  stopCurrentStream();
  setCameraError("");
  setStatusMsg(`Starting ${label === "default" ? "" : label + " "}camera...`);

  // Build the constraints once, using the effective facing mode
  const constraints = {
    video: {
      facingMode: { ideal: effectiveFacingMode },
      width: { ideal: 640 },
      height: { ideal: 480 },
    };



  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    if (!videoRef.current) {
      throw new Error("Video element is not available.");
    }
    videoRef.current.srcObject = stream;
    try {
      await videoRef.current.play();
    } catch (playErr) {
      console.warn("Autoplay was prevented or postponed:", playErr);
    }
    setCameraActive(true);
    setActiveCamera(label);
    setCameraError("");

    const startedMsg =
      label === "front"
        ? "Front camera activated."
        : label === "back"
        ? "Rear camera activated."
        : "Camera started.";
    setStatusMsg(startedMsg);
    speak(startedMsg, true);

    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
    }
    captureIntervalRef.current = setInterval(captureAndDetect, 1000);
  } catch (err) {
    console.error("Camera access error:", err);
    let errMsg = err.message || "Failed to start camera.";
    if (err.name === "NotAllowedError") {
      errMsg = "Camera permission denied. Please allow camera access in browser settings.";
    } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
      errMsg = "Requested camera device not found on this system.";
    } else if (err.name === "OverconstrainedError") {
      errMsg = "Requested camera configuration not supported.";
    }
    setCameraError(errMsg);
    setStatusMsg(errMsg);
    setCameraActive(false);
    setActiveCamera(null);
    speak(errMsg, true);
  }
};
    




  const handleStart = () => startCamera(null, "default");
  const handleStartFront = () => startCamera("user", "front");
  const handleStartBack = () => startCamera("environment", "back");

  const handleStop = () => {
    stopCurrentStream();
    setCameraActive(false);
    setActiveCamera(null);
    setStatusMsg("Camera stopped.");
    speak("Camera stopped.", true);
  };


  // ---------- Overlay Canvas Drawing ----------
  const clearOverlay = () => {
    const canvas = overlayRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }


  const drawDetections = (trackedObjects) => {
    const canvas = overlayRef.current;
    const video = videoRef.current;
    if (!canvas || !video || !video.videoWidth || !video.videoHeight) return;

    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const frameWidth = canvas.width;
    const third = frameWidth / 3;

    // Draw zone divider guides
    ctx.strokeStyle = "rgba(200, 161, 101, 0.4)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 6]);
    ctx.beginPath();
    ctx.moveTo(third, 0);
    ctx.lineTo(third, canvas.height);
    ctx.moveTo(2 * third, 0);
    ctx.lineTo(2 * third, canvas.height);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "rgba(242, 238, 232, 0.55)";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("LEFT ZONE", 12, 22);
    ctx.fillText("CENTER ZONE", third + 12, 22);
    ctx.fillText("RIGHT ZONE", 2 * third + 12, 22);

    trackedObjects.forEach((det) => {
      const [x1, y1, x2, y2] = det.bbox;
      const w = x2 - x1;
      const h = y2 - y1;

      if (det.isApproaching) {
        ctx.strokeStyle = "#D9534F";
        ctx.lineWidth = 3.5;
      } else {
        ctx.strokeStyle = "#C8A165";
        ctx.lineWidth = 2.5;
      }
      ctx.strokeRect(x1, y1, w, h);

      const labelCap = det.label.charAt(0).toUpperCase() + det.label.slice(1);
      const confPct = `${(det.confidence * 100).toFixed(0)}%`;
      const statusTag = det.isApproaching ? "APPROACHING" : det.zone;
      const displayLabel = `${labelCap} – ${statusTag} – ${confPct}`;

      ctx.font = "bold 13px sans-serif";
      const textWidth = ctx.measureText(displayLabel).width;

      ctx.fillStyle = det.isApproaching ? "#661815" : "#4A382C";
      ctx.fillRect(x1, Math.max(0, y1 - 22), textWidth + 10, 22);

      ctx.fillStyle = "#F2EEE8";
      ctx.fillText(displayLabel, x1 + 5, Math.max(16, y1 - 6));
    });


  // ---------- Directional Alerts & Movement Processing ----------
  const processDetections = (trackedObjects) => {
    latestDetectionsRef.current = trackedObjects;
    setActiveDetections(trackedObjects);

    if (trackedObjects.length === 0) return;
    if (isSpeakingRef.current) return;

    const now = Date.now();
    const alertCooldown = voiceSettings.alert_frequency || 4000;
    const isMuted = voiceSettings.alerts_muted || !alertEnabled;

    // 1. Approaching Vehicle Alert
    const approachingVehicle = trackedObjects.find((t) => t.isVehicle && t.isApproaching);
    if (approachingVehicle) {
      const key = `approaching-${approachingVehicle.id}`;
      const lastSpoken = alertHistoryRef.current[key] || 0;
      if (now - lastSpoken >= APPROACH_COOLDOWN) {
        alertHistoryRef.current[key] = now;
        const alertMsg = `A vehicle appears to be approaching from your ${approachingVehicle.zone.toLowerCase()}. Please wait and remain cautious.`;
        setAlertDisplay(`⚠️ ${alertMsg}`);

        // Persist deduplicated detection to MongoDB
        logDetectionToDatabase(
          approachingVehicle.label,
          approachingVehicle.confidence,
          approachingVehicle.zone
        );

        if (!isMuted) {
          speak(alertMsg, true);
        }
        return;
      }
    }

    // 2. Approaching Person in walking path
    const approachingPerson = trackedObjects.find(
      (t) => t.label === "person" && t.zone === "CENTER" && t.isApproaching
    );
    if (approachingPerson) {
      const key = `walking-person-${approachingPerson.id}`;
      const lastSpoken = alertHistoryRef.current[key] || 0;
      if (now - lastSpoken >= alertCooldown) {
        alertHistoryRef.current[key] = now;
        const alertMsg = "A person is walking in front of you.";
        setAlertDisplay(`🚶 ${alertMsg}`);

        logDetectionToDatabase("person", approachingPerson.confidence, "CENTER");

        if (!isMuted) {
          speak(alertMsg, false);
        }
        return;
      }
    }

    // 3. Regular Environmental Directional Alerts
    const sorted = [...trackedObjects].sort((a, b) => {
      const aWeight = a.area * (a.zone === "CENTER" ? 1.4 : 1.0) * (a.isVehicle ? 1.3 : 1.0);
      const bWeight = b.area * (b.zone === "CENTER" ? 1.4 : 1.0) * (b.isVehicle ? 1.3 : 1.0);
      return bWeight - aWeight;
    });

    const primary = sorted[0];
    const key = `${primary.label}-${primary.zone}`;
    const lastSpoken = alertHistoryRef.current[key] || 0;

    if (now - lastSpoken >= alertCooldown) {
      alertHistoryRef.current[key] = now;

      let message = "";
      const capLabel = primary.label.charAt(0).toUpperCase() + primary.label.slice(1);

      if (primary.isVehicle) {
        message = `A ${primary.label} is visible ${
          primary.zone === "CENTER" ? "ahead" : "on your " + primary.zone.toLowerCase()
        }.`;
      } else {
        const directionPhrase =
          primary.zone === "CENTER" ? "in front of you" : `on your ${primary.zone.toLowerCase()}`;
        message = `${capLabel} detected ${directionPhrase}.`;
      }

      setAlertDisplay(message);

      // Persist deduplicated detection record to MongoDB
      logDetectionToDatabase(primary.label, primary.confidence, primary.zone);

      if (!isMuted) {
        speak(message, false);
      }
    }


  // ---------- Periodic YOLO Frame Detection Loop ----------
  const captureAndDetect = async () => {
    if (!videoRef.current || processingRef.current) return;
    const video = videoRef.current;
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) return;

    setProcessing(true);
    processingRef.current = true;

    try {
      const offCanvas = document.createElement("canvas");
      offCanvas.width = video.videoWidth;
      offCanvas.height = video.videoHeight;
      const ctx = offCanvas.getContext("2d");
      ctx.drawImage(video, 0, 0, offCanvas.width, offCanvas.height);

      offCanvas.toBlob(
        async (blob) => {
          if (!blob) {
            setProcessing(false);
            processingRef.current = false;
            return;
          }

          const form = new FormData();
          form.append("file", blob, "frame.jpg");

          try {
            const resp = await fetch(`${API_BASE_URL}/detect`, {
              method: "POST",
              body: form,
            });

            if (!resp.ok) {
              const errData = await resp.json().catch(() => ({}));
              setStatusMsg(`Detection API error: ${errData.detail || resp.status}`);
              clearOverlay();
            } else {
              const data = await resp.json();
              const rawDetections = data.detections || [];
              const frameWidth = video.videoWidth || 640;

              const confidentDetections = rawDetections.filter(
                (d) => (d.confidence || 0) >= 0.4
              );

              const trackedObjects = trackerRef.current.update(
                confidentDetections,
                frameWidth,
                Date.now()
              );

              drawDetections(trackedObjects);
              processDetections(trackedObjects);

              if (trackedObjects.length > 0) {
                const approachingCount = trackedObjects.filter((t) => t.isApproaching).length;
                if (approachingCount > 0) {
                  setStatusMsg(`⚠️ Movement: ${approachingCount} approaching obstacle(s)`);
                } else {
                  setStatusMsg(`Tracking ${trackedObjects.length} object(s)`);
                }
              } else {
                setStatusMsg("No obstacles detected in view");
              }
            }
          } catch (netErr) {
            console.error("FastAPI backend connection error:", netErr);
            setStatusMsg("Backend offline. Ensure FastAPI is running on port 8000.");
          } finally {
            setProcessing(false);
            processingRef.current = false;
          }
        };

        "image/jpeg",
        0.8
      );
    } catch (captureErr) {
      console.error("Frame capture error:", captureErr);
      setProcessing(false);
      processingRef.current = false;
    }


  // ---------- Scene Understanding Service (Module 3) ----------
  const requestSceneDescription = async () => {
    if (!videoRef.current || videoRef.current.readyState < 2) {
      const msg = "Camera is not active. Please start camera to analyze surroundings.";
      setAiResponse(msg);
      speak(msg, true);
      return;
    }

    setIsAnalyzingScene(true);
    setAssistantState("processing");
    setStatusMsg("Analyzing complete surroundings...");

    try {
      const video = videoRef.current;
      const offCanvas = document.createElement("canvas");
      offCanvas.width = video.videoWidth;
      offCanvas.height = video.videoHeight;
      const ctx = offCanvas.getContext("2d");
      ctx.drawImage(video, 0, 0, offCanvas.width, offCanvas.height);

      offCanvas.toBlob(async (blob) => {
        if (!blob) {
          setIsAnalyzingScene(false);
          return;
        }

        const form = new FormData();
        form.append("file", blob, "scene.jpg");

        try {
          const resp = await fetch(`${API_BASE_URL}/scene`, {
            method: "POST",
            body: form,
          });

          if (resp.ok) {
            const data = await resp.json();
            const desc = data.scene_description || "I cannot identify the surroundings clearly right now.";
            setAiResponse(desc);
            chatHistoryRef.current.push({ role: "assistant", content: desc });
            speak(desc, true);
          } else {
            const fallback = "I cannot identify the surroundings clearly right now.";
            setAiResponse(fallback);
            speak(fallback, true);
          }
        } catch (e) {
          const fallback = "Scene understanding service is currently offline.";
          setAiResponse(fallback);
          speak(fallback, true);
        } finally {
          setIsAnalyzingScene(false);
        }
      };
 "image/jpeg", 0.85);
    } catch (e) {
      setIsAnalyzingScene(false);
    }


  // ---------- OCR Signboard Reading Service (Module 6) ----------
  const requestOCR = async () => {
    if (!videoRef.current || videoRef.current.readyState < 2) {
      const msg = "Camera is not active. Please start camera to read signboards.";
      setAiResponse(msg);
      speak(msg, true);
      return;
    }

    setAssistantState("processing");
    setStatusMsg("Scanning for signboards and shop text...");

    try {
      const video = videoRef.current;
      const offCanvas = document.createElement("canvas");
      offCanvas.width = video.videoWidth;
      offCanvas.height = video.videoHeight;
      const ctx = offCanvas.getContext("2d");
      ctx.drawImage(video, 0, 0, offCanvas.width, offCanvas.height);

      offCanvas.toBlob(async (blob) => {
        if (!blob) return;

        const form = new FormData();
        form.append("file", blob, "ocr.jpg");

        try {
          const resp = await fetch(`${API_BASE_URL}/ocr`, {
            method: "POST",
            body: form,
          });

          if (resp.ok) {
            const data = await resp.json();
            const text = data.text || "No visible signboards or text detected in front of you.";
            setAiResponse(text);
            chatHistoryRef.current.push({ role: "assistant", content: text });
            speak(text, true);
          } else {
            const fallback = "Could not read signboards in the current frame.";
            setAiResponse(fallback);
            speak(fallback, true);
          }
        } catch (e) {
          const fallback = "OCR reading service is currently offline.";
          setAiResponse(fallback);
          speak(fallback, true);
        }
      };
 "image/jpeg", 0.9);
    } catch (e) {
      console.error(e);
    }


  // ---------- Conversational & Voice Command Router ----------
  const processVoiceCommand = (rawTranscript) => {
    const now = Date.now();
    if (commandLock.current || now - lastProcessedTimeRef.current < 1200) {
      return;
    }
    commandLock.current = true;
    lastProcessedTimeRef.current = now;

    const cmd = rawTranscript
      .toLowerCase()
      .replace(/[.,!?]/g, "")
      .trim();

    console.log("Processing voice input:", cmd);

    try {
      // 1. Direct Hardware Commands
      if (cmd.includes("stop camera") || (cmd.includes("camera") && cmd.includes("stop"))) {
        handleStop();
        return;
      }
      if (cmd.includes("front camera") || cmd.includes("start front")) {
        handleStartFront();
        return;
      }
      if (
        cmd.includes("back camera") ||
        cmd.includes("rear camera") ||
        cmd.includes("start back") ||
        cmd.includes("start rear")
      ) {
        handleStartBack();
        return;
      }
      if (
        cmd.includes("start camera") ||
        cmd.includes("open camera") ||
        cmd === "camera" ||
        cmd === "start"
      ) {
        handleStart();
        return;
      }

      // 2. Direct Specialized Perception Commands
      if (cmd.includes("describe surroundings") || cmd.includes("what is around me")) {
        requestSceneDescription();
        return;
      }
      if (
        cmd.includes("read signboard") ||
        cmd.includes("read the sign") ||
        cmd.includes("read shop name") ||
        cmd.includes("what is written")
      ) {
        requestOCR();
        return;
      }

      // 3. Natural Conversational AI
      sendToChatAI(rawTranscript);
    } finally {
      setTimeout(() => {
        commandLock.current = false;
      };
 500);
    }


  // ---------- Speech Recognition Lifecycle ----------
  const startSpeechRecognition = async () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      const err = "Speech recognition is not supported in this browser. Please use Google Chrome.";
      setVoiceError(err);
      speak(err, true);
      return;
    }

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStream.getTracks().forEach((track) => track.stop());
      } catch (micErr) {
        const err = "Microphone access denied. Please allow microphone permission.";
        setVoiceError(err);
        setVoiceEnabled(false);
        speak(err, true);
        return;
      }
    }

    try {
      if (recognizerRef.current) {
        recognizerRef.current.abort();
        recognizerRef.current = null;
      }

      const recognizer = new SpeechRecognition();
      recognizer.continuous = true;
      recognizer.interimResults = false;
      recognizer.lang = voiceSettings.language || "en-US";
      recognizerRef.current = recognizer;

      recognizer.onstart = () => {
        setIsListening(true);
        setVoiceError("");
        if (!isSpeakingRef.current) {
          setAssistantState("listening");
        }
  
      recognizer.onresult = (event) => {
        if (isSpeakingRef.current) return;

        const lastIdx = event.results.length - 1;
        const result = event.results[lastIdx];
        if (result && result.isFinal) {
          const transcript = result[0].transcript.trim();
          if (transcript.length > 0) {
            setLastCommand(transcript);
            processVoiceCommand(transcript);
          }
        }
  
      recognizer.onerror = (event) => {
        console.warn("Speech recognition event:", event.error);
        if (event.error === "not-allowed") {
          setVoiceError("Microphone permission denied.");
          setVoiceEnabled(false);
          setIsListening(false);
          setAssistantState("idle");
        } else if (event.error !== "no-speech" && event.error !== "aborted") {
          setVoiceError(`Voice notice: ${event.error}`);
        }
  
      recognizer.onend = () => {
        setIsListening(false);
        if (isVoiceEnabledRef.current) {
          clearTimeout(restartTimeoutRef.current);
          restartTimeoutRef.current = setTimeout(() => {
            if (isVoiceEnabledRef.current && recognizerRef.current) {
              try {
                recognizerRef.current.start();
              } catch (e) {
                // Ignore if already active
              }
            }
          };
 300);
        } else {
          setAssistantState("idle");
        }
  
      recognizer.start();
      setVoiceEnabled(true);
      speak("Voice assistance enabled.", true);
    } catch (e) {
      console.error("Failed to start speech recognition:", e);
      setVoiceError("Could not initialize voice recognition.");
    }


  const stopSpeechRecognition = () => {
    setVoiceEnabled(false);
    isVoiceEnabledRef.current = false;
    clearTimeout(restartTimeoutRef.current);
    if (recognizerRef.current) {
      recognizerRef.current.abort();
      recognizerRef.current = null;
    }
    setIsListening(false);
    setAssistantState("idle");
    speak("Voice assistance disabled.", true);


  const toggleVoice = () => {
    if (voiceEnabled) {
      stopSpeechRecognition();
    } else {
      startSpeechRecognition();
    }


  useEffect(() => {
    return () => {
      stopCurrentStream();
      if (recognizerRef.current) {
        recognizerRef.current.abort();
      }
      clearTimeout(restartTimeoutRef.current);
  };
 []);

  const getAssistantBadge = () => {
    switch (assistantState) {
      case "listening":
        return <span className="mic-status listening">🎤 Listening...</span>;
      case "processing":
        return <span className="mic-status processing">⏳ Thinking...</span>;
      case "speaking":
        return <span className="mic-status speaking">🔊 Speaking...</span>;
      default:
        return <span className="mic-status idle">🔇 Mic Off</span>;
    }


  const handleTestVoiceAudio = (settings) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance("Hello! This is WAYORA AI, your walking companion.");
    utter.rate = settings.speech_rate || 1.0;
    utter.pitch = settings.speech_pitch || 1.0;
    utter.lang = settings.language || "en-US";
    if (settings.voice_name) {
      const voices = window.speechSynthesis.getVoices();
      const matched = voices.find((v) => v.name === settings.voice_name);
      if (matched) utter.voice = matched;
    }
    window.speechSynthesis.speak(utter);


  const handleSettingsSaved = (updated) => {
    setVoiceSettings(updated);
    if (updated.alerts_muted !== undefined) {
      setAlertEnabled(!updated.alerts_muted);
    }


  const handleToggleConsent = async (consent) => {
    const updated = { ...voiceSettings, consent_save_history: consent };
    setVoiceSettings(updated);
    try {
      await fetch(`${API_BASE_URL}/api/settings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId,
        };

        body: JSON.stringify(updated),
      });
    } catch (e) {}


  return (
    <div className="app-container" role="main">
      <header className="app-header">
        <h1>WAYORA AI</h1>
        <h2>Conversational AI Walking Companion & Environmental Guide</h2>
      </header>

      {/* Primary Accessible Navigation Bar */}
      <nav className="main-nav" aria-label="Main Navigation">
        <button
          className={`nav-tab ${activeTab === "live" ? "active" : ""}`}
          onClick={() => setActiveTab("live")}
          aria-current={activeTab === "live" ? "page" : undefined}
        >
          👁️ Live Assistance
        </button>
        <button
          className={`nav-tab ${activeTab === "conversation_history" ? "active" : ""}`}
          onClick={() => setActiveTab("conversation_history")}
          aria-current={activeTab === "conversation_history" ? "page" : undefined}
        >
          💬 Conversation History
        </button>
        <button
          className={`nav-tab ${activeTab === "detection_history" ? "active" : ""}`}
          onClick={() => setActiveTab("detection_history")}
          aria-current={activeTab === "detection_history" ? "page" : undefined}
        >
          🎯 Detection History
        </button>
        <button
          className={`nav-tab ${activeTab === "settings" ? "active" : ""}`}
          onClick={() => setActiveTab("settings")}
          aria-current={activeTab === "settings" ? "page" : undefined}
        >
          ⚙️ Voice Settings
        </button>
      </nav>

      {/* Screen 1: Live Assistance */}
      {activeTab === "live" && (
        <main className="tab-content">
          <section className="voice-panel" aria-label="Voice Controls & Conversation">
            <div className="button-group">
              <button
                className={`voice-btn ${voiceEnabled ? "active" : ""}`}
                onClick={toggleVoice}
                aria-label="Toggle Voice Assistance"
              >
                {voiceEnabled ? "Disable Voice" : "Enable Voice"}
              </button>
              <button
                className={`voice-btn ${alertEnabled ? "" : "muted"}`}
                onClick={() => setAlertEnabled((v) => !v)}
                aria-label="Toggle Voice Alerts"
              >
                {alertEnabled ? "Mute Alerts" : "Unmute Alerts"}
              </button>
              {getAssistantBadge()}
            </div>

            {voiceError && <div className="error-badge">{voiceError}</div>}

            {lastCommand && (
              <div className="last-command-badge">
                You said: <strong>"{lastCommand}"</strong>
              </div>
            )}

            {aiResponse && (
              <div className="ai-response-box" aria-live="polite">
                <span className="ai-tag">WAYORA:</span> {aiResponse}
              </div>
            )}

            {alertDisplay && (
              <div className="alert-banner" aria-live="polite">
                📢 {alertDisplay}
              </div>
            )}
          </section>

          <section className="camera-section" aria-label="Camera Live Feed">
            <div className="camera-preview-wrapper">
              <video
                ref={videoRef}
                className="camera-video"
                autoPlay
                playsInline
                muted
                style={{ display: cameraActive ? "block" : "none" }}
              />
              <canvas
                ref={overlayRef}
                className="overlay-canvas"
                style={{ display: cameraActive ? "block" : "none" }}
              />

              {!cameraActive && (
                <div className="camera-placeholder">
                  <span className="placeholder-icon">📷</span>
                  <p>Camera is currently stopped</p>
                  <small>Say "Start camera" or tap button below</small>
                </div>
              )}
            </div>

            {activeDetections.length > 0 && (
              <div className="detections-container" aria-label="Detected Objects List">
                <div className="detections-title">
                  Tracked Objects ({activeDetections.length}):
                </div>
                <div className="detections-grid">
                  {activeDetections.map((det) => (
                    <div
                      key={det.id}
                      className={`detection-chip zone-${det.zone.toLowerCase()} ${
                        det.isApproaching ? "status-approaching" : ""
                      }`}
                    >
                      <span className="chip-name">
                        {det.label.charAt(0).toUpperCase() + det.label.slice(1)}
                      </span>
                      <span className="chip-sep">–</span>
                      <span className="chip-zone">
                        {det.isApproaching ? "⚠️ APPROACHING" : det.zone}
                      </span>
                      <span className="chip-sep">–</span>
                      <span className="chip-conf">{(det.confidence * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="question-shortcuts" aria-label="Conversational Questions">
              <span className="shortcuts-label">Try asking:</span>
              <button className="query-btn" onClick={() => sendToChatAI("Hello!")}>
                "Hello"
              </button>
              <button className="query-btn" onClick={() => sendToChatAI("How are you?")}>
                "How are you?"
              </button>
              <button className="query-btn" onClick={() => sendToChatAI("What can you do?")}>
                "What can you do?"
              </button>
              <button className="query-btn" onClick={() => sendToChatAI("What is in front of me?")}>
                "What is in front?"
              </button>
              <button
                className="query-btn highlight-btn"
                disabled={isAnalyzingScene}
                onClick={() => requestSceneDescription()}
              >
                {isAnalyzingScene ? "Analyzing..." : "Describe surroundings"}
              </button>
              <button className="query-btn highlight-btn" onClick={() => requestOCR()}>
                Read signboard
              </button>
            </div>

            <div className="controls">
              {cameraActive ? (
                <button className="control-btn stop-btn" onClick={handleStop}>
                  Stop Camera
                </button>
              ) : (
                <>
                  <button className="control-btn primary-btn" onClick={handleStart}>
                    Start Camera
                  </button>
                  <button className="control-btn secondary-btn" onClick={handleStartFront}>
                    Front Camera
                  </button>
                  <button className="control-btn secondary-btn" onClick={handleStartBack}>
                    Rear Camera
                  </button>
                </>
              )}
            </div>

            <div className="status" aria-live="polite">
              {statusMsg}
            </div>
            {cameraError && (
              <div className="error-msg" aria-live="polite">
                ⚠️ {cameraError}
              </div>
            )}
          </section>
        </main>
      )}

      {/* Screen 2: Voice Conversation History */}
      {activeTab === "conversation_history" && (
        <ConversationHistory
          userId={userId}
          apiBaseUrl={API_BASE_URL}
          consentSave={voiceSettings.consent_save_history !== false}
          onToggleConsent={handleToggleConsent}
        />
      )}

      {/* Screen 3: Object Detection History */}
      {activeTab === "detection_history" && (
        <DetectionHistory userId={userId} apiBaseUrl={API_BASE_URL} />
      )}

      {/* Screen 4: Voice & Guidance Settings */}
      {activeTab === "settings" && (
        <VoiceSettings
          userId={userId}
          apiBaseUrl={API_BASE_URL}
          currentSettings={voiceSettings}
          onSettingsSaved={handleSettingsSaved}
          onTestVoice={handleTestVoiceAudio}
        />
      )}

      {/* Safety Notice & Accessibility Disclaimer */}
      <footer className="safety-disclaimer">
        <p>
          <strong>⚠️ Safety Disclaimer:</strong> WAYORA AI is an assistive environmental-awareness prototype.
          It does not compute exact physical distances, does not guarantee safe walking paths, and NEVER
          authorizes road crossings. Visually impaired users must continue to rely on a white cane, guide dog,
          pedestrian audio signals, and safe navigation practices.
        </p>
      </footer>
    </div>
  );
}
