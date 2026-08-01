import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip("'\""))


def get_database_config():
    """
    Returns database configuration dictionary.
    Supports 'sqlite' and 'postgres'.
    """
    database_url = os.getenv("DATABASE_URL")
    db_engine = os.getenv("DB_ENGINE", "").lower()

    if database_url and ("postgres" in database_url or "postgresql" in database_url):
        dsn = database_url
        if dsn.startswith("postgres://"):
            dsn = dsn.replace("postgres://", "postgresql://", 1)
        return {"engine": "postgres", "kwargs": {"dsn": dsn}}


    if db_engine in ("postgres", "postgresql") or (not db_engine and os.getenv("POSTGRES_HOST")):
        return {
            "engine": "postgres",
            "kwargs": {
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": os.getenv("POSTGRES_PORT", "5432"),
                "dbname": os.getenv("POSTGRES_DB", "iot_dashboard"),
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
            },
        }


    db_path = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "iot_dashboard.db"))
    return {
        "engine": "sqlite",
        "database": db_path,
    }


def get_database_connection_kwargs():
    return get_database_config().get("kwargs", {})


