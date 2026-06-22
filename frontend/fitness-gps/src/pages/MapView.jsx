import { useState, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, CircleMarker } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function MapView() {
  const [distance, setDistance] = useState("");
  const [address, setAddress] = useState("");
  const [coords, setCoords] = useState(null);
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {//constantly updates the user's location on the map
    if (!navigator.geolocation) {
      setError("Geolocation is not supported.");
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude } = position.coords;

        setCoords({
          latitude,
          longitude,
        });

        console.log(
          "Live position:",
          latitude,
          longitude
        );
      },

      (err) => {
        setError(err.message);
      },

      {
        enableHighAccuracy: true,
        maximumAge: 1000,
        timeout: 5000,
      }
    );

    return () => {
      navigator.geolocation.clearWatch(watchId);
    };
  }, []);

  const handleGenerateRoute = async () => {
    setError("");

    // Frontend validation
    if (!distance || Number(distance) <= 0) {
      setError("Please enter a valid distance.");
      return;
    }
    
    if (!coords) {
      setError("Waiting for GPS location...");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        "https://grips.onrender.com/route",// Link to backend endpoint
        {
          method: "POST",// Sends a post request to the backend
          headers: {
            "Content-Type": "application/json",// Specifies requested content type as JSON
          },
          body: JSON.stringify({// Expected body of the request
            distance_miles: Number(distance),
            lat: coords.latitude,
            lng: coords.longitude,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);// If the response is not ok, throw an error with the status code
      }

      const data = await response.json();// Parse the response as JSON

      console.log("Route data:", data);// Sends the route data to console for debugging

      setRoute(data);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (//This down makes all the UI visuals for the map view page
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

        Starting your run in a different location? Enter an address to update your starting point on the map:
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Enter an address"
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
        center={[42.3601, -71.0589]}// When first going to the map view page, the map will be centered on Central Boston
        zoom={13}
        style={{ height: "600px", width: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {coords && (
          <CircleMarker
            center={[
              coords.latitude,
              coords.longitude,
            ]}
            radius={8}
            pathOptions={{
              color: "blue",
              fillColor: "blue",
              fillOpacity: 1,
            }}
          />
        )}
        {route && (
          <GeoJSON// Renders the route
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