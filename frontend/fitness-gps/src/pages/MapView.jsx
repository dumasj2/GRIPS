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
  const [completedRoute, setCompletedRoute] = useState(null);
  const [upcomingRoute, setUpcomingRoute] = useState(null);

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

  useEffect(() => {
    if (!coords || !route) return;

    updateRouteProgress();

  }, [coords, route]);

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

  const updateRouteProgress = () => {

    const coordinates =
      route.features[0].geometry.coordinates;

    // Find the route point closest to the user
    let closestIndex = 0;
    let shortestDistance = Infinity;

    coordinates.forEach((point, index) => {

      const lng = point[0];
      const lat = point[1];

      const distance =
        Math.sqrt(
          (lat - coords.latitude) ** 2 +
          (lng - coords.longitude) ** 2
        );

      if (distance < shortestDistance) {

        shortestDistance = distance;

        closestIndex = index;
      }
    });

    const completed = coordinates.slice(
      0,
      closestIndex + 1
    );

    const upcoming = coordinates.slice(
      closestIndex
    );

    setCompletedRoute({
      type: "FeatureCollection",

      features: [
        {
          type: "Feature",

          geometry: {
            type: "LineString",

            coordinates: completed,
          },
        },
      ],
    });

    setUpcomingRoute({
      type: "FeatureCollection",

      features: [
        {
          type: "Feature",

          geometry: {
            type: "LineString",

            coordinates: upcoming,
          },
        },
      ],
    });
  };

  const bostonBounds = [
    [42.2926, -71.1537], // southwest
    [42.3794, -71.0363], // northeast
  ];

  return (//This down makes all the UI visuals for the map view page
    <div className="p-6 bg-gray-500 min-h-screen">
      <h1 className="text-3xl text-blue-900 ml-22 font-bold mb-4">
        Map View
      </h1>

      <div className="mb-6 flex flex-col gap-4 max-w-md">
        <input
          type="number"
          placeholder="Distance (miles)"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          className="border p-2 rounded border-blue-900 text-blue-900"
        />
        <h1 className="text-blue-900 font-bold mb-4">
          Starting your run in a different location? Enter an address to update your starting point on the map:
        </h1>
        
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Enter an address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="border p-2 rounded border-blue-900 text-blue-900"
          />
        </div>

        <button
          onClick={handleGenerateRoute}
          disabled={loading}
          className="px-4 py-2 bg-slate-300 text-blue-900 rounded"
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
      <div className="border-8 border-blue-900 rounded-xl overflow-hidden shadow-lg">
      <MapContainer
        center={[42.336, -71.095]}
        zoom={15}
        minZoom={13}
        maxBounds={bostonBounds}
        maxBoundsViscosity={1.0}
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
        {completedRoute && (
          <GeoJSON
            data={completedRoute}
            style={{
              color: "green",
              weight: 6,
            }}
          />
        )}

        {upcomingRoute && (
          <GeoJSON
            data={upcomingRoute}
            style={{
              color: "blue",
              weight: 6,
            }}
          />
        )}
      </MapContainer>
      </div>
    </div>
  );
}

export default MapView;