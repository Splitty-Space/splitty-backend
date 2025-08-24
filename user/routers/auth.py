import jwt
import os
import fastapi
import hashlib
from fastapi import HTTPException
from init_data_py import InitData
from user.dtos import (AuthData)

router = fastapi.APIRouter()

BOT_TOKEN = os.getenv('TOKEN', "7255787922:AAGhh5qrqCEFAivFn6Vc1nIMhr80y1x6oe8")
SECRET_KEY = hashlib.sha256(BOT_TOKEN.encode()).digest()
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

@router.post("/auth")
async def telegram_auth(auth: AuthData) -> dict[str, str]:
    if DEBUG:
        # Skip auth in debug mode
        return {"token": "debug-token"}

    print("auth = ", auth.init_data_raw)

    init_data = InitData.parse(auth.init_data_raw)

    print("init_data = ", init_data)

    print("BOT_TOKEN = ", BOT_TOKEN)

    is_valid = init_data.validate(
        bot_token=BOT_TOKEN,
        lifetime=3600,
    )

    print("is_valid = ", is_valid)

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth data")

    token = jwt.encode({'init_data': auth.init_data_raw}, SECRET_KEY, algorithm='HS256')

    return {"token": token}
