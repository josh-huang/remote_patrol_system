import { useState } from "react";
import { ProSidebar, Menu, MenuItem } from "react-pro-sidebar";
import { Box, IconButton, Typography, useTheme } from "@mui/material";
import { Link, useLocation } from "react-router-dom";
import "react-pro-sidebar/dist/css/styles.css";
import { tokens } from "../../theme";
import { useAuth } from "../../context/AuthContext";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import BadgeOutlinedIcon from "@mui/icons-material/BadgeOutlined";
import RouteOutlinedIcon from "@mui/icons-material/RouteOutlined";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import ReportProblemOutlinedIcon from "@mui/icons-material/ReportProblemOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import ChatOutlinedIcon from "@mui/icons-material/ChatOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";
import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";

const SECTIONS = [
  {
    items: [
      { title: "Dashboard", to: "/", icon: <HomeOutlinedIcon /> },
      { title: "AI Assistant", to: "/assistant", icon: <AutoAwesomeOutlinedIcon /> },
    ],
  },
  {
    heading: "Operations",
    items: [
      { title: "Live Map", to: "/live-map", icon: <MapOutlinedIcon /> },
      { title: "Route Planning", to: "/route-planning", icon: <RouteOutlinedIcon /> },
      { title: "Emergency Alerts", to: "/alerts", icon: <CampaignOutlinedIcon /> },
      { title: "Incidents", to: "/incidents", icon: <ReportProblemOutlinedIcon /> },
      { title: "Messages", to: "/messages", icon: <ChatOutlinedIcon /> },
    ],
  },
  {
    heading: "Fleet",
    items: [
      { title: "Vehicles", to: "/vehicles", icon: <LocalShippingOutlinedIcon /> },
      { title: "Locations", to: "/locations", icon: <PlaceOutlinedIcon /> },
      { title: "Guards", to: "/guards", icon: <BadgeOutlinedIcon /> },
    ],
  },
  {
    heading: "Analytics",
    items: [
      { title: "Patrol Records", to: "/records", icon: <HistoryOutlinedIcon /> },
      { title: "Reports", to: "/reports", icon: <AssessmentOutlinedIcon /> },
    ],
  },
];

const Sidebar = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <Box
      sx={{
        "& .pro-sidebar-inner": { background: `${colors.primary[400]} !important` },
        "& .pro-icon-wrapper": { backgroundColor: "transparent !important" },
        "& .pro-inner-item": { padding: "5px 35px 5px 20px !important" },
        "& .pro-inner-item:hover": { color: "#868dfb !important" },
        "& .pro-menu-item.active": { color: "#6870fa !important" },
      }}
    >
      <ProSidebar collapsed={isCollapsed}>
        <Menu iconShape="square">
          <MenuItem
            onClick={() => setIsCollapsed(!isCollapsed)}
            icon={isCollapsed ? <MenuOutlinedIcon /> : undefined}
            style={{ margin: "10px 0 20px 0", color: colors.grey[100] }}
          >
            {!isCollapsed && (
              <Box display="flex" justifyContent="space-between" alignItems="center" ml="15px">
                <Box display="flex" alignItems="center" gap="8px">
                  <ShieldOutlinedIcon />
                  <Typography variant="h4" color={colors.grey[100]}>
                    Patrol Ops
                  </Typography>
                </Box>
                <IconButton onClick={() => setIsCollapsed(!isCollapsed)}>
                  <MenuOutlinedIcon />
                </IconButton>
              </Box>
            )}
          </MenuItem>

          {!isCollapsed && user && (
            <Box mb="20px" textAlign="center">
              <Typography variant="h4" color={colors.grey[100]} fontWeight="bold">
                {[user.first_name, user.last_name].filter(Boolean).join(" ") || user.username}
              </Typography>
              <Typography variant="h6" color={colors.greenAccent[500]}>
                Command centre admin
              </Typography>
            </Box>
          )}

          <Box paddingLeft={isCollapsed ? undefined : "6%"}>
            {SECTIONS.map((section, i) => (
              <Box key={i}>
                {section.heading && !isCollapsed && (
                  <Typography variant="h6" color={colors.grey[300]} sx={{ m: "15px 0 5px 20px" }}>
                    {section.heading}
                  </Typography>
                )}
                {section.items.map((item) => (
                  <MenuItem
                    key={item.to}
                    active={item.to === "/" ? pathname === "/" : pathname.startsWith(item.to)}
                    style={{ color: colors.grey[100] }}
                    icon={item.icon}
                  >
                    <Typography>{item.title}</Typography>
                    <Link to={item.to} />
                  </MenuItem>
                ))}
              </Box>
            ))}
          </Box>
        </Menu>
      </ProSidebar>
    </Box>
  );
};

export default Sidebar;
