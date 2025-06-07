import schedule
import time
import asyncio
from datetime import datetime
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from user import api
from user.routers import groups as group_api
from user.routers import expenses as expense_api
from user.routers import user as user_api
from user.routers import activities as activities_api
from config import SERVER_PORT
from utils.send_message import send_message

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


def monthly_task():
    print("monthly_task")
    today = datetime.now()
    if today.day == 7:
        print("***********************************************************************")
        print("+++++++++++++++++++++++++++++++++++++++++++++++", today.time())
        send_message(254960854, "Monthly Report")

schedule.every().day.at("19:40").do(monthly_task)


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
