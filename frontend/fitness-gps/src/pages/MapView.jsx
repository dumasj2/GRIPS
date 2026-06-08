import { useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function MapView() {
  const [distance, setDistance] = useState("");
  const [address, setAddress] = useState("");
  const [coords, setCoords] = useState(null);

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      console.log("Geolocation not supported");
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
        console.error(error);
      }
    );
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-4">
        Map View
      </h1>

      {/* Input Form */}
      <div className="mb-6 flex flex-col gap-4 max-w-md">
        <input
          type="number"
          placeholder="Distance (miles)"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          className="border p-2 rounded"
        />

        <button
          onClick={handleGetLocation}
          className="px-4 py-2 bg-blue-600 text-white rounded"
        >
          Use My Location
        </button>

        <input
          type="text"
          placeholder="Or enter an address"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          className="border p-2 rounded"
        />
      </div>

      {coords && (
        <p className="mb-4">
          Current Location: {coords.latitude}, {coords.longitude}
        </p>
      )}

      <MapContainer
        center={[42.3601, -71.0589]}
        zoom={13}
        style={{ height: "600px", width: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      </MapContainer>
    </div>
  );
}

export default MapView;