from fastapi import FastAPI
import uvicorn
import ssl
from fastapi.middleware.cors import CORSMiddleware

from user import api
from user.routers import groups as group_api
from user.routers import expenses as expense_api
from user.routers import user as user_api
from config import SERVER_PORT


app = FastAPI()

app.include_router(api.router)
app.include_router(group_api.router)
app.include_router(expense_api.router)
app.include_router(expense_api.router)
app.include_router(user_api.router)

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, ssl_keyfile='./.ssl/key.pem', ssl_certfile='./.ssl/cert.pem')
