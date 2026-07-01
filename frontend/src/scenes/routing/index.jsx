import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  OutlinedInput,
  Select,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import RouteOutlinedIcon from "@mui/icons-material/RouteOutlined";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";

const ALGORITHMS = [
  { value: "dijkstra", label: "Dijkstra" },
  { value: "bellman_ford", label: "Bellman-Ford" },
  { value: "floyd_warshall", label: "Floyd-Warshall" },
];

const RoutePlanning = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [vehicles, setVehicles] = useState([]);
  const [locations, setLocations] = useState([]);
  const [selectedVehicles, setSelectedVehicles] = useState([]);
  const [selectedLocations, setSelectedLocations] = useState([]);
  const [algorithm, setAlgorithm] = useState("dijkstra");
  const [planName, setPlanName] = useState("New Patrol Plan");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/vehicles/").then((r) => setVehicles(r.data.results || r.data));
    api.get("/locations/").then((r) => setLocations(r.data.results || r.data));
  }, []);

  const handlePlan = async () => {
    setBusy(true);
    setResult(null);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const plan = await api.post("/plans/", { name: planName, date: today });
      const res = await api.post(`/plans/${plan.data.id}/plan_route/`, {
        vehicle_ids: selectedVehicles,
        location_ids: selectedLocations,
        algorithm,
      });
      setResult(res.data);
    } catch (e) {
      alert(e.response?.data?.detail || "Planning failed.");
    } finally {
      setBusy(false);
    }
  };

  const stopsByVehicle = (result?.stops || []).reduce((acc, s) => {
    (acc[s.vehicle_plate] = acc[s.vehicle_plate] || []).push(s);
    return acc;
  }, {});

  return (
    <Box m="20px">
      <Header
        title="ROUTE PLANNING"
        subtitle="Assign prioritised locations across vehicles using shortest-path algorithms"
      />

      <Box
        backgroundColor={colors.primary[400]}
        p="20px"
        borderRadius="6px"
        display="flex"
        flexDirection="column"
        gap={2}
        maxWidth="720px"
      >
        <TextField
          label="Plan Name"
          value={planName}
          onChange={(e) => setPlanName(e.target.value)}
        />
        <FormControl>
          <InputLabel>Vehicles</InputLabel>
          <Select
            multiple
            value={selectedVehicles}
            onChange={(e) => setSelectedVehicles(e.target.value)}
            input={<OutlinedInput label="Vehicles" />}
            renderValue={(sel) => (
              <Box display="flex" gap={0.5} flexWrap="wrap">
                {sel.map((id) => {
                  const v = vehicles.find((x) => x.id === id);
                  return <Chip key={id} label={v?.plate_number || id} size="small" />;
                })}
              </Box>
            )}
          >
            {vehicles.map((v) => (
              <MenuItem key={v.id} value={v.id}>
                {v.plate_number} ({v.engine_type})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl>
          <InputLabel>Locations (empty = all active)</InputLabel>
          <Select
            multiple
            value={selectedLocations}
            onChange={(e) => setSelectedLocations(e.target.value)}
            input={<OutlinedInput label="Locations (empty = all active)" />}
            renderValue={(sel) => `${sel.length} selected`}
          >
            {locations.map((l) => (
              <MenuItem key={l.id} value={l.id}>
                {l.name} (priority {l.priority})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          select
          label="Algorithm"
          value={algorithm}
          onChange={(e) => setAlgorithm(e.target.value)}
        >
          {ALGORITHMS.map((a) => (
            <MenuItem key={a.value} value={a.value}>
              {a.label}
            </MenuItem>
          ))}
        </TextField>
        <Button
          variant="contained"
          color="secondary"
          startIcon={<RouteOutlinedIcon />}
          disabled={busy || selectedVehicles.length === 0}
          onClick={handlePlan}
        >
          {busy ? "Planning…" : "Generate Optimised Route"}
        </Button>
      </Box>

      {result && (
        <Box mt="24px">
          <Box display="flex" gap={2} mb={2}>
            <Chip
              color="secondary"
              label={`Total distance: ${result.total_distance_km} km`}
            />
            <Chip
              color="success"
              label={`Estimated CO2e: ${result.total_emission_kg} kg`}
            />
          </Box>
          <Box display="flex" gap={2} flexWrap="wrap">
            {Object.entries(stopsByVehicle).map(([plate, stops]) => (
              <Box
                key={plate}
                backgroundColor={colors.primary[400]}
                p="16px"
                borderRadius="6px"
                minWidth="280px"
              >
                <Typography variant="h5" color={colors.greenAccent[400]}>
                  {plate}
                </Typography>
                <Divider sx={{ my: 1 }} />
                {stops
                  .sort((a, b) => a.order - b.order)
                  .map((s) => (
                    <Typography key={s.id} variant="body2">
                      {s.order + 1}. {s.location_name}{" "}
                      <span style={{ color: colors.grey[300] }}>
                        ({s.leg_distance_km} km)
                      </span>
                    </Typography>
                  ))}
              </Box>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default RoutePlanning;
