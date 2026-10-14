import os

# Load from local_config.py if present (ignored by git for security)
_local_openai = ""
_local_gemini = ""
try:
    from local_config import LOCAL_OPENAI_API_KEY, LOCAL_GEMINI_API_KEY
    _local_openai = LOCAL_OPENAI_API_KEY
    _local_gemini = LOCAL_GEMINI_API_KEY
except ImportError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", _local_openai)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", _local_gemini)

# Cloudflare R2 Storage (S3-compatible, zero egress fees)
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "aivtomation-media")
R2_PUBLIC_URL_PREFIX = os.getenv("R2_PUBLIC_URL_PREFIX", "")

WORK_DIR = os.getenv("WORK_DIR", "/tmp/media_worker")
os.makedirs(WORK_DIR, exist_ok=True)
