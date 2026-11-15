/**
 * WAYORA AI - Multi-Object Frame Tracker & Movement Analyzer
 * Tracks objects across consecutive frames using IoU (Intersection over Union).
 * Estimates vehicle and obstacle movement (e.g. approaching, stationary, receding).
 */

export function computeIoU(boxA, boxB) {
  const [ax1, ay1, ax2, ay2] = boxA;
  const [bx1, by1, bx2, by2] = boxB;

  const xLeft = Math.max(ax1, bx1);
  const yTop = Math.max(ay1, by1);
  const xRight = Math.min(ax2, bx2);
  const yBottom = Math.min(ay2, by2);

  if (xRight <= xLeft || yBottom <= yTop) {
    return 0.0;
  }

  const intersection = (xRight - xLeft) * (yBottom - yTop);
  const areaA = (ax2 - ax1) * (ay2 - ay1);
  const areaB = (bx2 - bx1) * (by2 - by1);
  const union = areaA + areaB - intersection;

  return union > 0 ? intersection / union : 0.0;
}

const VEHICLE_CLASSES = new Set(["car", "bus", "truck", "motorcycle", "bicycle"]);

export class MultiObjectTracker {
  constructor() {
    this.tracks = []; // [{ id, label, confidence, bbox, zone, history: [{bbox, area, time}], status, missedFrames }]
    this.nextId = 1;
  }

  reset() {
    this.tracks = [];
    this.nextId = 1;
  }

  update(detections, frameWidth, now = Date.now()) {
    const third = frameWidth / 3.0;
    const currentAnalyzed = detections.map((det) => {
      const [x1, y1, x2, y2] = det.bbox;
      const centerX = (x1 + x2) / 2.0;
      const centerY = (y1 + y2) / 2.0;
      const area = (x2 - x1) * (y2 - y1);

      let zone = "CENTER";
      if (centerX < third) {
        zone = "LEFT";
      } else if (centerX > 2 * third) {
        zone = "RIGHT";
      }

      return {
        ...det,
        centerX,
        centerY,
        area,
        zone,
        matched: false,
      };
    });

    const updatedTracks = [];

    // Match existing tracks with current detections using IoU + label match
    for (const track of this.tracks) {
      let bestMatchIdx = -1;
      let maxIoU = 0.25; // Minimum IoU threshold to consider same physical object

      for (let i = 0; i < currentAnalyzed.length; i++) {
        const candidate = currentAnalyzed[i];
        if (candidate.matched || candidate.label !== track.label) continue;

        const iou = computeIoU(track.bbox, candidate.bbox);
        if (iou > maxIoU) {
          maxIoU = iou;
          bestMatchIdx = i;
        }
      }

      if (bestMatchIdx !== -1) {
        const match = currentAnalyzed[bestMatchIdx];
        match.matched = true;

        // Update track history
        track.bbox = match.bbox;
        track.confidence = match.confidence;
        track.zone = match.zone;
        track.area = match.area;
        track.centerX = match.centerX;
        track.centerY = match.centerY;
        track.missedFrames = 0;

        track.history.push({
          bbox: match.bbox,
          area: match.area,
          centerY: match.centerY,
          time: now,
        });

        if (track.history.length > 8) {
          track.history.shift();
        }

        // Analyze movement trend over available history
        const isVehicle = VEHICLE_CLASSES.has(track.label.toLowerCase());
        let status = "TRACKED";
        let isApproaching = false;

        if (track.history.length >= 3) {
          const firstInWindow = track.history[0];
          const lastInWindow = track.history[track.history.length - 1];

          const areaDelta = (lastInWindow.area - firstInWindow.area) / Math.max(1, firstInWindow.area);
          const yDelta = lastInWindow.centerY - firstInWindow.centerY;

          // Growing bounding box area (>15%) and expanding vertically downward indicates approaching movement
          if (areaDelta > 0.15 && yDelta >= -5) {
            status = "APPROACHING";
            isApproaching = true;
          } else if (areaDelta < -0.15) {
            status = "RECEDING";
          }
        }

        track.status = status;
        track.isApproaching = isApproaching;
        track.isVehicle = isVehicle;

        updatedTracks.push(track);
      } else {
        // Track missed in this frame
        track.missedFrames += 1;
        if (track.missedFrames <= 2) {
          updatedTracks.push(track);
        }
      }
    }

    // Unmatched detections become new tracks
    for (const candidate of currentAnalyzed) {
      if (!candidate.matched) {
        const isVehicle = VEHICLE_CLASSES.has(candidate.label.toLowerCase());
        const newTrack = {
          id: this.nextId++,
          label: candidate.label,
          confidence: candidate.confidence,
          bbox: candidate.bbox,
          zone: candidate.zone,
          area: candidate.area,
          centerX: candidate.centerX,
          centerY: candidate.centerY,
          status: "NEW",
          isApproaching: false,
          isVehicle,
          missedFrames: 0,
          history: [{
            bbox: candidate.bbox,
            area: candidate.area,
            centerY: candidate.centerY,
            time: now,
          }],
        };
        updatedTracks.push(newTrack);
      }
    }

    this.tracks = updatedTracks;

    // Return tracks currently visible in this frame (missedFrames === 0)
    return this.tracks.filter((t) => t.missedFrames === 0);
  }
}
