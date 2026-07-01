import { useEffect, useState } from "react";
import { Box, Typography, useTheme } from "@mui/material";
import { ResponsiveLine } from "@nivo/line";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import ReportProblemOutlinedIcon from "@mui/icons-material/ReportProblemOutlined";
import Co2OutlinedIcon from "@mui/icons-material/Co2Outlined";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";

const StatCard = ({ title, value, subtitle, icon }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <Box
      gridColumn="span 3"
      backgroundColor={colors.primary[400]}
      display="flex"
      flexDirection="column"
      justifyContent="center"
      p="20px"
      borderRadius="6px"
    >
      <Box display="flex" justifyContent="space-between" alignItems="center">
        {icon}
        <Typography variant="h3" fontWeight="bold" color={colors.grey[100]}>
          {value}
        </Typography>
      </Box>
      <Typography variant="h6" color={colors.greenAccent[400]} mt={1}>
        {title}
      </Typography>
      <Typography variant="caption" color={colors.grey[300]}>
        {subtitle}
      </Typography>
    </Box>
  );
};

const Dashboard = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard/summary/").then((res) => setData(res.data));
  }, []);

  const iconStyle = { color: colors.greenAccent[500], fontSize: 28 };

  const trend = [
    {
      id: "CO2e (kg)",
      color: colors.greenAccent[500],
      data: (data?.emission_trend || []).map((row) => ({
        x: row.day,
        y: row.emission_kg,
      })),
    },
  ];

  return (
    <Box m="20px">
      <Header
        title="COMMAND DASHBOARD"
        subtitle="Fleet status, patrol coverage and carbon overview"
      />
      <Box
        display="grid"
        gridTemplateColumns="repeat(12, 1fr)"
        gap="20px"
      >
        <StatCard
          title="Vehicles Available"
          value={`${data?.vehicles?.available ?? "–"}/${data?.vehicles?.total ?? "–"}`}
          subtitle="fleet readiness"
          icon={<LocalShippingOutlinedIcon sx={iconStyle} />}
        />
        <StatCard
          title="Active Locations"
          value={data?.locations ?? "–"}
          subtitle="checkpoints on patrol"
          icon={<PlaceOutlinedIcon sx={iconStyle} />}
        />
        <StatCard
          title="Open Incidents"
          value={data?.open_incidents ?? "–"}
          subtitle={`${data?.critical_incidents ?? 0} critical`}
          icon={<ReportProblemOutlinedIcon sx={iconStyle} />}
        />
        <StatCard
          title="Total CO2e"
          value={`${data?.total_emission_kg ?? "–"} kg`}
          subtitle="estimated emissions"
          icon={<Co2OutlinedIcon sx={iconStyle} />}
        />

        <Box
          gridColumn="span 12"
          gridRow="span 2"
          backgroundColor={colors.primary[400]}
          borderRadius="6px"
          p="20px"
          height="360px"
        >
          <Typography variant="h5" fontWeight="600" mb={1}>
            Carbon Emission Trend (last 30 days)
          </Typography>
          <Box height="300px">
            <ResponsiveLine
              data={trend}
              theme={{
                axis: { ticks: { text: { fill: colors.grey[100] } } },
                legends: { text: { fill: colors.grey[100] } },
                tooltip: { container: { color: colors.primary[500] } },
              }}
              colors={{ datum: "color" }}
              margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
              xScale={{ type: "point" }}
              yScale={{ type: "linear", min: 0, max: "auto" }}
              axisBottom={{ tickRotation: -35, legend: "Day", legendOffset: 50, legendPosition: "middle" }}
              axisLeft={{ legend: "kg CO2e", legendOffset: -45, legendPosition: "middle" }}
              pointSize={8}
              pointBorderWidth={2}
              useMesh
              curve="monotoneX"
            />
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;
