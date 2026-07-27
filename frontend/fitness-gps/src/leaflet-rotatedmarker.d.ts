import "leaflet";

declare module "leaflet" {
  interface MarkerOptions {
    rotationAngle?: number;
    rotationOrigin?: string;
  }
}