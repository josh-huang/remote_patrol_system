import { useEffect, useState } from "react";
import { Box, Typography, Alert, Chip, useTheme } from "@mui/material";
import { GoogleMap, useJsApiLoader, MarkerF, InfoWindowF } from "@react-google-maps/api";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";

const MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY || "";
const containerStyle = { width: "100%", height: "72vh", borderRadius: "6px" };
// Default view centred on Singapore (matches the seed data).
const defaultCenter = { lat: 1.29, lng: 103.85 };

const LiveMapInner = ({ vehicles }) => {
  const [active, setActive] = useState(null);
  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: MAPS_KEY,
  });

  if (!isLoaded) return <Box p="20px">Loading map…</Box>;

  return (
    <GoogleMap
      mapContainerStyle={containerStyle}
      center={defaultCenter}
      zoom={12}
    >
      {vehicles.map((v) => (
        <MarkerF
          key={v.id}
          position={{ lat: v.current_latitude, lng: v.current_longitude }}
          label={{ text: v.plate_number, fontSize: "11px" }}
          onClick={() => setActive(v)}
        />
      ))}
      {active && (
        <InfoWindowF
          position={{
            lat: active.current_latitude,
            lng: active.current_longitude,
          }}
          onCloseClick={() => setActive(null)}
        >
          <div style={{ color: "#111" }}>
            <strong>{active.plate_number}</strong>
            <br />
            Engine: {active.engine_type}
            <br />
            Driver: {active.driver_name || "—"}
            <br />
            Status: {active.maintenance_status}
          </div>
        </InfoWindowF>
      )}
    </GoogleMap>
  );
};

const LiveMap = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [vehicles, setVehicles] = useState([]);

  useEffect(() => {
    const load = () =>
      api.get("/pings/live/").then((r) => setVehicles(r.data));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <Box m="20px">
      <Header
        title="LIVE MAP"
        subtitle="Real-time vehicle positions (auto-refreshes every 5s)"
      />
      <Box display="flex" gap={1} mb={2} flexWrap="wrap">
        {vehicles.map((v) => (
          <Chip key={v.id} label={`${v.plate_number} · ${v.driver_name || "—"}`} />
        ))}
      </Box>

      {MAPS_KEY ? (
        <LiveMapInner vehicles={vehicles} />
      ) : (
        <Box
          backgroundColor={colors.primary[400]}
          borderRadius="6px"
          p="30px"
          height="72vh"
        >
          <Alert severity="info" sx={{ mb: 2 }}>
            Set <code>REACT_APP_GOOGLE_MAPS_API_KEY</code> in{" "}
            <code>frontend/.env</code> to enable the live Google Map. Showing a
            coordinate list fallback below.
          </Alert>
          {vehicles.map((v) => (
            <Typography key={v.id} variant="body1">
              {v.plate_number}: ({v.current_latitude?.toFixed(4)},{" "}
              {v.current_longitude?.toFixed(4)}) — {v.driver_name || "no driver"}
            </Typography>
          ))}
        </Box>
      )}
    </Box>
  );
};

export default LiveMap;
