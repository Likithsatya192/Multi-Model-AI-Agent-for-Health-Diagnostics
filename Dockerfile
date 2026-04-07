# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (e.g., Tesseract for OCR if needed)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
# Install CPU-only PyTorch to reduce image size (saves ~2GB)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD sh -c "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"
