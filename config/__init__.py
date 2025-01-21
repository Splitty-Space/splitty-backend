import os


#DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:v1996r@localhost:5432/splitty")
SERVER_PORT = os.environ.get("SERVER_PORT", 8000)
