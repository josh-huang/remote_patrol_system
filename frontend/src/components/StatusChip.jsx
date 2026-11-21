import { Chip } from "@mui/material";

const COLORS = {
  healthy: "success",
  due: "warning",
  in_service: "error",
  out_of_service: "error",
  active: "error",
  dispatched: "warning",
  resolved: "success",
  completed: "success",
  low: "info",
  medium: "warning",
  high: "warning",
  critical: "error",
  open: "warning",
  acknowledged: "info",
  emergency: "error",
  reassigned: "info",
};

const LABELS = {
  in_service: "in service",
  out_of_service: "out of service",
  due: "service due",
};

const StatusChip = ({ value, ...props }) => (
  <Chip size="small" label={LABELS[value] || value || "—"} color={COLORS[value] || "default"} {...props} />
);

export default StatusChip;
