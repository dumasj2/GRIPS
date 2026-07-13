FROM ghcr.io/gis-ops/docker-valhalla/valhalla:latest

COPY boston.osm.pbf /custom_files/boston.osm.pbf

ENV use_tiles_ignore_pbf=False
ENV build_elevation=False
ENV build_admins=True
ENV build_time_zones=True
ENV server_threads=1

EXPOSE 8002