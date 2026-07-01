import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Switch,
  TextField,
  useTheme,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { DataGrid } from "@mui/x-data-grid";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import api from "../../api/client";

const emptyForm = {
  name: "",
  address: "",
  latitude: "",
  longitude: "",
  priority: 1,
  emergency_trigger: false,
};

const Locations = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = () =>
    api.get("/locations/").then((res) => setRows(res.data.results || res.data));

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    await api.post("/locations/", {
      ...form,
      latitude: parseFloat(form.latitude),
      longitude: parseFloat(form.longitude),
      priority: parseInt(form.priority, 10),
    });
    setOpen(false);
    setForm(emptyForm);
    load();
  };

  const columns = [
    { field: "name", headerName: "Name", flex: 1.2 },
    { field: "address", headerName: "Address", flex: 1.5 },
    { field: "priority", headerName: "Priority", flex: 0.6 },
    {
      field: "emergency_trigger",
      headerName: "Emergency",
      flex: 0.8,
      renderCell: (p) => (p.value ? "⚠ Yes" : "No"),
    },
    { field: "latitude", headerName: "Lat", flex: 0.8 },
    { field: "longitude", headerName: "Lng", flex: 0.8 },
  ];

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="LOCATIONS" subtitle="Patrol checkpoints & priorities" />
        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => setOpen(true)}
        >
          Add Location
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
        <DialogTitle>Add Location</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextField
            label="Address"
            value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
          />
          <TextField
            label="Latitude"
            value={form.latitude}
            onChange={(e) => setForm({ ...form, latitude: e.target.value })}
          />
          <TextField
            label="Longitude"
            value={form.longitude}
            onChange={(e) => setForm({ ...form, longitude: e.target.value })}
          />
          <TextField
            label="Priority (higher = earlier)"
            type="number"
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.emergency_trigger}
                onChange={(e) =>
                  setForm({ ...form, emergency_trigger: e.target.checked })
                }
              />
            }
            label="Emergency trigger (force to front of route)"
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

export default Locations;
