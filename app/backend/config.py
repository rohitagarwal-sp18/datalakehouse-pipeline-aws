import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://appuser:password@localhost:5432/ecommerce",
)
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 1440  # 24 hours
