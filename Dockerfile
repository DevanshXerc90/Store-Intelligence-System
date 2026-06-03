FROM python:3.12-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8n model to avoid runtime download
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copy source code
COPY src/ src/
COPY tests/ tests/
COPY data/sales/ data/sales/

# Create data directories
RUN mkdir -p data/db data/videos

# Default command (overridden by docker-compose)
CMD ["python", "-m", "src.api.main"]
