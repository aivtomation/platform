# Hugging Face Spaces Docker Media Worker (24/7 Failover)
FROM python:3.10-slim

# 1. Install system dependencies: FFmpeg, libass, fontconfig, and core fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass-dev \
    fontconfig \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy fonts to system directory and refresh fontconfig cache
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY fonts/*.ttf /usr/share/fonts/truetype/custom/
RUN fc-cache -fv

# 3. Configure non-root user (UID 1000 required for Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# 4. Install Python dependencies
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy application source code
COPY --chown=user:user . .

# 6. Hugging Face Spaces default port
ENV PORT=7860
EXPOSE 7860

# 7. Run FastAPI app and background polling engine
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
