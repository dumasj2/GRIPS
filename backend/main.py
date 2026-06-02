from fastapi import FastAPI
from database import connection
from sqlalchemy import text

app = FastAPI()


@app.get("/")
def root():
    return {"message": "GRIPS backend running"}


@app.get("/health")
def health():

    return {
        "status": "ok"
    }


@app.get("/ping")
def ping():

    return {
        "message": "pong"
    }


@app.get("/routes")
def get_routes():

    result = connection.execute(text("SELECT * FROM routes;"))

    routes = []

    for row in result:
        routes.append(dict(row._mapping))

    return routes