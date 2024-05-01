import os


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
SERVER_PORT = os.environ.get("SERVER_PORT", 8000)
