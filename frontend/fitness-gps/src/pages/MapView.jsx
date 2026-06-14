import { useState } from "react";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function MapView() {
  const [distance, setDistance] = useState("");
  const [address, setAddress] = useState("");
  const [coords, setCoords] = useState(null);
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;

        console.log("Latitude:", latitude);
        console.log("Longitude:", longitude);

        setCoords({ latitude, longitude });
        setError("");
      },
      (err) => {
        setError(err.message);
      }
    );
  };

  const handleGenerateRoute = async () => {
    setError("");

    // Frontend validation
    if (!distance || Number(distance) <= 0) {
      setError("Please enter a valid distance.");
      return;
    }

    if (!coords) {
      setError("Please use your location first.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        "https://grips.onrender.com/route",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            distance_miles: Number(distance),
            lat: coords.latitude,
            lng: coords.longitude,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      console.log("Route data:", data);

      setRoute(data);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-4">
        Map View
      </h1>

      <div className="mb-6 flex flex-col gap-4 max-w-md">
        <input
          type="number"
          placeholder="Distance (miles)"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          className="border p-2 rounded"
        />
        <div className="flex items-center gap-2">
          <button
            onClick={handleGetLocation}
            className="px-4 py-2 bg-blue-600 text-white rounded"
          >
            Use My Location
          </button>
          or
          <input
            type="text"
            placeholder="Or enter an address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="border p-2 rounded"
          />
        </div>

        <button
          onClick={handleGenerateRoute}
          disabled={loading}
          className="px-4 py-2 bg-green-600 text-white rounded"
        >
          {loading ? "Generating Route..." : "Generate Route"}
        </button>
      </div>

      {coords && (
        <p className="mb-4">
          Location: {coords.latitude}, {coords.longitude}
        </p>
      )}

      {error && (
        <p className="mb-4 text-red-600">
          Error: {error}
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
        {route && (
          <GeoJSON
            data={route}
            style={{
              color: "blue",
              weight: 5,
              opacity: 0.8,
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}

export default MapView;