FROM ghcr.io/valhalla/valhalla-scripted:latest

COPY boston.osm.pbf /custom_files/boston.osm.pbf

ENV use_tiles_ignore_pbf=False
ENV build_elevation=False
ENV build_admins=False
ENV build_time_zones=False
ENV server_threads=1
ENV serve_tiles=True
ENV build_tar=True

EXPOSE 8002