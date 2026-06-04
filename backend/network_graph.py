import os
import psycopg2
import networkx as nx
from shapely.wkb import loads
import matplotlib.pyplot as plt
import folium

def load_osm_graph():
    db_url = os.environ.get("DATABASE_URL")
    osmium_box = os.environ.get("OSMIUM_BBOX")

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    query = """SELECT osm_id, name, highway, way,
                ST_Length(ST_Transform(way, 6491)) as length_meters
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
                u = cords[i]
                v = cords[i+1]
                
                segment_weight = length_m / num_cords
                
                G.add_edge( u, v,
                           osm_id=osm_id,
                           name=name or "Unknown",
                           highway_type=highway_type,
                           weight=segment_weight,
                           )
    cursor.close()        
    conn.close()
    
    return G

if __name__ == "__main__":
    graph = load_osm_graph()
    pos = {node: node for node in graph.nodes()}
    plt.figure(figsize=(13,13))
    
    sample_node_a = graph.nodes[100]
    sample_node_b = graph.nodes[500]

    
    
    nx.draw(graph, pos= pos, node_size=0, width= 0.5)
    plt.show()
    