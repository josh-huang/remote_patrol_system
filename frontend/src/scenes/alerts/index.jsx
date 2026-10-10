import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, MenuItem, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import Header from "../../components/Header";
import Panel from "../../components/Panel";
import AlertCard from "../../components/AlertCard";
import api from "../../api/client";
import { errorMessage, fetchList } from "../../api/resources";

const Alerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [sites, setSites] = useState([]);
  const [filter, setFilter] = useState("open");
  const [form, setForm] = useState({ location: "", description: "" });
  const [error, setError] = useState("");

  const load = useCallback(() => {
    const params = filter === "open" ? {} : { status: filter };
    fetchList("/alerts/", { ordering: "-created_at", ...params }).then((rows) =>
      setAlerts(filter === "open" ? rows.filter((a) => a.status !== "resolved") : rows)
    );
    fetchList("/vehicles/").then(setVehicles);
  }, [filter]);

  useEffect(() => {
    load();
    fetchList("/locations/", { is_active: true }).then(setSites);
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const raise = async () => {
    setError("");
    try {
      await api.post("/alerts/", { ...form, source: "manual" });
      setForm({ location: "", description: "" });
      load();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <Box m="20px">
      <Header
        title="EMERGENCY ALERTS"
        subtitle="Dispatching diverts a vehicle and re-plans its remaining route from the emergency site — no driving back"
      />
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "1fr 2fr" }} gap="16px">
        <Panel title="Raise an alert">
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Box display="flex" flexDirection="column" gap={2}>
            <TextField select label="Site" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })}>
              {sites.map((l) => (
                <MenuItem key={l.id} value={l.id}>
                  {l.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="What happened?"
              multiline
              minRows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <Button variant="contained" color="error" startIcon={<CampaignOutlinedIcon />} disabled={!form.location} onClick={raise}>
              Raise emergency alert
            </Button>
            <Typography variant="caption">
              Site alarms, critical incident reports and the AI agent can also raise alerts automatically.
            </Typography>
          </Box>
        </Panel>
        <Panel
          title="Noticeboard"
          action={
            <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)}>
              <ToggleButton value="open">Open</ToggleButton>
              <ToggleButton value="dispatched">Dispatched</ToggleButton>
              <ToggleButton value="resolved">Resolved</ToggleButton>
            </ToggleButtonGroup>
          }
        >
          <Box display="flex" flexDirection="column" gap={1.5}>
            {alerts.length === 0 && <Typography>No alerts.</Typography>}
            {alerts.map((a) => (
              <AlertCard key={a.id} alert={a} vehicles={vehicles} onChange={load} />
            ))}
          </Box>
        </Panel>
      </Box>
    </Box>
  );
};

export default Alerts;
