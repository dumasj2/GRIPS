import { useState } from "react";
import { useNavigate } from "react-router-dom";

function Home() {
  const [destination, setDestination] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();

    navigate("/map", {
      state: { destination }
    });
  };

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">
        GRIPS Route Planner
      </h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          placeholder="Enter destination"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          className="border p-2 w-full"
        />

        <button
          type="submit"
          className="bg-blue-500 text-white px-4 py-2 rounded"
        >
          Generate Route
        </button>
      </form>
    </div>
  );
}

export default Home;