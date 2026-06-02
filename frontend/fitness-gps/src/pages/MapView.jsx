import { useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function MapView() {
  const [coords, setCoords] = useState(null);

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      console.log("Geolocation is not supported by this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;

        console.log("Latitude:", latitude);
        console.log("Longitude:", longitude);

        setCoords({ latitude, longitude });
      },
      (error) => {
        console.error("Error getting location:", error.message);
      }
    );
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-4">
        Map View
      </h1>

      {/* Button */}
      <button
        onClick={handleGetLocation}
        className="mb-4 px-4 py-2 bg-blue-600 text-white rounded"
      >
        Get My Location
      </button>

      {/* Optional debug display */}
      {coords && (
        <p className="mb-4">
          Lat: {coords.latitude}, Lng: {coords.longitude}
        </p>
      )}

      <MapContainer
        center={[42.3601, -71.0589]}
        zoom={13}
        style={{ height: "600px", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      </MapContainer>
    </div>
  );
}

export default MapView;