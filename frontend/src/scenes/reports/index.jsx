import { useEffect, useState } from "react";
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  Chip,
  useTheme,
} from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";

const Metric = ({ label, value }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <Box
      backgroundColor={colors.primary[400]}
      p="16px"
      borderRadius="6px"
      minWidth="160px"
    >
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
    api
      .get(`/reports/patrol/?period=${period}`)
      .then((r) => setReport(r.data));
  }, [period]);

  return (
    <Box m="20px">
      <Header
        title="PATROL REPORTS"
        subtitle="Operational summary with an AI-generated narrative"
      />

      <ToggleButtonGroup
        value={period}
        exclusive
        color="secondary"
        onChange={(e, v) => v && setPeriod(v)}
        sx={{ mb: 3 }}
      >
        <ToggleButton value="daily">Daily</ToggleButton>
        <ToggleButton value="monthly">Monthly</ToggleButton>
      </ToggleButtonGroup>

      {report && (
        <>
          <Box display="flex" gap={2} flexWrap="wrap" mb={3}>
            <Metric label="Patrol plans" value={report.total_patrols} />
            <Metric label="Visits logged" value={report.total_records} />
            <Metric label="Distance (km)" value={report.total_distance_km} />
            <Metric label="CO2e (kg)" value={report.total_emission_kg} />
            <Metric label="Incidents" value={report.total_incidents} />
            <Metric label="Critical" value={report.critical_incidents} />
          </Box>

          <Box
            backgroundColor={colors.primary[400]}
            p="20px"
            borderRadius="6px"
            maxWidth="900px"
          >
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <AutoAwesomeIcon sx={{ color: colors.greenAccent[400] }} />
              <Typography variant="h5" fontWeight="600">
                AI Executive Summary
              </Typography>
              <Chip
                label={report.source === "llm" ? "LLM" : "mock"}
                size="small"
                variant="outlined"
              />
            </Box>
            <Typography variant="body1" color={colors.grey[100]}>
              {report.narrative}
            </Typography>
          </Box>
        </>
      )}
    </Box>
  );
};

export default Reports;
