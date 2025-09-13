import schedule
import time
import asyncio
from datetime import datetime
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from app import orm
from user import api
from user.routers import auth as auth_api
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
app.include_router(auth_api.router)
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

            print("user.username = ", user.username)

            if language == "en":
                header = "🗓️ Weekly report:"
                owed_header = "🟩 In total, you are owed:"
                owe_header = "🟥 In total you owe:"
                footer = "For more details, check the app 👇"
                noDebt = "You have no debts and no one owes you anything 🙌"
            elif language == "ru":
                header = "🗓️ Еженедельный отчёт:"
                owed_header = "🟩 Всего тебе должны:"
                owe_header = "🟥 Всего ты должен:"
                footer = "Более подробно смотри в приложении 👇"
                noDebt = "У тебя нет долгов и тебе никто не должен 🙌"
            elif language == "ua":
                header = "🗓️ Щотижневий звіт:"
                owed_header = "🟩 Усього тобі повинні:"
                owe_header = "🟥 Усього ти повинен:"
                footer = "Детальніше дивись у додатку 👇"
                noDebt = "У тебе немає боргів і тобі ніхто не винен 🙌"

            response = friends(user_id=user.id)

            owe_list = response.meta['total'].get('owe', [])
            owed_list = response.meta['total'].get('owed', [])

            owe_message = ""
            for owe in owe_list:
                print("owe.amount = ", owe.amount)
                print("owe.currency = ", owe.currency)
                owe_message += str(owe.amount) + " " + owe.currency + "\n"
                print("owe_message = ", owe_message)

            owed_message = ""
            for owed in owed_list:
                print("owed.amount == ", owed.amount)
                print("owed.currency == ", owed.currency)
                owed_message += str(owed.amount) + " " + owed.currency + "\n"
                print("owed_message == ", owed_message)

            final_message = header + "\n\n"

            print("owed_message === ", owed_message)
            print("owe_message === ", owe_message)

            if owed_message:
                final_message += owed_header + "\n" + owed_message + "\n"

            if owe_message:
                final_message += owe_header + "\n" + owe_message + "\n"

            if owed_message or owe_message:
                final_message += footer
            else:
                final_message = header + noDebt

            print("final_message === ", final_message)

            send_message(user.id, final_message)


schedule.every().saturday.at("14:40").do(weekly_task)


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
