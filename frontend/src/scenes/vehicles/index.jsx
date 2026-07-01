import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  TextField,
  useTheme,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { DataGrid } from "@mui/x-data-grid";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";

const ENGINE_TYPES = ["petrol", "diesel", "hybrid", "electric"];
const STATUSES = ["healthy", "due", "in_service", "out_of_service"];

const Vehicles = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    plate_number: "",
    contact_number: "",
    engine_type: "petrol",
    maintenance_status: "healthy",
    odometer_km: 0,
  });

  const load = () =>
    api.get("/vehicles/").then((res) => setRows(res.data.results || res.data));

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    await api.post("/vehicles/", form);
    setOpen(false);
    setForm({
      plate_number: "",
      contact_number: "",
      engine_type: "petrol",
      maintenance_status: "healthy",
      odometer_km: 0,
    });
    load();
  };

  const columns = [
    { field: "plate_number", headerName: "Plate", flex: 1 },
    { field: "engine_type", headerName: "Engine", flex: 1 },
    { field: "maintenance_status", headerName: "Status", flex: 1 },
    { field: "driver_name", headerName: "Driver", flex: 1 },
    { field: "contact_number", headerName: "Contact", flex: 1 },
    {
      field: "odometer_km",
      headerName: "Odometer (km)",
      flex: 1,
      valueFormatter: (p) => Math.round(p.value),
    },
    {
      field: "is_available",
      headerName: "Available",
      flex: 0.6,
      renderCell: (p) => (p.value ? "Yes" : "No"),
    },
  ];

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="VEHICLES" subtitle="Manage the patrol fleet" />
        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => setOpen(true)}
        >
          Add Vehicle
        </Button>
      </Box>
      <Box
        height="70vh"
        sx={{
          "& .MuiDataGrid-root": { border: "none" },
          "& .MuiDataGrid-columnHeaders": {
            backgroundColor: colors.blueAccent[700],
          },
          "& .MuiDataGrid-footerContainer": {
            backgroundColor: colors.blueAccent[700],
          },
        }}
      >
        <DataGrid rows={rows} columns={columns} getRowId={(r) => r.id} />
      </Box>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add Vehicle</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="Plate Number"
            value={form.plate_number}
            onChange={(e) => setForm({ ...form, plate_number: e.target.value })}
          />
          <TextField
            label="Contact Number"
            value={form.contact_number}
            onChange={(e) => setForm({ ...form, contact_number: e.target.value })}
          />
          <TextField
            select
            label="Engine Type"
            value={form.engine_type}
            onChange={(e) => setForm({ ...form, engine_type: e.target.value })}
          >
            {ENGINE_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Maintenance Status"
            value={form.maintenance_status}
            onChange={(e) =>
              setForm({ ...form, maintenance_status: e.target.value })
            }
          >
            {STATUSES.map((t) => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Odometer (km)"
            type="number"
            value={form.odometer_km}
            onChange={(e) => setForm({ ...form, odometer_km: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={handleCreate} variant="contained" color="secondary">
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Vehicles;
