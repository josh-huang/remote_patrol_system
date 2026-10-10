import { Box, Typography, useTheme } from "@mui/material";
import { tokens } from "../theme";

const StatCard = ({ title, value, subtitle, icon, accent }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <Box
      backgroundColor={colors.primary[400]}
      display="flex"
      flexDirection="column"
      justifyContent="center"
      p="18px"
      borderRadius="8px"
      borderLeft={`4px solid ${accent || colors.greenAccent[500]}`}
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
      {subtitle && (
        <Typography variant="caption" color={colors.grey[300]}>
          {subtitle}
        </Typography>
      )}
    </Box>
  );
};

export default StatCard;
