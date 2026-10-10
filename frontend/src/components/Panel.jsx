import { Box, Typography, useTheme } from "@mui/material";
import { tokens } from "../theme";

// Card container used across the dashboard.
const Panel = ({ title, action, children, sx, ...rest }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <Box backgroundColor={colors.primary[400]} borderRadius="8px" p="18px" sx={sx} {...rest}>
      {(title || action) && (
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5} gap={1}>
          {title && (
            <Typography variant="h5" fontWeight={600} color={colors.grey[100]}>
              {title}
            </Typography>
          )}
          {action}
        </Box>
      )}
      {children}
    </Box>
  );
};

export default Panel;
