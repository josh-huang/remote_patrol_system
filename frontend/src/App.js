import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { CssBaseline, ThemeProvider, Box } from "@mui/material";
import { ColorModeContext, useMode } from "./theme";
import { useAuth } from "./context/AuthContext";

import Topbar from "./scenes/global/Topbar";
import Sidebar from "./scenes/global/Sidebar";
import Login from "./scenes/login";
import Dashboard from "./scenes/dashboard";
import Vehicles from "./scenes/vehicles";
import Locations from "./scenes/locations";
import RoutePlanning from "./scenes/routing";
import LiveMap from "./scenes/livemap";
import Incidents from "./scenes/incidents";
import Reports from "./scenes/reports";
import Assistant from "./scenes/assistant";

const RequireAuth = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Box p="40px">Loading…</Box>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
};

function App() {
  const [theme, colorMode] = useMode();
  const { user } = useAuth();

  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <div className="app">
          {user && <Sidebar />}
          <main className="content">
            {user && <Topbar />}
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route
                path="/"
                element={
                  <RequireAuth>
                    <Dashboard />
                  </RequireAuth>
                }
              />
              <Route
                path="/assistant"
                element={
                  <RequireAuth>
                    <Assistant />
                  </RequireAuth>
                }
              />
              <Route
                path="/vehicles"
                element={
                  <RequireAuth>
                    <Vehicles />
                  </RequireAuth>
                }
              />
              <Route
                path="/locations"
                element={
                  <RequireAuth>
                    <Locations />
                  </RequireAuth>
                }
              />
              <Route
                path="/route-planning"
                element={
                  <RequireAuth>
                    <RoutePlanning />
                  </RequireAuth>
                }
              />
              <Route
                path="/live-map"
                element={
                  <RequireAuth>
                    <LiveMap />
                  </RequireAuth>
                }
              />
              <Route
                path="/incidents"
                element={
                  <RequireAuth>
                    <Incidents />
                  </RequireAuth>
                }
              />
              <Route
                path="/reports"
                element={
                  <RequireAuth>
                    <Reports />
                  </RequireAuth>
                }
              />
            </Routes>
          </main>
        </div>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export default App;
