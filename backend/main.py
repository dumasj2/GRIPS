from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from database import connection
from sqlalchemy import text

import network_graph
import route_generator
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://grips-beta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    lat: float
    lon: float
    miles: float = Field(gt=0, le=10)

graph = None

USE_FAKE_ROUTE = os.getenv("USE_FAKE_ROUTE", "false").lower() == "true"

@app.on_event("startup")
def startup_event():
    global graph

    if USE_FAKE_ROUTE:
        print("USE_FAKE_ROUTE=true, skipping OSM graph loading.")
        graph = None
        return

    try:
        print("Loading OSM graph...")
        graph = network_graph.load_osm_graph()
        network_graph.build_spatial_index(graph)
        print("OSM graph loaded.")
    except Exception as e:
        print(f"Graph failed to load: {e}")
        graph = None

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
    validate_bounds(req.lat, req.lon)

    if USE_FAKE_ROUTE:
        return {
            "route": fake_route_geojson(req.lat, req.lon, req.miles),
            "triangle_points": [],
            "requested": {
                "lat": req.lat,
                "lon": req.lon,
                "miles": req.miles,
            },
        }

    if graph is None:
        raise HTTPException(status_code=503, detail="Graph is not loaded yet.")

    try:
        route_geojson, tri_list = route_generator.generate_route(
            graph,
            (req.lon, req.lat), 
            req.miles
        )

        return {
            "route": route_geojson,
            "triangle_points": tri_list,
            "requested": {
                "lat": req.lat,
                "lon": req.lon,
                "miles": req.miles,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route generation failed: {e}")

#@app.get("/routes/db")
#def get_route_from_db():
    #conn = get_db_connection()
    #cursor = conn.cursor()

    #cursor.execute("""
        #SELECT ST_AsGeoJSON(geom)
        #FROM routes
        #LIMIT 1;
    #""")

    #row = cursor.fetchone()

    #return {
        #"type": "Feature",
        #"geometry": json.loads(row[0]),
        #"properties": {}
    #}