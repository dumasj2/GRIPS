import os
import psycopg2
import networkx as nx
from shapely.wkb import loads
import matplotlib.pyplot as plt
from  shapely import LineString
from geopy.distance import geodesic
from dotenv import load_dotenv
from sklearn.neighbors import KDTree
import pickle


load_dotenv()

def load_osm_graph():
    db_url = os.environ.get("DATABASE_URL")

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    query = """SELECT osm_id, name, highway, 
                ST_AsHEXEWKB(ST_Transform(way, 4326)) as way,
                ST_Length(ST_Transform(way, 6492)) as length_meters
            FROM planet_osm_line
            WHERE highway is not NULL
            """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    G = nx.Graph()
    
    for osm_id, name, highway_type, wkb_geometry, length_m in rows:
        geom = loads(wkb_geometry, hex=True)
        if geom.geom_type == 'LineString':
            cords = list(geom.coords)
            num_cords = len(cords) - 1
            
            for i in range(num_cords):
                u = (round(cords[i][0],6), round(cords[i][1],6))
                v = (round(cords[i+1][0],6), round(cords[i+1][1],6))

                segment_length = geodesic((u[1], u[0]), (v[1], v[0])).meters

                penalty = 1.0
                
                if highway_type in ['footway', 'path', 'pedestrian', 'living_street', 'residential']:
                    #reward
                    penalty = .75
                elif highway_type in ['primary', 'secondary', 'trunk']:
                    # Severe penalty
                    penalty = 5.0
                elif highway_type in ['steps']:
                    # Moderate penalty
                    penalty = 2.0
                
                adjusted_weight = segment_length * penalty
                
                G.add_edge( u, v,
                           osm_id=osm_id,
                           name=name or "Unknown",
                           highway_type=highway_type,
                           distance_in_meters = segment_length,
                           weight=adjusted_weight,
                           )
    cursor.close()        
    conn.close()

    build_spatial_index(G)

    return G

def build_spatial_index(G: nx):
    node_ids = list(G.nodes())

    node_list = [[n[0], n[1]] for n in node_ids]

    G.graph["spatial_graph"] = KDTree(node_list)
    G.graph["spatial_node_ids"] = node_ids

def backend_export(G: nx, filepath: str = "data/network_cache.pkl"):
    #pickle
    os.makedirs(os.path.dirname(filepath), exist_ok= True)
    with open(filepath, "wb") as file:
        pickle.dump(G, file, protocol=5)


if __name__ == "__main__":
    graph = load_osm_graph()    
    pos = {node: node for node in graph.nodes()}
    plt.figure(figsize=(13,13))
    
    osm_box =  os.environ.get("OSMIUM_BBOX")
    cords = list(map(float, osm_box.split(",")))
    center = ((cords[1] + cords[3]) /2, (cords[0] + cords[2]) / 2)
    calc_dist = geodesic(center, (cords[1], cords[0])).meters
    print(f" Geopy Results: Origin Point {center} & Distace from center to edge: {calc_dist}")

    nx.draw(graph, pos= pos, node_size=0, width= 0.5)
    plt.show()

    backend_export(graph)
    