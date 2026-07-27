

import { useState, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Marker } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import "leaflet-rotatedmarker";

function MapView() {
  const [distance, setDistance] = useState("");
  const [address, setAddress] = useState("");
  const [coords, setCoords] = useState(null);
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completedRoute, setCompletedRoute] = useState(null);
  const [upcomingRoute, setUpcomingRoute] = useState(null);
  const [routeVersion,setRouteVersion] = useState(0);
  const [progressVersion, setProgressVersion] = useState(0);
  const [heading, setHeading] = useState(0);
  const [previousCoords, setPreviousCoords] = useState(null);
  const [eta, setEta] = useState(null);
  const [safetyScore, setSafetyScore] = useState(null);
  const API_BASE_URL = import.meta.env.VITE_API_URL;

  const arrowIcon = L.divIcon({
    className: "",
    html: `
      <div style="
        font-size: 30px;
        color: blue;
        transform: translate(-50%, -50%);
      ">
        ▲
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });

  useEffect(() => {//constantly updates the user's location on the map
    if (!navigator.geolocation) {
      setError("Geolocation is not supported.");
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        setError("");

        const { latitude, longitude } = position.coords;

        // Calculate heading from previous GPS position
        if (previousCoords) {
          const deltaLat = latitude - previousCoords.latitude;
          const deltaLng = longitude - previousCoords.longitude;

          const angle =
            Math.atan2(deltaLng, deltaLat) * (180 / Math.PI);

          setHeading(angle);
        }

        // Save current location as previous for next update
        setPreviousCoords({
          latitude,
          longitude,
        });

        // Update the user's current position
        setCoords({
          latitude,
          longitude,
        });

        console.log("Live position:", latitude, longitude);
        if (previousCoords) {
          console.log("Heading:", angle);
        }
      },

      (err) => {
        switch (err.code) {
          case err.PERMISSION_DENIED:
            setError(
              "Location access was denied. Please enable location permissions in your browser and try again."
            );
            break;

          case err.POSITION_UNAVAILABLE:
            setError(
              "Unable to determine your current location. Please make sure your device's location services are enabled."
            );
            break;

          case err.TIMEOUT:
            setError(
              "Location request timed out. Please try again."
            );
            break;

          default:
            setError(
              "An unexpected location error occurred."
            );
        }
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

  useEffect(() => {// Updates the route progress whenever the user's location or the route changes
    if (!coords || !route) return;

    updateRouteProgress();

  }, [coords, route]);

  const handleGenerateRoute = async () => {//Gets called when user clicks generate route button
    setError("");

    // Frontend validation
    if (!distance || Number(distance) <= 0 || Number(distance) > 6) {
      setError("Distance must be between 0 and 6 miles.");
      return;
    }
    
    if (!coords) {
      setError("Waiting for GPS location...");
      return;
    }

    setLoading(true);

    try {//The request send to the backend to generate a route
      const controller = new AbortController();

      const timeout = setTimeout(() => {
        controller.abort();
      }, 60000);//waits for a minute for a response from backend 

      const response = await fetch(
        //`${API_BASE_URL}/route`,// Link to backend on the API(Have only 1 uncommented)
        //"http://127.0.0.1:8000/route",// Link to backend on the local machine(Have only 1 uncommented)
        "https://grips.onrender.com/route",// Link to backend endpoint(Have only 1 uncommented)
        {
          method: "POST",// Sends a post request to the backend
          headers: {
            "Content-Type": "application/json",// Specifies requested content type as JSON
          },
          signal: controller.signal,
          body: JSON.stringify({// Expected body of the request
            lat: coords.latitude,
            lon: coords.longitude,
            miles: Number(distance)
          }),
        }
      );
      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);// If the response is not ok, throw an error with the status code
      }

      const data = await response.json();// Parse the response as JSON

      console.log("Route data:", data);// Sends the route data to console for debugging
      
      setEta(data.eta_minutes);
      setSafetyScore(data.safety_score);

      console.log("ETA:", data.eta_minutes);
      console.log("Safety Score:", data.safety_score);
      

      // Check that a route actually exists
      if (!data.route || !data.route.features || data.route.features.length === 0) {
        setError(
          "No route could be found for the selected distance. Try another distance."
        );

        setRoute(null);
        setCompletedRoute(null);
        setUpcomingRoute(null);

        return;
      }

      // Clear any previous errors
      setError("");

      setCompletedRoute(null);
      setUpcomingRoute(null);
      setRoute(data.route);
      setRouteVersion((v) => v + 1);
      

      

    } catch (err) {
      console.error(err);

      if (err.name === "AbortError") {
        setError(
          "The server took too long to respond. Please try again."
        );
      } else {
        setError(
          "Unable to connect to the routing server."
        );
      }

      setRoute(null);
      setCompletedRoute(null);
      setUpcomingRoute(null);
    } finally {
      setLoading(false);
    }
  };

  const updateRouteProgress = () => {//changes the color of the route on the map based on the user's location
    console.log("Updating route progress...");
    if (!route || !route.features || route.features.length === 0) {
      return;
    }
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
    console.log("Closest route point:", closestIndex);
    console.log("Completed points:", completed.length);
    console.log("Upcoming points:", upcoming.length);

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
    setProgressVersion((v) => v + 1);
  };

  const bostonBounds = [//Sets map boundaries
    [42.2926, -71.1537], // southwest
    [42.3794, -71.0363], // northeast
  ];

  return (//This down makes all the UI visuals for the map view page
    <div className="p-6 bg-gray-400 min-h-screen">
      <h1 className="text-3xl text-black ml-22 font-bold mb-4">
        G.R.I.P.S.
      </h1>
      <div className="mb-6 flex flex-col gap-4 max-w-md">
        <h1 className="text-black italic mb-4">
          Global Runner Intelligent Positioning System
        </h1>
        <h1 className="text-black font-bold mb-4">
          How many miles do you want to run?
        </h1>
        <input
          type="number"
          placeholder="Distance (miles)"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          className="border p-2 rounded border-blue-900 text-black"
        />
        <h1 className="text-black font-bold mb-4">
          Starting your run in a different location? Enter an address to change your starting point on the map:
        </h1>
        
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Enter an address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="border p-2 rounded border-blue-900 text-black"
          />
        </div>

        <button
          onClick={handleGenerateRoute}
          disabled={loading}
          className="px-4 py-2 bg-slate-300 text-black rounded"
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
      <div className="border-8 border-blue-900 bg-white rounded-xl overflow-hidden shadow-lg">
        {route && (
        <div className="rounded-xl overflow-hidden shadow-lg">
          <h2 className="text-lg font-bold text-black mb-3">
            Route Information
          </h2>

          <div className="mb-4">
            <p className="text-sm text-gray-600">
              Estimated Time
            </p>

            <p className="text-2xl font-bold text-black">
              {eta !== null ? `${eta} min` : "--"}
            </p>
          </div>

          <div>
            <p className="text-sm text-gray-600 mb-2">
              Route Safety
            </p>

            <div className="w-full bg-gray-200 rounded-full h-4">
              <div
                className="bg-green-500 h-4 rounded-full transition-all duration-500"
                style={{ width: `${safetyScore}%` }}
              />
            </div>

            <p className="mt-2 text-center font-semibold text-green-700">
              {safetyScore}/100
            </p>
        </div>
      </div>
      )}
      <MapContainer
        key={routeVersion}//regenerates the map when the route changes
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
          <Marker
            position={[
              coords.latitude,
              coords.longitude,
            ]}
            icon={arrowIcon}
            rotationAngle={heading}
            rotationOrigin="center"
          />
        )}
        {completedRoute && (
          <GeoJSON
            key={`comnpleted-${progressVersion}`}
            data={completedRoute}
            style={{
              color: "grey",
              weight: 4,
            }}
          />
        )}

        {upcomingRoute && (
          <GeoJSON
            key={`upcoming-${progressVersion}`}
            data={upcomingRoute}
            style={{
              color: "blue",
              weight: 4,
            }}
          />
        )}
      </MapContainer>
      </div>
    </div>
  );
}

export default MapView;