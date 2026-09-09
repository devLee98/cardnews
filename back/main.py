from fastapi import FastAPI
from controller import cardnews

app = FastAPI()

app.include_router(cardnews.router)


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

