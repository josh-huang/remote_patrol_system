import { useEffect, useState } from "react";
import { Box, Button, Chip, IconButton, Tooltip } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import Header from "../../components/Header";
import DataTable from "../../components/DataTable";
import FormDialog from "../../components/FormDialog";
import RowActions from "../../components/RowActions";
import RouteMap from "../../components/RouteMap";
import Panel from "../../components/Panel";
import api from "../../api/client";
import { errorMessage, fetchList } from "../../api/resources";

const PRIORITIES = [
  { value: 1, label: "1 — normal" },
  { value: 2, label: "2 — elevated" },
  { value: 3, label: "3 — high" },
  { value: 4, label: "4 — very high" },
  { value: 5, label: "5 — critical" },
];

const FIELDS = [
  { name: "name", label: "Site name", required: true },
  { name: "address", label: "Address" },
  { name: "latitude", label: "Latitude", type: "number", required: true },
  { name: "longitude", label: "Longitude", type: "number", required: true },
  { name: "priority", label: "Priority", type: "select", options: PRIORITIES, helperText: "Higher priority sites are visited first." },
  { name: "contact_number", label: "Site contact number" },
  { name: "is_active", label: "Active (include in patrols)", type: "checkbox" },
];

const EMPTY = { priority: 1, is_active: true, latitude: 1.3521, longitude: 103.8198 };

const Locations = () => {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null);

  const load = () => fetchList("/locations/").then(setRows);
  useEffect(() => {
    load();
  }, []);

  const save = async (form) => {
    const { image, active_alerts, emergency_trigger, created_at, ...body } = form;
    if (form.id) await api.patch(`/locations/${form.id}/`, body);
    else await api.post("/locations/", body);
    load();
  };

  const remove = async (row) => {
    if (!window.confirm(`Remove site ${row.name}?`)) return;
    await api.delete(`/locations/${row.id}/`);
    load();
  };

  const trigger = async (row) => {
    const description = window.prompt(`Raise an emergency alert at ${row.name}? Describe the alarm:`, "Alarm triggered");
    if (description === null) return;
    try {
      await api.post(`/locations/${row.id}/trigger_emergency/`, { description });
      load();
    } catch (e) {
      window.alert(errorMessage(e));
    }
  };

  const columns = [
    { field: "name", headerName: "Site", flex: 1.3 },
    { field: "address", headerName: "Address", flex: 1.3 },
    { field: "priority", headerName: "Priority", flex: 0.5 },
    {
      field: "emergency_trigger",
      headerName: "Emergency",
      flex: 0.7,
      renderCell: ({ value }) => (value ? <Chip size="small" color="error" label="ACTIVE" /> : "—"),
    },
    { field: "is_active", headerName: "Active", flex: 0.5, renderCell: ({ value }) => (value ? "Yes" : "No") },
    {
      field: "coords",
      headerName: "Coordinates",
      flex: 1,
      valueGetter: ({ row }) => `${row.latitude.toFixed(4)}, ${row.longitude.toFixed(4)}`,
    },
    {
      field: "actions",
      headerName: "",
      sortable: false,
      width: 140,
      renderCell: ({ row }) => (
        <RowActions onEdit={() => setEditing(row)} onDelete={() => remove(row)}>
          <Tooltip title="Trigger emergency alarm">
            <IconButton size="small" color="error" onClick={() => trigger(row)}>
              <CampaignOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </RowActions>
      ),
    },
  ];

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="LOCATIONS" subtitle="Patrol sites, their priority and emergency status" />
        <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={() => setEditing(EMPTY)}>
          Add site
        </Button>
      </Box>
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", xl: "3fr 2fr" }} gap="16px">
        <DataTable rows={rows} columns={columns} />
        <Panel title="Site map">
          <RouteMap sites={rows.filter((r) => r.is_active)} height={520} />
        </Panel>
      </Box>
      <FormDialog
        open={Boolean(editing)}
        title={editing?.id ? `Edit ${editing.name}` : "Add site"}
        fields={FIELDS}
        initial={editing}
        onClose={() => setEditing(null)}
        onSubmit={save}
      />
    </Box>
  );
};

export default Locations;
