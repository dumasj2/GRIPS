import json
import math
import pickle
import random
import time
from dotenv import load_dotenv
import folium
import networkx as nx
from typing import List, Literal, Tuple, Optional
import requests
from sklearn.neighbors import KDTree
import polyline
import os
from shapely import LineString, convex_hull
import network_graph
import numpy as np

load_dotenv()
VALHALLA_BASE_URL = os.environ.get("VALHALLA_URL")
print(VALHALLA_BASE_URL)

METERS_IN_A_MILE = 1609.34
EARTH_RADIUS_IN_M = 6371008


# TODO post processing
# TODO nx.single_source_dijkstra_path_length -> keep bests 3 -> run Vallhalla -> best via grading


def generate_route(G: nx, start: Tuple[float, float], miles: float):

    # start is given as lon, Lat
    # Convert Miles to meters

    target_meters = miles * METERS_IN_A_MILE
    waypoint_meters = target_meters / (3.0 * get_w_pedestrian_boston(miles))
    start_node = find_starting_node(G, start)
    if not start_node:
        raise ValueError(f"Invalid Coordinates Given: {start}")

    waypoints = find_waypoint(G, start, waypoint_meters)
    if waypoints is None:
        raise ValueError(f"Could not find suitable waypoint")

    best_grade = float("inf")
    best_result = None
    best_tri_list = None

    acceptable_error = 20.0

    # 360 / 45 = 8. Consider adjusting depedning on number of angle orientations
    for waypoint in waypoints:

        new_tri_list = create_triangle_nodes(G, start, waypoint)

        new_route = valhalla_route(new_tri_list)
        new_result = valhalla_to_geojson(new_route)

        new_grade = route_grader(new_result, target_meters)

        if new_grade < best_grade:
            best_grade = new_grade
            best_result = new_result
            best_tri_list = new_tri_list

            if new_grade <= acceptable_error:
                break

    print(
        f"Route distance: "
        f"{best_result['features'][0]['properties']['distance_meters']:.0f} m"
    )

    print(
        f"Coordinate count: "
        f"{len(best_result['features'][0]['geometry']['coordinates'])}"
    )

    print(f"Grade: " f"{best_grade}")

    # TODO
    try:
        route_coords = best_result["features"][0]["geometry"]["coordinates"]
        print(len(route_coords))
        trace = valhalla_route(route_coords, "TRACE")
        print(trace.keys())
        print(trace["trip"].keys())
        print(len(trace["trip"]["legs"]))
        print(len(trace["trip"]["legs"][0]["maneuvers"]))

        eta, best_result, score = post_processing(
            best_result, trace, target_meters, G, best_tri_list
        )

    except RuntimeError as e:
        print(f"Trace failed: {e}")

    return best_result, best_tri_list, eta, score


def valhalla_route(
    node_list: List[Tuple[float, float]], type: Literal["ROUTE", "TRACE"] = "ROUTE"
):

    unique_pass = [node_list[0]]
    for i in node_list[1:]:
        if i != unique_pass[-1]:
            unique_pass.append(i)

    payload = {
        "costing": "pedestrian",
    }

    endpoint = ""

    locations = []
    if type == "ROUTE":
        endpoint = "/route"

        payload["costing_options"] = {
            "pedestrian": {
                "use_ferry": 0,
                "use_living_streets": 1,
                "walkway_factor": 0.75,
                "step_penalty": 5,
                "alley_factor": 0.1,
                "u_turn_penalty": 100000,
                "maneuver_penalty": 500,
            }
        }

        payload["units"] = "kilometres"
        for i, node in enumerate(unique_pass):
            di = {"lat": node[1], "lon": node[0]}

            if i == 0 or i == len(unique_pass) - 1:
                di["type"] = "break"
            else:
                di["type"] = "through"

            locations.append(di)
        payload["locations"] = locations
    elif type == "TRACE":
        endpoint = "/trace_route"
        payload["shape_match"] = "walk_or_snap"
        # lon/lat format
        payload["shape"] = [{"lon": pas[0], "lat": pas[1]} for pas in unique_pass]

    else:
        raise RuntimeError("Invaid Request type: Please use ROUTE or TRACE")

    try:
        response = requests.post(
            f"{VALHALLA_BASE_URL}{endpoint}", json=payload, timeout=20
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Valhalla Request failed: {e}")
        print(f"failed route: {VALHALLA_BASE_URL}{endpoint}")
        raise RuntimeError(f"Routing engine unreachable: {e}")


def get_w_pedestrian_boston(dist_in_miles: float):
    match dist_in_miles:
        case m if m >= 3:
            return 1.15
        case n if n >= 2:
            return 1.20
        case l if l >= 1:
            return 1.30
        case _:
            return 1.40


def find_waypoint(G: nx, start: Tuple, distance: float):

    best = {}
    start_node = find_starting_node(G, start)
    print(f" Start Node: {start_node}")
    distances = nx.single_source_dijkstra_path_length(
        G, start_node, cutoff=distance * 1.25, weight="weight"
    )

    for node, dis in distances.items():
        err = abs(dis - distance)
        sector = int(find_bearing(start_node, node) // 45)
        if sector not in best or err < best[sector][1]:
            best[sector] = (node, err)

    return [node for node, _ in best.values()]


def create_triangle_nodes(
    G: nx,
    start: Tuple[float, float],
    end: Tuple[float, float],
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


def project_point(node: Tuple[float, float], angle: float, distance: float):
    lon, lat = node
    ang_rad = math.radians(angle)
    lat_rad = math.radians(lat)
    dlat = math.cos(ang_rad) * (distance / EARTH_RADIUS_IN_M)
    dlon = math.sin(ang_rad) / math.cos(lat_rad) * (distance / EARTH_RADIUS_IN_M)
    return ((lon + math.degrees(dlon)), (lat + math.degrees(dlat)))


def valhalla_to_geojson(valhalla_response: dict):
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


def find_bearing(p1: Tuple[float, float], p2: Tuple[float, float]):
    lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
    lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])

    dlon = lon2 - lon1

    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        dlon
    )

    angle = math.degrees(math.atan2(x, y))
    return (angle + 360) % 360


def route_grader(route: dict, target_distance: float):
    # Criteria: target distance error + connectivity
    actual_distance = route["features"][0]["properties"].get("distance_meters", 0)
    dist_err = (
        abs(
            (target_distance - actual_distance)
            / ((target_distance + actual_distance) / 2)
        )
        * 100
    )

    # Connectivity: use Hull theory
    coords = route["features"][0]["geometry"]["coordinates"]

    lat_to_m = 111320.0
    lon_to_m = 111320 * math.cos(math.radians(np.mean(coords)))
    coords_m = [(cord[0] * lon_to_m, cord[1] * lat_to_m) for cord in coords]

    convex_results = convex_hull(LineString(coords_m)).area
    shape_penalty = 0

    if convex_results <= 0:
        shape_penalty = 100
    else:
        good_area = (actual_distance / (2 * math.pi)) ** 2 * math.pi
        ratio = convex_results / good_area

        shape_penalty = abs(1.0 - min(ratio, 1.0)) * 50

    return dist_err + shape_penalty


# TODO Finish
def post_processing(route: dict, trace: dict, distance: float, G: nx, waypoints: List):

    del waypoints[0]
    del waypoints[-1]

    eta = create_eta(trace)
    smoothed_route = route_optimization(route, G, waypoints)
    route_quality = final_route_quality(smoothed_route, distance, G)
    return eta, smoothed_route, route_quality


def create_eta(trace: dict, speed: Literal["Walking", "Running"] = "Walking"):
    rate = 0
    match speed:
        case "Running":
            rate = 10.0
        case "Walking":
            rate = 5.0
        case _:
            raise ValueError("Invalid speed mode")

    print(f"Type check {type(trace)}")

    raw_length = trace["trip"]["summary"]["length"]

    eta = (raw_length / rate) * 60

    print(f"eta: {eta}")
    return eta
    # return sum(edge.distance / rate for edge in trace["edges"]) * 60


def route_optimization(route: dict, G: nx, waypoints: List):
    coords = route["features"][0]["geometry"]["coordinates"]

    for waypoint in waypoints:
        current_idx = get_current_pos(waypoint, coords)

        window_points = max(
            5,
            int(len(coords) / 27.5)
        )

        start = max(0, current_idx - window_points)
        end = min(len(coords), current_idx + (window_points + 1))

        local_window = coords[start:end]

        # Comparre distance between A - E vs AB - BC - CD - DE
        start_to_end_distance = Haversine_Distance(local_window[0], local_window[-1])
        actual_distance = 0

        for i in range(len(local_window) - 1):
            actual_distance += Haversine_Distance(local_window[i], local_window[i + 1])

        ratio = (
            actual_distance / start_to_end_distance
            if start_to_end_distance > 0
            else float("inf")
        )

        # Analyze each angle bearing
        bearings = []
        for i in range(len(local_window) - 1):
            bearings.append(find_bearing(local_window[i], local_window[i + 1]))

        heading_change = []
        for i in range(len(bearings) - 1):
            diff = abs(bearings[i] - bearings[i + 1])
            diff = min(diff, 360 - diff)
            heading_change.append(diff)

        print(f"heading change {max(heading_change)}")

        if ratio > 1.5:
            start_node = find_starting_node(G, local_window[0])
            end_node = find_starting_node(G, local_window[-1])

            try:
                path = nx.shortest_path(G, start_node, end_node, weight="weight")

                repair_window = list(path)

                coords = coords[:start] + repair_window + coords[end:]
                route["features"][0]["geometry"]["coordinates"] = coords

                print(f"new coords: {coords[:5]}")

                
            except nx.NetworkXNoPath:
                print("network X no path error")
                pass
        elif max(heading_change, default=0) > 90:
            start_node = find_starting_node(G, local_window[0])
            end_node = find_starting_node(G, local_window[-1])

            try:
                bearing  = find_bearing(start_node, end_node)
                length = nx.dijkstra_path_length(G, start_node, end_node, weight="weight")
                half_way = length / 2

                new_w = project_point(start_node, bearing, half_way)
                new_node = find_starting_node(G, new_w)

                path1 = nx.shortest_path(G, start_node, new_node, weight="weight")
                path2 = nx.shortest_path(G, new_node, end_node, weight="weight")

                path = path1[:-1] + path2

                repair_window = list(path)

                coords = coords[:start] + repair_window + coords[end:]
                route["features"][0]["geometry"]["coordinates"] = coords

                # print(f"new coords: {coords[:5]}")
                # print("start:", start_node)
                # print("end:", end_node)
                # print("bearing:", bearing)
                # print("halfway:", half_way)
                # print("projected waypoint:", new_w)
                # print("new node:", new_node)
                # print("old window length:", len(local_window))
                # print("repair length:", len(repair_window))
                
            except nx.NetworkXNoPath:
                print("network X no path error")
                pass

    return route


def get_current_pos(waypoint, route):
    current_closest_idx = 0
    current_closest = Haversine_Distance(route[current_closest_idx], waypoint)

    for current_idx, cord in enumerate(route):
        current_dist = Haversine_Distance(cord, waypoint)

        if current_dist < current_closest:
            current_closest = current_dist
            current_closest_idx = current_idx

    return current_closest_idx


def final_route_quality(route: dict, target_distance: float, G: nx):
    raw_grade = route_grader(route, target_distance)

    coords = route["features"][0]["geometry"]["coordinates"]
    total_penalty = 0.0

    for i in range(len(coords) - 1):
        u = find_starting_node(G, tuple(coords[i]))
        v = find_starting_node(G, tuple(coords[i + 1]))

        if G.has_edge(u, v):
            edge = G[u][v]
        elif G.has_edge(v, u):
            edge = G[v][u]
        else:
            continue

        total_penalty += edge["weight"]

    penalty_score = 20 * (
        total_penalty / route["features"][0]["properties"]["distance_meters"]
    )

    return penalty_score + raw_grade


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
    start_t = time.perf_counter()

    with open("data/network_cache.pkl", "rb") as f:
        G = pickle.load(f)

    start_point = (-71.095, 42.336)  # (lon, lat)
    target_miles = 5.75
    route, tri_list, eta, score = generate_route(G, start_point, target_miles)

    print(f"eta: {eta}")
    print(f"score: {score}")

    visualize_route(route, start_point, tri_list=tri_list)

    end_t = time.perf_counter()

    print(f"Time elasped: {end_t - start_t}")
