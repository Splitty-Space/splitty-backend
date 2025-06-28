import schedule
import time
import asyncio
from datetime import datetime
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from app import orm
from user import api
from user.routers import groups as group_api
from user.routers import expenses as expense_api
from user.routers import user as user_api
from user.routers import activities as activities_api
from config import SERVER_PORT
from utils.send_message import send_message
from user.models import User
from user.api import friends

app = FastAPI()

app.include_router(api.router)
app.include_router(group_api.router)
app.include_router(expense_api.router)
app.include_router(user_api.router)
app.include_router(activities_api.router)

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def weekly_task():
    print("weekly_task -----------------------------------------------------------")
    today = datetime.now()
    print(today.time())

    with orm.Session.begin() as transaction:
        users = transaction.query(User).all()

        for user in users:
            language = user.language

            if language == "en":
                header = "🗓️ Weekly report:"
                owed_header = "🟩 In total, you are owed:"
                owe_header = "🟥 In total you owe:"
            elif language == "ru":
                header = "🗓️ Еженедельный отчёт:"
                owed_header = "🟩 Всего тебе должны:"
                owe_header = "🟥 Всего ты должен:"
            elif language == "ua":
                header = "🗓️ Щотижневий звіт:"
                owed_header = "🟩 Усього тобі повинні:"
                owe_header = "🟥 Усього ти повинен:"

            response = friends(user_id=user.id)

            owe_list = response.meta['total'].get('owe', [])
            owed_list = response.meta['total'].get('owed', [])

            owe_message = ""
            for owe in owe_list:
                owe_message += str(owe.amount) + " " + owe.currency + "\n"

            owed_message = ""
            for owed in owed_list:
                owed_message += str(owed.amount) + " " + owed.currency + "\n"

            send_message(user.id, f"{header}\n{owed_header}\n{owed_message}\n{owe_header}\n{owe_message}")


schedule.every().saturday.at("16:45").do(weekly_task)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)



@app.on_event("startup")
async def startup_event():
    # Запускаем schedule в отдельном потоке, чтобы не блокировать event loop FastAPI
    asyncio.create_task(asyncio.to_thread(run_scheduler))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, ssl_keyfile='./.ssl/key.pem', ssl_certfile='./.ssl/cert.pem')
