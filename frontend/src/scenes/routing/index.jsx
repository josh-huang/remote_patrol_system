import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  MenuItem,
  Tab,
  Tabs,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import RouteOutlinedIcon from "@mui/icons-material/RouteOutlined";
import Header from "../../components/Header";
import Panel from "../../components/Panel";
import PlanResult from "../../components/PlanResult";
import DataTable from "../../components/DataTable";
import StatusChip from "../../components/StatusChip";
import RouteMap from "../../components/RouteMap";
import { tokens } from "../../theme";
import api from "../../api/client";
import { ALGORITHMS, colorFor, errorMessage, fetchList, fmt } from "../../api/resources";

const today = () => new Date().toISOString().slice(0, 10);

const AlgorithmSelect = ({ value, onChange }) => (
  <TextField select label="Shortest-path algorithm" value={value} onChange={(e) => onChange(e.target.value)} sx={{ minWidth: 220 }}>
    {ALGORITHMS.map((a) => (
      <MenuItem key={a.value} value={a.value}>
        {a.label}
      </MenuItem>
    ))}
  </TextField>
);

const AutoPlan = ({ vehicles, sites, onPlanned }) => {
  const operational = vehicles.filter((v) => v.is_operational);
  const [name, setName] = useState("");
  const [vehicleIds, setVehicleIds] = useState([]);
  const [locationIds, setLocationIds] = useState([]);
  const [algorithm, setAlgorithm] = useState("dijkstra");
  const [depot, setDepot] = useState("");
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => setVehicleIds(operational.map((v) => v.id)), [vehicles]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/plans/auto_daily/", {
        name: name || undefined,
        vehicle_ids: vehicleIds,
        location_ids: locationIds,
        algorithm,
        depot_location_id: depot || null,
        from_live_positions: live,
      });
      onPlanned(data);
    } catch (e) {
      setError(errorMessage(e, "Planning failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box display="flex" flexDirection="column" gap={2} maxWidth={760}>
      <Typography variant="body2">
        Plans every selected vehicle across the selected sites (default: all operational vehicles × all active sites).
        Every site is covered once, higher-priority and emergency sites first, with the shortest total distance.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Plan name (optional)" value={name} onChange={(e) => setName(e.target.value)} />
      <Autocomplete
        multiple
        options={operational}
        getOptionLabel={(v) => `${v.plate_number} (${v.engine_type})`}
        value={operational.filter((v) => vehicleIds.includes(v.id))}
        onChange={(_, val) => setVehicleIds(val.map((v) => v.id))}
        renderInput={(p) => <TextField {...p} label="Vehicles (operational only)" />}
      />
      <Autocomplete
        multiple
        options={sites}
        getOptionLabel={(l) => `${l.name} (P${l.priority})`}
        value={sites.filter((l) => locationIds.includes(l.id))}
        onChange={(_, val) => setLocationIds(val.map((l) => l.id))}
        renderInput={(p) => <TextField {...p} label="Sites (empty = all active)" />}
      />
      <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
        <AlgorithmSelect value={algorithm} onChange={setAlgorithm} />
        <TextField select label="Start from (depot)" value={depot} onChange={(e) => setDepot(e.target.value)} sx={{ minWidth: 220 }} disabled={live}>
          <MenuItem value="">— first site —</MenuItem>
          {sites.map((l) => (
            <MenuItem key={l.id} value={l.id}>
              {l.name}
            </MenuItem>
          ))}
        </TextField>
        <FormControlLabel
          control={<Checkbox checked={live} onChange={(e) => setLive(e.target.checked)} />}
          label="Start from each vehicle's live position"
        />
      </Box>
      <Button
        variant="contained"
        color="secondary"
        startIcon={<RouteOutlinedIcon />}
        disabled={busy || vehicleIds.length === 0}
        onClick={submit}
        sx={{ alignSelf: "flex-start" }}
      >
        {busy ? "Planning…" : "Generate optimised plan"}
      </Button>
    </Box>
  );
};

const ManualPlan = ({ vehicles, sites, onPlanned }) => {
  const operational = vehicles.filter((v) => v.is_operational);
  const [name, setName] = useState("Manual patrol plan");
  const [algorithm, setAlgorithm] = useState("dijkstra");
  const [assign, setAssign] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const taken = new Set(Object.values(assign).flat().map((l) => l.id));

  const submit = async () => {
    const routes = Object.entries(assign)
      .filter(([, locs]) => locs.length)
      .map(([vid, locs]) => ({ vehicle_id: Number(vid), location_ids: locs.map((l) => l.id) }));
    if (!routes.length) return setError("Assign at least one site to a vehicle.");
    setBusy(true);
    setError("");
    try {
      const plan = await api.post("/plans/", { name, date: today() });
      const { data } = await api.post(`/plans/${plan.data.id}/manual_route/`, { routes, algorithm });
      onPlanned(data);
    } catch (e) {
      setError(errorMessage(e, "Could not save plan."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box display="flex" flexDirection="column" gap={2} maxWidth={760}>
      <Typography variant="body2">
        Pick each vehicle's sites in the order they should be visited. Distances are computed on the same road network
        as automatic plans so the two are comparable.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Box display="flex" gap={2} flexWrap="wrap">
        <TextField label="Plan name" value={name} onChange={(e) => setName(e.target.value)} sx={{ flex: 1 }} />
        <AlgorithmSelect value={algorithm} onChange={setAlgorithm} />
      </Box>
      {operational.map((v, i) => (
        <Autocomplete
          key={v.id}
          multiple
          options={sites.filter((l) => !taken.has(l.id) || (assign[v.id] || []).some((x) => x.id === l.id))}
          getOptionLabel={(l) => l.name}
          value={assign[v.id] || []}
          onChange={(_, val) => setAssign({ ...assign, [v.id]: val })}
          renderTags={(val, getTagProps) =>
            val.map((l, idx) => <Chip {...getTagProps({ index: idx })} key={l.id} size="small" label={`${idx + 1}. ${l.name}`} />)
          }
          renderInput={(p) => <TextField {...p} label={`${v.plate_number} — visiting order`} sx={{ "& label": { color: colorFor(i) } }} />}
        />
      ))}
      <Typography variant="caption">
        {taken.size}/{sites.length} sites assigned
      </Typography>
      <Button variant="contained" color="secondary" onClick={submit} disabled={busy} sx={{ alignSelf: "flex-start" }}>
        {busy ? "Saving…" : "Save manual plan"}
      </Button>
    </Box>
  );
};

const PlanHistory = ({ onSelect, refreshKey }) => {
  const [plans, setPlans] = useState([]);
  useEffect(() => {
    fetchList("/plans/").then(setPlans);
  }, [refreshKey]);
  const columns = [
    { field: "date", headerName: "Date", flex: 0.7 },
    { field: "name", headerName: "Plan", flex: 1.4 },
    { field: "mode", headerName: "Mode", flex: 0.5 },
    { field: "status", headerName: "Status", flex: 0.7, renderCell: ({ value }) => <StatusChip value={value} /> },
    { field: "progress", headerName: "Visited", flex: 0.6, valueGetter: ({ value }) => `${value.visited}/${value.total}` },
    { field: "total_distance_km", headerName: "km", flex: 0.5, valueFormatter: ({ value }) => fmt(value) },
    { field: "baseline_distance_km", headerName: "Baseline km", flex: 0.6, valueFormatter: ({ value }) => fmt(value) },
    { field: "total_emission_kg", headerName: "CO2e kg", flex: 0.6, valueFormatter: ({ value }) => fmt(value, 2) },
    { field: "emission_saved_kg", headerName: "Saved kg", flex: 0.6, valueFormatter: ({ value }) => fmt(value, 2) },
  ];
  return <DataTable rows={plans} columns={columns} height="45vh" onRowClick={({ row }) => onSelect(row)} />;
};

const ShortestPath = ({ sites }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [src, setSrc] = useState("");
  const [dst, setDst] = useState("");
  const [algorithm, setAlgorithm] = useState("dijkstra");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const run = async () => {
    setError("");
    try {
      const { data } = await api.post("/routing/shortest-path/", {
        source_location_id: src,
        target_location_id: dst,
        algorithm,
        compare: true,
      });
      setResult(data);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <Box>
      <Typography variant="body2" mb={2}>
        Sites form an approximate road network (each linked to its nearest neighbours, with a road-circuity factor),
        so the shortest road path between two sites can pass through others.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Box display="flex" gap={2} flexWrap="wrap" mb={2}>
        {[["From", src, setSrc], ["To", dst, setDst]].map(([label, val, set]) => (
          <TextField key={label} select label={label} value={val} onChange={(e) => set(e.target.value)} sx={{ minWidth: 220 }}>
            {sites.map((l) => (
              <MenuItem key={l.id} value={l.id}>
                {l.name}
              </MenuItem>
            ))}
          </TextField>
        ))}
        <AlgorithmSelect value={algorithm} onChange={setAlgorithm} />
        <Button variant="contained" color="secondary" onClick={run} disabled={!src || !dst}>
          Find shortest path
        </Button>
      </Box>
      {result && (
        <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "3fr 2fr" }} gap={2}>
          <RouteMap
            sites={sites}
            routes={[{ key: "p", color: colors.greenAccent[500], points: result.path_coords.map((p, i) => ({ ...p, order: i + 1 })) }]}
            height={420}
          />
          <Box>
            <Typography variant="h4" color={colors.greenAccent[400]} fontWeight={700}>
              {fmt(result.distance_km, 2)} km
            </Typography>
            <Typography variant="caption">straight line {fmt(result.straight_line_km, 2)} km</Typography>
            <Typography mt={1}>{result.path_names.join(" → ")}</Typography>
            <Typography variant="caption" display="block" mt={1}>
              Road network: {result.graph.nodes} nodes, {result.graph.edges} edges
            </Typography>
            <Box mt={2}>
              <Typography variant="h6">Algorithm comparison</Typography>
              {result.comparison.map((c) => (
                <Box key={c.algorithm} display="flex" justifyContent="space-between" py={0.5} borderBottom={`1px solid ${colors.primary[500]}`}>
                  <span>{ALGORITHMS.find((a) => a.value === c.algorithm)?.label}</span>
                  <span>
                    {fmt(c.distance_km, 3)} km · {fmt(c.runtime_ms, 3)} ms
                  </span>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      )}
    </Box>
  );
};

const RoutePlanning = () => {
  const [tab, setTab] = useState(0);
  const [vehicles, setVehicles] = useState([]);
  const [sites, setSites] = useState([]);
  const [plan, setPlan] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    fetchList("/vehicles/").then(setVehicles);
    fetchList("/locations/", { is_active: true }).then(setSites);
  }, []);

  const vehicleIndex = useMemo(() => Object.fromEntries(vehicles.map((v, i) => [v.id, i])), [vehicles]);
  const vehicleColor = (id) => colorFor(vehicleIndex[id] ?? 0);

  const showPlan = (p) => {
    setPlan(p);
    setNotice("");
    setRefreshKey((k) => k + 1);
  };

  const rebalance = async () => {
    try {
      const { data } = await api.post(`/plans/${plan.id}/rebalance/`);
      setNotice(data.moved ? `Moved ${data.moved} stop(s) off vehicles that are no longer operational.` : "Nothing to rebalance.");
      setPlan(data.plan);
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setNotice(errorMessage(e));
    }
  };

  const complete = async () => {
    const { data } = await api.patch(`/plans/${plan.id}/`, { status: "completed" });
    setPlan(data);
    setRefreshKey((k) => k + 1);
  };

  return (
    <Box m="20px">
      <Header title="ROUTE PLANNING" subtitle="Automatic & manual patrol plans, plan history and shortest-path tools" />
      <Panel>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} textColor="secondary" indicatorColor="secondary" sx={{ mb: 2 }}>
          <Tab label="Automatic plan" />
          <Tab label="Manual plan" />
          <Tab label="Plans" />
          <Tab label="Shortest path" />
        </Tabs>
        {tab === 0 && <AutoPlan vehicles={vehicles} sites={sites} onPlanned={showPlan} />}
        {tab === 1 && <ManualPlan vehicles={vehicles} sites={sites} onPlanned={showPlan} />}
        {tab === 2 && <PlanHistory onSelect={setPlan} refreshKey={refreshKey} />}
        {tab === 3 && <ShortestPath sites={sites} />}
      </Panel>

      {plan && tab !== 3 && (
        <Panel
          mt="16px"
          action={
            plan.status === "active" && (
              <Box display="flex" gap={1}>
                <Button size="small" variant="outlined" color="inherit" onClick={rebalance}>
                  Rebalance broken-down vehicles
                </Button>
                <Button size="small" variant="outlined" color="inherit" onClick={complete}>
                  Mark completed
                </Button>
              </Box>
            )
          }
        >
          {notice && <Alert severity="info" sx={{ mb: 2 }}>{notice}</Alert>}
          <PlanResult plan={plan} sites={sites} vehicleColor={vehicleColor} />
        </Panel>
      )}
    </Box>
  );
};

export default RoutePlanning;
