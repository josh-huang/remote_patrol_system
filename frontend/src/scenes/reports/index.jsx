import { useEffect, useState } from "react";
import { Box, Button, Chip, ToggleButton, ToggleButtonGroup, Typography, useTheme } from "@mui/material";
import { ResponsiveBar } from "@nivo/bar";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import Header from "../../components/Header";
import Panel from "../../components/Panel";
import { tokens } from "../../theme";
import api from "../../api/client";
import { fmt } from "../../api/resources";

const Metric = ({ label, value }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <Box backgroundColor={colors.primary[400]} p="16px" borderRadius="8px" minWidth="150px" flex="1">
      <Typography variant="h3" fontWeight="bold" color={colors.greenAccent[400]}>
        {value}
      </Typography>
      <Typography variant="body2" color={colors.grey[200]}>
        {label}
      </Typography>
    </Box>
  );
};

const Reports = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [period, setPeriod] = useState("daily");
  const [report, setReport] = useState(null);

  useEffect(() => {
    setReport(null);
    api.get("/reports/patrol/", { params: { period } }).then((r) => setReport(r.data));
  }, [period]);

  const download = async () => {
    const res = await api.get("/reports/patrol/", { params: { period, export: "csv" }, responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `patrol-report-${period}-${report?.end_date || "today"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const saved = report?.carbon_saved || {};

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap">
        <Header title="PATROL REPORTS" subtitle="Daily or monthly operational report with an AI-written summary" />
        <Box display="flex" gap={2} alignItems="center">
          <ToggleButtonGroup value={period} exclusive color="secondary" onChange={(e, v) => v && setPeriod(v)}>
            <ToggleButton value="daily">Daily</ToggleButton>
            <ToggleButton value="monthly">Monthly</ToggleButton>
          </ToggleButtonGroup>
          <Button variant="contained" color="secondary" startIcon={<DownloadOutlinedIcon />} onClick={download} disabled={!report}>
            Download CSV
          </Button>
        </Box>
      </Box>

      {report && (
        <>
          <Typography variant="h5" mb={2}>
            {report.period} ({report.start_date} → {report.end_date})
          </Typography>
          <Box display="flex" gap={2} flexWrap="wrap" mb={2}>
            <Metric label="Patrol plans" value={report.total_patrols} />
            <Metric label="Site visits" value={report.total_records} />
            <Metric label="Distance (km)" value={fmt(report.total_distance_km)} />
            <Metric label="CO2e (kg)" value={fmt(report.total_emission_kg, 2)} />
            <Metric label="CO2e saved (kg)" value={fmt(saved.total_saved_kg, 2)} />
            <Metric label="Emergency alerts" value={report.emergency_alerts} />
            <Metric label="Incidents (critical)" value={`${report.total_incidents} (${report.critical_incidents})`} />
          </Box>

          <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "3fr 2fr" }} gap="16px">
            <Panel title="Per-vehicle distance & emissions">
              <Box height="300px">
                <ResponsiveBar
                  data={report.per_vehicle.map((v) => ({ vehicle: v.plate_number, "Distance (km)": v.distance_km, "CO2e (kg)": v.emission_kg }))}
                  keys={["Distance (km)", "CO2e (kg)"]}
                  indexBy="vehicle"
                  groupMode="grouped"
                  valueFormat=">-.1f"
                  margin={{ top: 10, right: 130, bottom: 40, left: 50 }}
                  colors={[colors.blueAccent[400], colors.greenAccent[500]]}
                  theme={{
                    axis: { ticks: { text: { fill: colors.grey[100] } } },
                    legends: { text: { fill: colors.grey[100] } },
                    tooltip: { container: { color: colors.primary[500] } },
                  }}
                  labelTextColor="#111"
                  legends={[{ dataFrom: "keys", anchor: "right", direction: "column", translateX: 120, itemWidth: 110, itemHeight: 20 }]}
                />
              </Box>
              <table style={{ width: "100%", marginTop: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", color: colors.grey[300] }}>
                    <th>Vehicle</th>
                    <th>Engine</th>
                    <th>Visits</th>
                    <th>km</th>
                    <th>kg CO2e</th>
                  </tr>
                </thead>
                <tbody>
                  {report.per_vehicle.map((v) => (
                    <tr key={v.vehicle_id}>
                      <td>{v.plate_number}</td>
                      <td>{v.engine_type}</td>
                      <td>{v.visits}</td>
                      <td>{fmt(v.distance_km)}</td>
                      <td>{fmt(v.emission_kg, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            <Box display="flex" flexDirection="column" gap="16px">
              <Panel
                title="AI executive summary"
                action={<Chip icon={<AutoAwesomeIcon />} label={report.source === "llm" ? "LLM" : "offline mock"} size="small" variant="outlined" />}
              >
                <Typography variant="body1">{report.narrative}</Typography>
              </Panel>
              <Panel title="Carbon savings">
                <Typography variant="body2">
                  Planning saved {fmt(saved.planning_saved_km)} km ({fmt(saved.planning_saved_kg, 2)} kg CO2e) against the manual
                  baseline; emergency re-routing saved a further {fmt(saved.reroute_saved_km)} km (
                  {fmt(saved.reroute_saved_kg, 2)} kg).
                </Typography>
              </Panel>
              <Panel title="Incidents by category">
                {report.incident_breakdown.length === 0 && <Typography variant="body2">No incidents.</Typography>}
                {report.incident_breakdown.map((row) => (
                  <Box key={row.ai_category} display="flex" justifyContent="space-between">
                    <span>{row.ai_category || "unclassified"}</span>
                    <strong>{row.count}</strong>
                  </Box>
                ))}
              </Panel>
            </Box>
          </Box>
        </>
      )}
    </Box>
  );
};

export default Reports;
