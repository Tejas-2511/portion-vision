import { BrowserRouter, Routes, Route } from "react-router-dom";

import { AppProvider } from "./contexts/AppContext";
import ErrorBoundary from "./components/ErrorBoundary";

import Splash from "./pages/Splash";
import Home from "./pages/Home";
import Preferences from "./pages/Preferences";
import MenuUpload from "./pages/MenuUpload";
import PlateCapture from "./pages/PlateCapture";
import Analysis from "./pages/Analysis";

// Main App component with routing configuration
export default function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Splash />} />
            <Route path="/home" element={<Home />} />
            <Route path="/preferences" element={<Preferences />} />
            <Route path="/menu-upload" element={<MenuUpload />} />
            <Route path="/plate" element={<PlateCapture />} />
            <Route path="/analysis" element={<Analysis />} />
          </Routes>
        </BrowserRouter>
      </AppProvider>
    </ErrorBoundary>
  );
}
