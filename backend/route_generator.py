import math
import random
from dotenv import load_dotenv
import folium
import networkx as nx
from typing import List, Tuple
import requests
from sklearn.neighbors import KDTree
import polyline
import os

import network_graph

load_dotenv()
VALHALLA_BASE_URL = os.environ.get("VALHALLA_URL")

METERS_IN_A_MILE = 1609.34
EARTH_RADIUS_IN_M = 6371008
W_PEDESTRIAN_BOSTON = 1.25


def generate_route(G: nx, start: Tuple[float, float], miles: float):
    # start is given as lon, Lat

    # Convert Miles to meters
    target_meters = miles * METERS_IN_A_MILE
    waypoint_meters = target_meters / (3.0 * W_PEDESTRIAN_BOSTON)
    start_node = find_starting_node(G, start)
    if not start_node:
        raise ValueError(f"Invalid Coordinates Given: {start}")

    waypoint_node = find_waypoint(G, start, waypoint_meters)
    if waypoint_node is None:
        raise ValueError(f"Could not find suitable waypoint")

    tri_list = create_triangle_nodes(G, start, waypoint_node, target_meters)
    print(f"Arc List: {tri_list}")

    node_list = [tri_list[0]]
    for node in tri_list[1:]:
        if node != node_list[-1]:
            node_list.append(node)

    route = valhalla_route(node_list)

    result = valhalla_to_geojson(route)

    print(
        f"Route distance: "
        f"{result['features'][0]['properties']['distance_meters']:.0f} m"
    )

    print(
        f"Coordinate count: " f"{len(result['features'][0]['geometry']['coordinates'])}"
    )

    return result, tri_list


def valhalla_route(node_list: List[Tuple[float, float]]):

    unique_pass = [node_list[0]]
    for i in node_list[1:]:
        if i != unique_pass[-1]:
            unique_pass.append(i)

    locations = []

    for i, node in enumerate(unique_pass):
        dict = {"lat": node[1], "lon": node[0]}
        if i == 0 or i == len(unique_pass) - 1:
            dict["type"] = "break"
        else:
            dict["type"] = "through"

        locations.append(dict)

    payload = {
        "locations": locations,
        "costing": "pedestrian",
        "costing_options": {
            "pedestrian": {
                "use_ferry": 0,
                "use_living_streets": 1,
                "walkway_factor": 0.75,
                "step_penalty": 5,
                "alley_factor": 3,
                "u_turn_penalty": 100000,
            }
        },
        "units": "kilometres",
    }

    try:
        response = requests.post(f"{VALHALLA_BASE_URL}/route", json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Valhalla Request failed: {e}")
        raise RuntimeError(f"Routing engine unreachable: {e}")


def find_waypoint(G: nx, start: Tuple, disatnce: float):

    angles = list(range(0, 360, 20))

    random.shuffle(angles)

    best_node = None
    best_dis = float("inf")

    start_node = find_starting_node(G, start)
    print(f" Start Node: {start_node}")

    for angle in angles:
        projected_point = project_point(start, angle, disatnce)
        projected_node = find_starting_node(G, projected_point)
        print(f" angle= {angle}, projected={projected_point}, node= {projected_node}")

        if projected_node == start_node:
            print(" -> same as start, skipping")
            continue

        try:
            path_length = Haversine_Distance(start_node, projected_node)
            err = abs(path_length - disatnce)
            print(f"  -> path_length{err}")
            if err < best_dis:
                best_node = projected_node
                best_dis = err

        except nx.NetworkXNoPath:
            continue
        except Exception as e:
            print(f"  -> failed: {e}")

    return best_node


def create_triangle_nodes(
    G: nx, start: Tuple[float, float], end: Tuple[float, float], distance: float
):
    dx = end[0] - start[0]
    dy = end[1] - start[1]

    # Direction from start to waypoint (apex)
    line_angle_deg = math.degrees(math.atan2(dx, dy)) % 360
    perp_angle_deg = (line_angle_deg + 90) % 360

    # Chord and flank offset distance
    chord_m = Haversine_Distance(start, end)
    flank_offset = chord_m * 0.35
    
    # Left and right flank points (perpendicular)
    one = (start[0] + dx * 0.33, start[1] + dy * 0.33)
    two = (start[0] + dx * 0.66, start[1] + dy * 0.66)

    left_flank = project_point(one, perp_angle_deg, flank_offset)
    right_flank = project_point(two, (perp_angle_deg + 180) % 360, flank_offset)

    return [
        start,
        find_starting_node(G, left_flank),
        end,
        find_starting_node(G, right_flank),
        start,
    ]


def find_starting_node(G: nx, start: Tuple[float, float]):
    # USING KDTree from sklearn.neighbors
    _, indices = G.graph["spatial_graph"].query([[start[0], start[1]]], k=1)
    nearest_index = indices[0][0]
    return G.graph["spatial_node_ids"][nearest_index]


def build_spatial_index(G: nx):
    node_ids = list(G.nodes())

    node_list = [[n[0], n[1]] for n in node_ids]

    G.graph["spatial_graph"] = KDTree(node_list)
    G.graph["spatial_node_ids"] = node_ids


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
                "properties": {
                    "distance_meters": valhalla_response["trip"]["summary"].get(
                        "length", 0
                    )
                    * 1000
                },
                "geometry": {"type": "LineString", "coordinates": all_cords},
            },
        ],
    }


def Haversine_Distance(p1: Tuple[float, float], p2: Tuple[float, float]):

    lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
    lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin((dlat) / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_IN_M * c


def visualize_route(route: dict, start: Tuple[float, float], tri_list: List = None):
    if not route or not route.get("features"):
        print("No route to visualize.")
        return

    coords = route["features"][0]["geometry"]["coordinates"]
    distance_m = route["features"][0]["properties"].get("distance_meters", 0)

    center_lat = coords[len(coords) // 2][1]
    center_lon = coords[len(coords) // 2][0]

    m = folium.Map(location=[center_lat, center_lon], zoom_start=15)

    # route
    route_latlon = [[c[1], c[0]] for c in coords]
    folium.PolyLine(
        locations=route_latlon,
        color="blue",
        weight=4,
        opacity=0.8,
        tooltip=f"Route: {distance_m:.0f}m",
    ).add_to(m)

    # Start/end marker
    folium.Marker(
        location=[start[1], start[0]],
        popup=f"Start/End\n{distance_m:.0f}m total",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # arcs
    if tri_list:
        for i, point in enumerate(tri_list):
            folium.CircleMarker(
                location=[point[1], point[0]],
                radius=5,
                color="red",
                fill=True,
                fill_opacity=0.7,
                popup=f"Arc point {i}: ({point[0]:.5f}, {point[1]:.5f})",
            ).add_to(m)

    output_path = "route_preview.html"
    m.save(output_path)
    print(f"Map saved to {output_path} — open in browser to view.")
    return m


if __name__ == "__main__":
    G = network_graph.load_osm_graph()
    build_spatial_index(G)

    start_point = (-71.095, 42.336)  # (lon, lat)
    target_miles = 1
    route, tri_list = generate_route(G, start_point, target_miles)

    visualize_route(route, start_point, tri_list=tri_list)
