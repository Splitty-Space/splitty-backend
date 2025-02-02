import os
#from dotenv import load_dotenv

#load_dotenv()

#SECRET_KEY = os.getenv('REFERRAL_SECRET_KEY')
SECRET_KEY = os.environ.get('REFERRAL_SECRET_KEY')

DATABASE_URL = "sqlite:///db.sqlite3"
# DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:v1996r@localhost:5432/splitty")
SERVER_PORT = os.environ.get("SERVER_PORT", 8000)
