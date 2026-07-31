from fastapi import FastAPI
from controller import items

app = FastAPI()

app.include_router(items.router)


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

