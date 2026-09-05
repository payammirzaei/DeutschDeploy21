import os
import sys
from pathlib import Path

# Windows + psycopg need SelectorEventLoop; do not impose this on Linux CI.
if sys.platform.startswith("win"):
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-that-is-longer-than-thirty-two-characters")
os.environ.setdefault("APP_BOOTSTRAP_EMAIL", "tester@example.com")
os.environ.setdefault("APP_BOOTSTRAP_PASSWORD", "local-test-password-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/deutschdeploy_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("MEDIA_STORAGE_BACKEND", "filesystem")
os.environ.setdefault("MEDIA_ROOT", str(Path("/tmp/dd21-test-media")))
os.environ.setdefault("SPEECH_TRANSCRIPTION_PROVIDER", "mock")
