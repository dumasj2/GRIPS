#!/bin/bash
# Assume data folder and corresponding data already exists
# Ensure executible via chmod
# run via ./run_valhalla.sh {OSM FILE NAME}

DATA_DIR="$(dirname "${BASH_SOURCE[0]}")"

if [ -z "$1" ]; then
    echo "Usage: <Script> <OSM FILE NAME> "
    exit 1
fi 

TARGET_FILE="$1"

if [ ! -f "$DATA_DIR/$TARGET_FILE" ]; then 
    echo "Error: File '$TARGET_FILE' not found in '$DATA_DIR'"
    exit 1
fi

if [ "$(docker ps -a -q -f name=valhalla_service)" ]; then
    docker stop valhalla_service
    docker rm valhalla_service
fi

echo "Valhalla launched on port 8002 using $TARGET_FILE..."
docker run -dt --name valhalla_service \
    -p 8002:8002 \
    -v "$(pwd):/custom_files" \
    ghcr.io/gis-ops/docker-valhalla/valhalla:latest
