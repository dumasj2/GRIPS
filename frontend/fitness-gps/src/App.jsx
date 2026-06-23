import { BrowserRouter, Routes, Route } from "react-router-dom";

import MapView from "./pages/MapView";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapView />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;