import { Box, Chip, Divider, Typography, useTheme } from "@mui/material";
import { tokens } from "../theme";
import { fmt } from "../api/resources";
import RouteMap, { routesFromStops } from "./RouteMap";
import StatusChip from "./StatusChip";

/** Summary, map and per-vehicle stop list for a patrol plan. */
const PlanResult = ({ plan, sites, vehicleColor }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const byVehicle = {};
  plan.stops.forEach((s) => (byVehicle[s.vehicle] = byVehicle[s.vehicle] || []).push(s));
  const savedKm = Math.max(0, plan.baseline_distance_km - plan.total_distance_km);
  const pct = plan.baseline_distance_km ? (100 * savedKm) / plan.baseline_distance_km : 0;

  return (
    <Box>
      <Box display="flex" gap={1} mb={2} flexWrap="wrap" alignItems="center">
        <Typography variant="h5" fontWeight={700} mr={1}>
          {plan.name}
        </Typography>
        <StatusChip value={plan.status} />
        <Chip size="small" variant="outlined" label={`${plan.mode} · ${plan.algorithm}`} />
        <Chip color="secondary" label={`Route: ${fmt(plan.total_distance_km)} km`} />
        <Chip label={`CO2e: ${fmt(plan.total_emission_kg, 2)} kg`} />
        {plan.mode === "auto" && (
          <>
            <Chip variant="outlined" label={`Manual baseline: ${fmt(plan.baseline_distance_km)} km`} />
            <Chip
              color="success"
              label={`Saved ${fmt(savedKm)} km (${fmt(pct, 0)}%) · ${fmt(plan.baseline_emission_kg - plan.total_emission_kg, 2)} kg CO2e`}
            />
          </>
        )}
        {plan.reroute_saved_km > 0 && (
          <Chip color="success" variant="outlined" label={`Re-routing saved ${fmt(plan.reroute_saved_km)} km`} />
        )}
      </Box>
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "3fr 2fr" }} gap={2}>
        <RouteMap sites={sites} routes={routesFromStops(plan.stops, vehicleColor)} height={460} />
        <Box display="flex" flexDirection="column" gap={1.5} maxHeight={460} overflow="auto">
          {Object.entries(byVehicle).map(([vid, stops]) => {
            const km = stops.reduce((t, s) => t + s.leg_distance_km, 0);
            return (
              <Box key={vid} p="12px" borderRadius="6px" backgroundColor={colors.primary[500]}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6" fontWeight={700} color={vehicleColor(Number(vid))}>
                    {stops[0].vehicle_plate}
                  </Typography>
                  <Typography variant="caption">
                    {stops.length} stops · {fmt(km)} km
                  </Typography>
                </Box>
                <Divider sx={{ my: 1 }} />
                {stops
                  .sort((a, b) => a.order - b.order)
                  .map((s) => (
                    <Typography
                      key={s.id}
                      variant="body2"
                      sx={{ opacity: s.is_visited ? 0.55 : 1, textDecoration: s.is_visited ? "line-through" : "none" }}
                    >
                      {s.order + 1}. {s.source === "emergency" ? "⚠ " : ""}
                      {s.location_name}{" "}
                      <span style={{ color: colors.grey[400] }}>
                        (+{fmt(s.leg_distance_km)} km · P{s.priority})
                      </span>
                      {s.source === "reassigned" && <span style={{ color: colors.blueAccent[300] }}> · reassigned</span>}
                    </Typography>
                  ))}
              </Box>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
};

export default PlanResult;
