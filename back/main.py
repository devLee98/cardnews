from fastapi import FastAPI
from controller import cardnews, items

app = FastAPI()

app.include_router(items.router)
app.include_router(cardnews.router)


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

