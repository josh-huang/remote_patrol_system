import { useState } from "react";
import { Box, Button, MenuItem, TextField, Typography, useTheme } from "@mui/material";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import { tokens } from "../theme";
import api from "../api/client";
import { errorMessage, fmt } from "../api/resources";
import StatusChip from "./StatusChip";

/**
 * One emergency alert on the noticeboard, with Dispatch / Resolve actions.
 * Dispatching diverts a vehicle (nearest by default) and re-plans the rest of
 * its route from the emergency site; the saving vs driving back is shown.
 */
const AlertCard = ({ alert, vehicles = [], onChange, compact = false }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [vehicleId, setVehicleId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const detail = alert.reroute_detail || {};

  const run = async (path, body) => {
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/alerts/${alert.id}/${path}/`, body);
      onChange && onChange(data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const isActive = alert.status === "active";
  return (
    <Box
      p="12px 14px"
      borderRadius="6px"
      border={`1px solid ${isActive ? colors.redAccent[500] : colors.primary[300]}`}
      backgroundColor={colors.primary[500]}
    >
      <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
        <CampaignOutlinedIcon sx={{ color: isActive ? colors.redAccent[500] : colors.grey[300] }} />
        <Typography variant="h6" fontWeight={700}>
          {alert.location_name}
        </Typography>
        <StatusChip value={alert.status} />
        <Typography variant="caption" color={colors.grey[300]} ml="auto">
          {alert.source} · {new Date(alert.created_at).toLocaleString()}
        </Typography>
      </Box>
      {alert.description && (
        <Typography variant="body2" color={colors.grey[200]} mt={0.5}>
          {alert.description}
        </Typography>
      )}

      {alert.status !== "active" && alert.vehicle_plate && (
        <Box mt={1}>
          <Typography variant="body2">
            <strong>{alert.vehicle_plate}</strong> dispatched · re-routed {fmt(alert.rerouted_km)} km vs{" "}
            {fmt(alert.baseline_km)} km driving back ·{" "}
            <span style={{ color: colors.greenAccent[400], fontWeight: 700 }}>
              saved {fmt(alert.saved_km)} km / {fmt(alert.saved_kg, 2)} kg CO2e
            </span>
          </Typography>
          {!compact && detail.new_order_names && (
            <>
              <Typography variant="caption" color={colors.greenAccent[300]} display="block" mt={0.5}>
                New route: {detail.new_order_names.join(" → ")}
              </Typography>
              <Typography variant="caption" color={colors.grey[400]} display="block">
                Old practice: {detail.baseline_order_names.join(" → ")}
              </Typography>
            </>
          )}
        </Box>
      )}

      {error && (
        <Typography variant="caption" color="error" display="block" mt={1}>
          {error}
        </Typography>
      )}

      {alert.status !== "resolved" && (
        <Box display="flex" gap={1} mt={1.2} alignItems="center" flexWrap="wrap">
          {isActive && (
            <>
              {!compact && (
                <TextField
                  select
                  size="small"
                  label="Vehicle"
                  value={vehicleId}
                  onChange={(e) => setVehicleId(e.target.value)}
                  sx={{ minWidth: 170 }}
                >
                  <MenuItem value="">Nearest operational</MenuItem>
                  {vehicles
                    .filter((v) => v.is_operational)
                    .map((v) => (
                      <MenuItem key={v.id} value={v.id}>
                        {v.plate_number}
                      </MenuItem>
                    ))}
                </TextField>
              )}
              <Button
                size="small"
                variant="contained"
                color="error"
                disabled={busy}
                onClick={() => run("dispatch", vehicleId ? { vehicle_id: vehicleId } : {})}
              >
                Dispatch & re-route
              </Button>
            </>
          )}
          <Button size="small" variant="outlined" color="inherit" disabled={busy} onClick={() => run("resolve")}>
            Resolve
          </Button>
        </Box>
      )}
    </Box>
  );
};

export default AlertCard;
