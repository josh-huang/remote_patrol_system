import { useState } from "react";
import { ProSidebar, Menu, MenuItem } from "react-pro-sidebar";
import { Box, IconButton, Typography, useTheme } from "@mui/material";
import { Link } from "react-router-dom";
import "react-pro-sidebar/dist/css/styles.css";
import { tokens } from "../../theme";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import RouteOutlinedIcon from "@mui/icons-material/RouteOutlined";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import ReportProblemOutlinedIcon from "@mui/icons-material/ReportProblemOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";
import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";

const Item = ({ title, to, icon, selected, setSelected }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <MenuItem
      active={selected === title}
      style={{ color: colors.grey[100] }}
      onClick={() => setSelected(title)}
      icon={icon}
    >
      <Typography>{title}</Typography>
      <Link to={to} />
    </MenuItem>
  );
};

const Sidebar = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selected, setSelected] = useState("Dashboard");

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
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="center"
                ml="15px"
              >
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

<<<<<<< HEAD
=======
          {!isCollapsed && (
            <Box mb="25px">
              <Box display="flex" justifyContent="center" alignItems="center">
                <img
                  alt="profile-user"
                  width="100px"
                  height="100px"
                  src={`../../assets/user.png`}
                  style={{ cursor: "pointer", borderRadius: "50%" }}
                />
              </Box>
              <Box textAlign="center">
                <Typography
                  variant="h2"
                  color={colors.grey[100]}
                  fontWeight="bold"
                  sx={{ m: "10px 0 0 0" }}
                >
                  Joshua
                </Typography>
                <Typography variant="h5" color={colors.greenAccent[500]}>
                  Control Centre Admin
                </Typography>
              </Box>
            </Box>
          )}

>>>>>>> 02b7eceb7089738a0269c6f33ad9366e175cbf09
          <Box paddingLeft={isCollapsed ? undefined : "10%"}>
            <Item
              title="Dashboard"
              to="/"
              icon={<HomeOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
<<<<<<< HEAD
              title="AI Assistant"
              to="/assistant"
              icon={<AutoAwesomeOutlinedIcon />}
=======
              title="Manage Team"
              to="/team"
              icon={<PeopleOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            {/* <Item
              title="Contacts Information"
              to="/contacts"
              icon={<ContactsOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Invoices Balances"
              to="/invoices"
              icon={<ReceiptOutlinedIcon />}
>>>>>>> 02b7eceb7089738a0269c6f33ad9366e175cbf09
              selected={selected}
              setSelected={setSelected}
            /> */}

            <Typography
              variant="h6"
              color={colors.grey[300]}
              sx={{ m: "15px 0 5px 20px" }}
            >
              Fleet
            </Typography>
            <Item
              title="Vehicles"
              to="/vehicles"
              icon={<LocalShippingOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Locations"
              to="/locations"
              icon={<PlaceOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />

            <Typography
              variant="h6"
              color={colors.grey[300]}
              sx={{ m: "15px 0 5px 20px" }}
            >
              Operations
            </Typography>
            <Item
              title="Route Planning"
              to="/route-planning"
              icon={<RouteOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Live Map"
              to="/live-map"
              icon={<MapOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
            <Item
              title="Incidents"
              to="/incidents"
              icon={<ReportProblemOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />

            <Typography
              variant="h6"
              color={colors.grey[300]}
              sx={{ m: "15px 0 5px 20px" }}
            >
              Analytics
            </Typography>
            <Item
              title="Reports"
              to="/reports"
              icon={<AssessmentOutlinedIcon />}
              selected={selected}
              setSelected={setSelected}
            />
          </Box>
        </Menu>
      </ProSidebar>
    </Box>
  );
};

export default Sidebar;
