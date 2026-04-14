FROM python:3.10-slim

WORKDIR /app

# System deps: Tesseract OCR + OpenGL
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (own layer — cached unless torch version changes)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Speed optimization: bake embedding model into image ──────────────────────
# Pre-downloads all-MiniLM-L6-v2 during build → zero download latency at startup
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
print('Embedding model cached.')"

# After model is baked in, disable ALL HuggingFace network calls at runtime.
# This eliminates the 10+ HTTP HEAD requests that caused 504 on Render.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/torch/sentence_transformers

# Copy application code (after deps — keeps layer cache valid on code-only changes)
COPY . .

EXPOSE 8000

# Single worker on free tier (512MB RAM). Increase to 2 on paid plans.
CMD sh -c "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
