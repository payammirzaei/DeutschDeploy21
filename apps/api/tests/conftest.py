import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-that-is-longer-than-thirty-two-characters")
os.environ.setdefault("APP_BOOTSTRAP_EMAIL", "tester@example.com")
os.environ.setdefault("APP_BOOTSTRAP_PASSWORD", "local-test-password-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/deutschdeploy_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
