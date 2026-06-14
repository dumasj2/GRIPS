from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import connection
from sqlalchemy import text

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://grips-beta.vercel.app/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    lat: float
    lng: float
    distance_miles: float

def validate_bounds(lat, lng):
    if not (42.30 <= lat <= 42.37 and -71.15 <= lng <= -71.05):
        raise HTTPException(status_code=422, detail="Outside supported area")
    
def fake_route_geojson(lat, lng, distance_miles):
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [lng, lat],
                    [lng + 0.005, lat + 0.005],
                    [lng + 0.01, lat],
                    [lng, lat],
                ],
            },
            "properties": {
                "distance_miles": distance_miles,
                "score": 75,
                "eta_minutes": round(distance_miles * 10),
            },
        }],
    }


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

@app.post("/route")
def create_route(req: RouteRequest):
    if req.distance_miles <= 0:
        raise HTTPException(status_code=422, detail="Distance must be greater than 0.")

    # temporary fake loop near the input point
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [req.lng, req.lat],
                        [req.lng + 0.005, req.lat + 0.005],
                        [req.lng + 0.01, req.lat],
                        [req.lng, req.lat],
                    ],
                },
                "properties": {
                    "score": 75,
                    "eta_minutes": round(req.distance_miles * 10),
                    "distance_miles": req.distance_miles,
                },
            }
        ],
    }

    return geojson