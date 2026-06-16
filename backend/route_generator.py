import math
import random
from dotenv import load_dotenv
import networkx as nx
from typing import List, Optional, Tuple
import requests
from sklearn.neighbors import KDTree
import polyline
import os

import network_graph

load_dotenv()
VALHALLA_BASE_URL = os.environ.get("VALHALLA_URL")

METERS_IN_A_MILE = 1609.34
EARTH_RADIUS_IN_M = 6371008
W_PEDESTRIAN_BOSTON = 1.15

def generate_route(G: nx, start: Tuple[float, float], miles: float):
    #start is given as lon, Lat

    # Convert Miles to meters
    target_meters = miles * METERS_IN_A_MILE
    waypoint_meters = target_meters / (2.0 * W_PEDESTRIAN_BOSTON)
    start_node = find_starting_node(G, start)
    if not start_node:
        raise ValueError(f"Invalid Coordinates Given: {start}")

    waypoint_node = find_waypoint(G, start, waypoint_meters)
    if waypoint_node is None:
        raise ValueError(f"Could not find suitable waypoint")

    arc_list = create_arc_nodes(start, waypoint_node, target_meters )

    node_list = []
    for node in arc_list:
        next_node = find_starting_node(G, node)
        node_list.append(next_node)

    route = valhalla_route(node_list)

    return valhalla_to_geojson(route)


def valhalla_route(
    node_list: List[Tuple[float, float]]
):

    locations = []
    for i in range(len(node_list)):
        locations.append({"lat": node_list[i][1], "lon": node_list[i][0]})

    payload = {
        "locations": locations,
        "costing": "pedestrian",
        "costing_options": {
            "pedestrian": {
                "use_ferry": 0,
                "use_living_streets": 1,
                "walkway_factor": 0.75,
                "step_penalty": 5,
            }
        },
        "units": "metres",
    }

    try:
        response = requests.post(f"{VALHALLA_BASE_URL}/route", json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Valhalla Request failed: {e}")
        raise RuntimeError(f"Routing engine unreachable: {e}")

def find_waypoint(G: nx, start: Tuple, disatnce: float):

    angles = [45 * i for i in range(8)]

    random.shuffle(angles)

    best_node = None
    best_dis = float("inf")

    start_node = find_starting_node(G,start)
    print(f" Start Node: {start_node}")

    for angle in angles:
        projected_point = project_point(start, angle, disatnce)
        projected_node = find_starting_node(G, projected_point)
        print(f" angle= {angle}, projected={projected_point}, node= {projected_node}")


        if projected_node == start_node:
            print(" -> same as start, skipping")
            continue

        try:
            path_length = nx.shortest_path_length(G, source=start_node, target=projected_node, weight='weight')
            print(f"  -> path_length{path_length}")
            if path_length < best_dis:
                best_node = projected_node
                best_dis = path_length
        except Exception as e:
            print(f"  -> failed: {e}")

    return best_node

def create_arc_nodes(start: Tuple[float, float], end: Tuple[float, float], length: float):
    NODES_PER_X_METERS = 300
    NODE_MAX = 7
    NODE_MIN = 1

    # Num nodes -> N for Half circle
    num_arc_nodes= int(math.floor(length / NODES_PER_X_METERS)) 
    if num_arc_nodes == 0:
        num_arc_nodes = NODE_MIN
    else:
        num_arc_nodes = min(max(NODE_MIN, num_arc_nodes), NODE_MAX)

    dx, dy = end[0] - start[0], end[1] - start[1]
    num_nodes = num_arc_nodes + 1

    # Angle of X to Y in DEGREER
    line_angle_in_rad= math.atan2(dx,dy)
    line_angle_in_deg = math.degrees(line_angle_in_rad) % 360
    
    # chord distace (distance / Nsin(pi/2n))and radius
    chord_distance = length / (num_nodes * math.sin( math.pi / (2 * num_nodes)))
    radius = chord_distance / 2.0

    # Center Node projected using start, Angle, Radius
    center_project = project_point(start, line_angle_in_deg, radius)

    # Define step angle and start angle (remember 180)
    start_angle = line_angle_in_deg - 180
    step_angle = start_angle / 180

    # calculate and project arc nodes using mid node
    # Iterate angles via angle step
    node_list = [start]
    for i in range(num_arc_nodes):
        next_node = project_point(center_project, step_angle * i, radius)
        node_list.append(next_node)

    # add new start again to arc list
    node_list.append(start)

    return node_list


def find_starting_node(G: nx, start: Tuple[float, float]):
    # USING KDTree from sklearn.neighbors
    if "spatial_graph" not in G.graph or "spatial_node_ids" not in G.graph:
        node_ids = list(G.nodes())

        node_list = [[n[0], n[1]] for n in node_ids]

        G.graph["spatial_graph"] = KDTree(node_list)
        G.graph["spatial_node_ids"] = node_ids

    distance, indices = G.graph["spatial_graph"].query([[start[0], start[1]]], k=1)
    nearest_index = indices[0][0]
    return G.graph["spatial_node_ids"][nearest_index]


def project_point(node: Tuple[float, float], angle: float, distance: float):
    lon, lat = node
    ang_rad = math.radians(angle)
    lat_rad = math.radians(lat)
    dlat = math.cos(ang_rad) * (distance / EARTH_RADIUS_IN_M)
    dlon = math.sin(ang_rad) / math.cos(lat_rad) * (distance / EARTH_RADIUS_IN_M)
    return ((lon + math.degrees(dlon)), (lat + math.degrees(dlat)))


def valhalla_to_geojson(valhalla_response):
    if not valhalla_response or "trip" not in valhalla_response:
        return {}
    
    all_cords = []

    for leg in valhalla_response["trip"]["legs"]:
        if "shape" in leg:
            decoded_line = polyline.decode(leg["shape"], precision=6)
            leg_cords = [[lon, lat] for lat, lon in decoded_line]

            if not all_cords:
                all_cords.extend(leg_cords)
            else:
                all_cords.extend(leg_cords[1:])
    
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                'properties': {
                    "distance_meters": valhalla_response["trip"]["summary"].get("length", 0)
                },
                "geometry": {
                    "type": "LineString", 
                    "coordinates": all_cords
                },
            },
        ],
    }

if __name__ == "__main__":
    G = network_graph.load_osm_graph()
    generate_route(G, (-71.095, 42.336), .5)
