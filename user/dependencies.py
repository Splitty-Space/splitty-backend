import os
import jwt
import hashlib
from fastapi import Header, HTTPException, status

BOT_TOKEN = os.getenv('TOKEN', "7255787922:AAGhh5qrqCEFAivFn6Vc1nIMhr80y1x6oe8")
SECRET_KEY = hashlib.sha256(BOT_TOKEN.encode()).digest()
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

def verify_token(authorization: str = Header(...)):
    if DEBUG:
        # Skip token verification in debug mode
        return
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    token = authorization.split(" ")[1]
    try:
        jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")