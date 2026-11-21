import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Alert, Box, Button, CssBaseline, ThemeProvider } from "@mui/material";
import { ColorModeContext, useMode } from "./theme";
import { useAuth } from "./context/AuthContext";

import Topbar from "./scenes/global/Topbar";
import Sidebar from "./scenes/global/Sidebar";
import Login from "./scenes/login";
import Dashboard from "./scenes/dashboard";
import Vehicles from "./scenes/vehicles";
import Locations from "./scenes/locations";
import Guards from "./scenes/guards";
import RoutePlanning from "./scenes/routing";
import LiveMap from "./scenes/livemap";
import Alerts from "./scenes/alerts";
import Incidents from "./scenes/incidents";
import Records from "./scenes/records";
import Messages from "./scenes/messages";
import Reports from "./scenes/reports";
import Assistant from "./scenes/assistant";

const PAGES = [
  ["/", Dashboard],
  ["/assistant", Assistant],
  ["/live-map", LiveMap],
  ["/route-planning", RoutePlanning],
  ["/alerts", Alerts],
  ["/incidents", Incidents],
  ["/messages", Messages],
  ["/vehicles", Vehicles],
  ["/locations", Locations],
  ["/guards", Guards],
  ["/records", Records],
  ["/reports", Reports],
];

// The dashboard is for command-centre admins; guards use the duty-phone app.
const RequireAdmin = ({ children }) => {
  const { user, loading, logout } = useAuth();
  const location = useLocation();
  if (loading) return <Box p="40px">Loading…</Box>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (user.role !== "admin") {
    return (
      <Box p="40px" maxWidth={560}>
        <Alert severity="info" action={<Button onClick={logout}>Sign out</Button>}>
          This dashboard is for the command centre. Patrol officers should use the duty-phone app.
        </Alert>
      </Box>
    );
  }
  return children;
};

function App() {
  const [theme, colorMode] = useMode();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <div className="app">
          {isAdmin && <Sidebar />}
          <main className="content">
            {isAdmin && <Topbar />}
            <Routes>
              <Route path="/login" element={<Login />} />
              {PAGES.map(([path, Page]) => (
                <Route
                  key={path}
                  path={path}
                  element={
                    <RequireAdmin>
                      <Page />
                    </RequireAdmin>
                  }
                />
              ))}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export default App;
