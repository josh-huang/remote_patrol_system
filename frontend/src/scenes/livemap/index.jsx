import { useEffect, useMemo, useState } from "react";
import { Box, Chip, Typography } from "@mui/material";
import Header from "../../components/Header";
import Panel from "../../components/Panel";
import RouteMap, { currentStops, routesFromStops } from "../../components/RouteMap";
import { colorFor, fetchList } from "../../api/resources";

const LiveMap = () => {
  const [vehicles, setVehicles] = useState([]);
  const [sites, setSites] = useState([]);
  const [stops, setStops] = useState([]);
  const [showRoutes, setShowRoutes] = useState(true);

  useEffect(() => {
    const load = () => {
      fetchList("/vehicles/").then(setVehicles);
      fetchList("/locations/", { is_active: true }).then(setSites);
      fetchList("/plans/", { status: "active" }).then((plans) => setStops(currentStops(plans)));
    };
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const index = useMemo(() => Object.fromEntries(vehicles.map((v, i) => [v.id, i])), [vehicles]);
  const vehicleColor = (id) => colorFor(index[id] ?? 0);
  // Only the part of each route still to drive.
  const remaining = stops.filter((s) => !s.is_visited);

  return (
    <Box m="20px">
      <Header title="LIVE MAP" subtitle="Real-time vehicle positions and remaining routes (refreshes every 5s)" />
      <Box display="flex" gap={1} mb={2} flexWrap="wrap" alignItems="center">
        {vehicles.map((v) => (
          <Chip
            key={v.id}
            sx={{ borderColor: vehicleColor(v.id), borderWidth: 2 }}
            variant="outlined"
            label={`${v.plate_number} · ${v.driver_name || "—"} · next: ${v.next_location?.name || "—"}${
              v.last_seen_at ? ` · ${new Date(v.last_seen_at).toLocaleTimeString()}` : ""
            }`}
          />
        ))}
        <Chip
          label={showRoutes ? "Hide routes" : "Show routes"}
          onClick={() => setShowRoutes(!showRoutes)}
          color="secondary"
        />
      </Box>
      <Panel>
        <RouteMap
          height="70vh"
          sites={sites}
          vehicles={vehicles.map((v) => ({ ...v, color: vehicleColor(v.id) }))}
          routes={showRoutes ? routesFromStops(remaining, vehicleColor) : []}
        />
        <Typography variant="caption" display="block" mt={1}>
          Red sites have an active emergency alarm. Positions come from the duty phones' GPS pings.
        </Typography>
      </Panel>
    </Box>
  );
};

export default LiveMap;
