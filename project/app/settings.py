"""All configuration in one place, read from environment variables."""
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://course:course@localhost:5432/course_test")
POOL_MIN_SIZE = int(os.environ.get("POOL_MIN_SIZE", "1"))
POOL_MAX_SIZE = int(os.environ.get("POOL_MAX_SIZE", "5"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "3"))   # retry cap for deadlock / serialization errors
