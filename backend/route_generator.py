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
from shapely import LineString, convex_hull
import network_graph
import numpy as np

load_dotenv()
VALHALLA_BASE_URL = os.environ.get("VALHALLA_URL")

METERS_IN_A_MILE = 1609.34
EARTH_RADIUS_IN_M = 6371008


def generate_route(G: nx, start: Tuple[float, float], miles: float):

    # start is given as lon, Lat
    # Convert Miles to meters
    target_meters = miles * METERS_IN_A_MILE
    waypoint_meters = target_meters / (3.0 * get_w_pedestrian_boston(miles))
    start_node = find_starting_node(G, start)
    if not start_node:
        raise ValueError(f"Invalid Coordinates Given: {start}")

    waypoint_node, waypoint_angle = find_waypoint(G, start, waypoint_meters)
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
    grade = route_grader(result, target_meters)

    best_grade = grade
    best_result = result
    best_tri_list = tri_list

    acceptable_error = 20.0
    illegal_angles = [waypoint_angle]

    # 360 / 15 = 24. Consider adjusting depedning on number of angle orientations
    while best_grade > acceptable_error and len(illegal_angles) < 12:

        next_waypoint, next_angle = find_waypoint(
            G, start, waypoint_meters, illegal_angles
        )
        if next_waypoint is None:
            break

        illegal_angles.append(next_angle)

        new_tri_list = create_triangle_nodes(G, start, next_waypoint, target_meters)

        node_list = [new_tri_list[0]]
        for node in new_tri_list[1:]:
            if node != node_list[-1]:
                node_list.append(node)

        new_route = valhalla_route(node_list)
        new_result = valhalla_to_geojson(new_route)

        new_grade = route_grader(new_result, target_meters)

        if new_grade < best_grade:
            best_grade = new_grade
            best_result = new_result
            best_tri_list = new_tri_list

    print(
        f"Route distance: "
        f"{result['features'][0]['properties']['distance_meters']:.0f} m"
    )

    print(
        f"Coordinate count: " f"{len(result['features'][0]['geometry']['coordinates'])}"
    )

    print(
        f"Grade: " f"{best_grade}"
    )


    return best_result, best_tri_list


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


def find_waypoint(G: nx, start: Tuple, disatnce: float, skip_angles: List[int] = None):

    if skip_angles is None:
        skip_angles = []

    angles = [a for a in range(0, 360, 15) if a not in skip_angles]
    random.shuffle(angles)

    best_node = None
    best_dis = float("inf")
    best_angle = -1
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
            print(f" -> path_length{err}")
            if err < best_dis:
                best_node = projected_node
                best_dis = err
                best_angle = angle
        except nx.NetworkXNoPath:
            continue
        except Exception as e:
            print(f" -> failed: {e}")
   
    print(
        "Projected:",
        projected_point,
        "Actual:",
        projected_node,
        "Snap:",
        Haversine_Distance(projected_point, projected_node)
    )

    return best_node, best_angle


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
    target_miles = 3
    route, tri_list = generate_route(G, start_point, target_miles)

    visualize_route(route, start_point, tri_list=tri_list)
