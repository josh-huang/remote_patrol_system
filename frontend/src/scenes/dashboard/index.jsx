import { useCallback, useEffect, useState } from "react";
import { Box, LinearProgress, Typography, useTheme } from "@mui/material";
import { ResponsiveLine } from "@nivo/line";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import Co2OutlinedIcon from "@mui/icons-material/Co2Outlined";
import EnergySavingsLeafOutlinedIcon from "@mui/icons-material/EnergySavingsLeafOutlined";
import Header from "../../components/Header";
import Panel from "../../components/Panel";
import StatCard from "../../components/StatCard";
import StatusChip from "../../components/StatusChip";
import AlertCard from "../../components/AlertCard";
import RouteMap, { currentStops, routesFromStops } from "../../components/RouteMap";
import { tokens } from "../../theme";
import api from "../../api/client";
import { colorFor, fetchList, fmt } from "../../api/resources";

const Dashboard = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [data, setData] = useState(null);
  const [vehicles, setVehicles] = useState([]);
  const [sites, setSites] = useState([]);
  const [stops, setStops] = useState([]);

  const load = useCallback(() => {
    api.get("/dashboard/summary/").then((r) => setData(r.data));
    fetchList("/vehicles/").then(setVehicles);
    fetchList("/locations/", { is_active: true }).then(setSites);
    fetchList("/plans/", { status: "active" }).then((plans) => setStops(currentStops(plans)));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const vehicleIndex = Object.fromEntries(vehicles.map((v, i) => [v.id, i]));
  const vehicleColor = (id) => colorFor(vehicleIndex[id] ?? 0);
  const iconStyle = { color: colors.greenAccent[500], fontSize: 28 };
  const saved = data?.carbon_saved || {};

  const series = (data?.emission_by_vehicle || []).map((s) => ({
    id: s.plate_number,
    color: vehicleColor(s.vehicle_id),
    data: s.points.map((p) => ({ x: p.day, y: p.emission_kg })),
  }));

  return (
    <Box m="20px">
      <Header title="COMMAND DASHBOARD" subtitle="Tonight's patrol, emergencies, fleet health and carbon footprint" />

      <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(210px, 1fr))" gap="16px" mb="16px">
        <StatCard
          title="Operational vehicles"
          value={`${data?.vehicles?.operational ?? "–"}/${data?.vehicles?.total ?? "–"}`}
          subtitle={`${data?.vehicles?.in_maintenance ?? 0} in maintenance`}
          icon={<LocalShippingOutlinedIcon sx={iconStyle} />}
        />
        <StatCard
          title="Sites patrolled"
          value={`${data?.stops_today?.visited ?? "–"}/${data?.stops_today?.total ?? "–"}`}
          subtitle={`${data?.active_plans ?? 0} active plan(s)`}
          icon={<FactCheckOutlinedIcon sx={iconStyle} />}
        />
        <StatCard
          title="Emergency alerts"
          value={data?.active_alerts?.length ?? "–"}
          subtitle={`${data?.open_incidents ?? 0} open incidents · ${data?.critical_incidents ?? 0} critical`}
          icon={<CampaignOutlinedIcon sx={{ ...iconStyle, color: colors.redAccent[500] }} />}
          accent={colors.redAccent[500]}
        />
        <StatCard
          title="Estimated CO2e"
          value={`${fmt(data?.total_emission_kg)} kg`}
          subtitle={`${fmt(data?.total_distance_km, 0)} km patrolled`}
          icon={<Co2OutlinedIcon sx={iconStyle} />}
        />
        <StatCard
          title="CO2e saved"
          value={`${fmt(saved.total_saved_kg)} kg`}
          subtitle={`${fmt(saved.planning_saved_km, 0)} km by planning · ${fmt(saved.reroute_saved_km, 0)} km by re-routing`}
          icon={<EnergySavingsLeafOutlinedIcon sx={iconStyle} />}
          accent={colors.greenAccent[300]}
        />
      </Box>

      <Box display="grid" gridTemplateColumns="repeat(12, 1fr)" gap="16px">
        <Panel title="Emergency alert noticeboard" sx={{ gridColumn: { xs: "span 12", lg: "span 5" } }}>
          <Box display="flex" flexDirection="column" gap={1.2} maxHeight={430} overflow="auto">
            {(data?.active_alerts || []).length === 0 && (
              <Typography color={colors.grey[300]}>No active alerts. All sites normal.</Typography>
            )}
            {(data?.active_alerts || []).map((a) => (
              <AlertCard key={a.id} alert={a} vehicles={vehicles} onChange={load} compact />
            ))}
          </Box>
        </Panel>

        <Panel title="Live fleet & routes" sx={{ gridColumn: { xs: "span 12", lg: "span 7" } }}>
          <RouteMap
            height={430}
            sites={sites}
            vehicles={vehicles.map((v) => ({ ...v, color: vehicleColor(v.id) }))}
            routes={routesFromStops(stops, vehicleColor)}
          />
        </Panel>

        <Panel title="Fleet status" sx={{ gridColumn: "span 12" }}>
          <Box overflow="auto">
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", color: colors.grey[300] }}>
                  {["Vehicle", "Driver in charge", "Contact", "Health", "Next location", "Progress", "Mileage this patrol", "Total patrol km"].map((h) => (
                    <th key={h} style={{ padding: "6px 8px", fontWeight: 600 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {vehicles.map((v) => {
                  const p = v.route_progress || { visited: 0, total: 0 };
                  return (
                    <tr key={v.id} style={{ borderTop: `1px solid ${colors.primary[500]}` }}>
                      <td style={{ padding: "8px" }}>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Box width={10} height={10} borderRadius="2px" backgroundColor={vehicleColor(v.id)} />
                          <strong>{v.plate_number}</strong>
                        </Box>
                        <Typography variant="caption" color={colors.grey[400]}>
                          {v.model_name} · {v.engine_type}
                        </Typography>
                      </td>
                      <td style={{ padding: "8px" }}>{v.driver_name || "—"}</td>
                      <td style={{ padding: "8px" }}>{v.driver_phone || v.contact_number || "—"}</td>
                      <td style={{ padding: "8px" }}>
                        <StatusChip value={v.maintenance_status} />
                      </td>
                      <td style={{ padding: "8px" }}>
                        {v.next_location ? (
                          <span style={{ color: v.next_location.is_emergency ? colors.redAccent[400] : undefined }}>
                            {v.next_location.is_emergency ? "⚠ " : ""}
                            {v.next_location.name}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td style={{ padding: "8px", minWidth: 120 }}>
                        <LinearProgress
                          variant="determinate"
                          color="secondary"
                          value={p.total ? (100 * p.visited) / p.total : 0}
                        />
                        <Typography variant="caption">
                          {p.visited}/{p.total}
                        </Typography>
                      </td>
                      <td style={{ padding: "8px" }}>{fmt(v.route_mileage_km)} km</td>
                      <td style={{ padding: "8px" }}>{fmt(v.patrol_mileage_km, 0)} km</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Box>
        </Panel>

        <Panel title="Estimated carbon emission per vehicle (last 30 days)" sx={{ gridColumn: { xs: "span 12", lg: "span 8" } }}>
          <Box height="320px">
            <ResponsiveLine
              data={series}
              theme={{
                axis: { ticks: { text: { fill: colors.grey[100] } }, legend: { text: { fill: colors.grey[100] } } },
                legends: { text: { fill: colors.grey[100] } },
                grid: { line: { stroke: colors.primary[300], strokeOpacity: 0.3 } },
                tooltip: { container: { color: colors.primary[500] } },
              }}
              colors={{ datum: "color" }}
              margin={{ top: 20, right: 110, bottom: 60, left: 55 }}
              xScale={{ type: "point" }}
              yScale={{ type: "linear", min: 0, max: "auto" }}
              axisBottom={{ tickRotation: -40 }}
              axisLeft={{ legend: "kg CO2e", legendOffset: -45, legendPosition: "middle" }}
              pointSize={6}
              useMesh
              curve="monotoneX"
              legends={[{ anchor: "right", direction: "column", translateX: 100, itemWidth: 90, itemHeight: 20, symbolSize: 10 }]}
            />
          </Box>
        </Panel>

        <Panel title="Carbon savings" sx={{ gridColumn: { xs: "span 12", lg: "span 4" } }}>
          <Typography variant="body2" color={colors.grey[300]} mb={2}>
            Automated planning vs the manual baseline, plus dynamic re-routing after emergencies
            (continuing from the emergency site instead of driving back).
          </Typography>
          {[
            ["Manual baseline", `${fmt(saved.baseline_km, 0)} km`],
            ["Optimised plans", `${fmt(saved.planned_km, 0)} km`],
            ["Saved by planning", `${fmt(saved.planning_saved_km, 0)} km · ${fmt(saved.planning_saved_kg)} kg CO2e`],
            ["Saved by re-routing", `${fmt(saved.reroute_saved_km, 1)} km · ${fmt(saved.reroute_saved_kg, 2)} kg CO2e`],
          ].map(([k, v]) => (
            <Box key={k} display="flex" justifyContent="space-between" py={0.8} borderBottom={`1px solid ${colors.primary[500]}`}>
              <Typography>{k}</Typography>
              <Typography fontWeight={700}>{v}</Typography>
            </Box>
          ))}
          <Box mt={2} textAlign="center">
            <Typography variant="h2" color={colors.greenAccent[400]} fontWeight={700}>
              {fmt(saved.total_saved_kg)} kg
            </Typography>
            <Typography variant="caption" color={colors.grey[300]}>
              total CO2e avoided
            </Typography>
          </Box>
        </Panel>
      </Box>
    </Box>
  );
};

export default Dashboard;
