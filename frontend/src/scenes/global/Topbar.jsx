import { Box, IconButton, Typography, useTheme } from "@mui/material";
import { useContext } from "react";
import { ColorModeContext, tokens } from "../../theme";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import { useAuth } from "../../context/AuthContext";

const Topbar = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const colorMode = useContext(ColorModeContext);
  const { user, logout } = useAuth();

  return (
    <Box display="flex" justifyContent="flex-end" alignItems="center" p={2}>
      <Box display="flex" alignItems="center" gap="8px">
        <PersonOutlinedIcon />
        <Typography variant="body2" color={colors.grey[100]}>
          {user ? `${user.username} (${user.role})` : ""}
        </Typography>
        <IconButton onClick={colorMode.toggleColorMode}>
          {theme.palette.mode === "dark" ? (
            <DarkModeOutlinedIcon />
          ) : (
            <LightModeOutlinedIcon />
          )}
        </IconButton>
        <IconButton onClick={logout} title="Log out">
          <LogoutOutlinedIcon />
        </IconButton>
      </Box>
    </Box>
  );
};

export default Topbar;
