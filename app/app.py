from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from user import api as user_api

from config import SERVER_PORT


app = FastAPI()
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
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
