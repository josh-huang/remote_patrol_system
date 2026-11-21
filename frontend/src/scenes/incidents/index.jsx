import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";
import { fetchList } from "../../api/resources";
import StatusChip from "../../components/StatusChip";

const SEVERITY_COLOR = {
  low: "info",
  medium: "warning",
  high: "warning",
  critical: "error",
};

const Incidents = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [sites, setSites] = useState([]);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => fetchList("/incidents/", { ordering: "-created_at" }).then(setItems);

  useEffect(() => {
    load();
    fetchList("/locations/").then(setSites);
  }, []);

  const setStatus = async (inc, status) => {
    await api.patch(`/incidents/${inc.id}/`, { status });
    load();
  };

  const handleSubmit = async () => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("description", description);
      if (location) fd.append("location", location);
      files.forEach((f) => fd.append("uploaded_images", f));
      await api.post("/incidents/", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setOpen(false);
      setDescription("");
      setLocation("");
      setFiles([]);
      load();
    } catch (e) {
      alert("Submission failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header
          title="INCIDENTS"
          subtitle="AI-triaged field reports submitted from the duty phones"
        />
        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => setOpen(true)}
        >
          Report Incident
        </Button>
      </Box>

      <Box display="flex" flexDirection="column" gap={2}>
        {items.map((inc) => (
          <Box
            key={inc.id}
            backgroundColor={colors.primary[400]}
            p="16px"
            borderRadius="6px"
          >
            <Box display="flex" gap={1} alignItems="center" mb={1} flexWrap="wrap">
              <Chip
                label={(inc.ai_severity || "unassessed").toUpperCase()}
                color={SEVERITY_COLOR[inc.ai_severity] || "default"}
                size="small"
              />
              <Chip label={inc.ai_category || "—"} size="small" variant="outlined" />
              {inc.ai_anomaly_detected && (
                <Chip label="ANOMALY" color="error" size="small" />
              )}
              <Chip
                icon={<AutoAwesomeIcon />}
                label={`AI: ${inc.ai_source || "—"}`}
                size="small"
                variant="outlined"
              />
              <StatusChip value={inc.status} variant="outlined" />
              <Typography variant="caption" color={colors.grey[300]} ml="auto">
                {inc.location_name || "Unknown location"}
                {inc.vehicle_plate ? ` · ${inc.vehicle_plate}` : ""} ·{" "}
                {new Date(inc.created_at).toLocaleString()}
              </Typography>
            </Box>
            <Typography variant="body1">{inc.description}</Typography>
            {inc.ai_summary && (
              <Typography variant="body2" color={colors.greenAccent[400]} mt={1}>
                <strong>AI summary:</strong> {inc.ai_summary}
              </Typography>
            )}
            {inc.ai_recommended_action && (
              <Typography variant="body2" color={colors.grey[200]}>
                <strong>Recommended:</strong> {inc.ai_recommended_action}
              </Typography>
            )}
            {inc.ai_tags?.length > 0 && (
              <Box display="flex" gap={0.5} mt={1} flexWrap="wrap">
                {inc.ai_tags.map((t) => (
                  <Chip key={t} label={t} size="small" />
                ))}
              </Box>
            )}
            {inc.images?.length > 0 && (
              <Box display="flex" gap={1} mt={1} flexWrap="wrap">
                {inc.images.map((img) => (
                  <a key={img.id} href={img.image} target="_blank" rel="noreferrer">
                    <img src={img.image} alt="incident" style={{ height: 80, borderRadius: 4 }} />
                  </a>
                ))}
              </Box>
            )}
            {inc.status !== "resolved" && (
              <Box display="flex" gap={1} mt={1.5}>
                {inc.status === "open" && (
                  <Button size="small" variant="outlined" color="inherit" onClick={() => setStatus(inc, "acknowledged")}>
                    Acknowledge
                  </Button>
                )}
                <Button size="small" variant="outlined" color="success" onClick={() => setStatus(inc, "resolved")}>
                  Resolve
                </Button>
              </Box>
            )}
          </Box>
        ))}
      </Box>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Report an Incident</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="Description"
            multiline
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what you observed…"
          />
          <TextField select label="Site" value={location} onChange={(e) => setLocation(e.target.value)}>
            <MenuItem value="">— unknown —</MenuItem>
            {sites.map((l) => (
              <MenuItem key={l.id} value={l.id}>
                {l.name}
              </MenuItem>
            ))}
          </TextField>
          <Button variant="outlined" component="label">
            Attach Photos ({files.length})
            <input
              hidden
              multiple
              type="file"
              accept="image/*"
              onChange={(e) => setFiles(Array.from(e.target.files))}
            />
          </Button>
          <Typography variant="caption" color={colors.grey[300]}>
            On submit, the AI analyst classifies the report and assigns a
            severity. High/critical incidents at a site raise an emergency
            alert and the agent proposes a dispatch.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            color="secondary"
            disabled={busy || !description}
          >
            {busy ? "Analyzing…" : "Submit & Analyze"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Incidents;
