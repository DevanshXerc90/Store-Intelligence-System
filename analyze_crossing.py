import cv2
from ultralytics import YOLO

video_path = "/app/data/videos/CAM 3.mp4"
cap = cv2.VideoCapture(video_path)
model = YOLO("yolov8n.pt")
frame_idx = 0
trajectories = {}

print("Extracting trajectories from CAM 3...")
while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1
    if frame_idx % 5 != 0:  # sample at 6 FPS
        continue
        
    res = model.track(frame, persist=True, classes=[0], conf=0.3, verbose=False)
    if res and res[0].boxes is not None and res[0].boxes.id is not None:
        ids = res[0].boxes.id.cpu().numpy()
        boxes = res[0].boxes.xyxy.cpu().numpy()
        for tid, box in zip(ids, boxes):
            tid = int(tid)
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            if tid not in trajectories:
                trajectories[tid] = []
            trajectories[tid].append((frame_idx, cx, cy))
cap.release()

print(f"Extracted {len(trajectories)} tracks.")

# Test vertical lines (X-crossings)
print("\nTesting Vertical Lines (X crossings):")
for x_candidate in range(400, 1600, 100):
    crossings = 0
    for tid, traj in trajectories.items():
        # Check if the track crosses x_candidate
        sides = []
        for f, cx, cy in traj:
            if cx < x_candidate:
                sides.append("left")
            else:
                sides.append("right")
        # Find transitions
        transitions = 0
        current_side = None
        for s in sides:
            if current_side is None:
                current_side = s
            elif s != current_side:
                transitions += 1
                current_side = s
        if transitions > 0:
            crossings += 1
    print(f"  Line x={x_candidate}: {crossings} tracks crossed")

# Test horizontal lines (Y-crossings)
print("\nTesting Horizontal Lines (Y crossings):")
for y_candidate in range(200, 1000, 100):
    crossings = 0
    for tid, traj in trajectories.items():
        # Check if the track crosses y_candidate
        sides = []
        for f, cx, cy in traj:
            if cy < y_candidate:
                sides.append("top")
            else:
                sides.append("bottom")
        # Find transitions
        transitions = 0
        current_side = None
        for s in sides:
            if current_side is None:
                current_side = s
            elif s != current_side:
                transitions += 1
                current_side = s
        if transitions > 0:
            crossings += 1
    print(f"  Line y={y_candidate}: {crossings} tracks crossed")
