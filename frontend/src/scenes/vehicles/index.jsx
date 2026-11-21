import { useEffect, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import Header from "../../components/Header";
import DataTable from "../../components/DataTable";
import FormDialog from "../../components/FormDialog";
import RowActions from "../../components/RowActions";
import StatusChip from "../../components/StatusChip";
import api from "../../api/client";
import { ENGINE_TYPES, HEALTH_STATUSES, errorMessage, fetchList, fmt } from "../../api/resources";

const FIELDS = [
  { name: "plate_number", label: "Car plate number", required: true },
  { name: "model_name", label: "Model" },
  { name: "contact_number", label: "Vehicle contact number" },
  { name: "engine_type", label: "Engine type", type: "select", options: ENGINE_TYPES.map((t) => ({ value: t, label: t })) },
  { name: "maintenance_status", label: "Health status", type: "select", options: HEALTH_STATUSES },
  { name: "odometer_km", label: "Odometer (km)", type: "number" },
  { name: "is_available", label: "Available for duty", type: "checkbox" },
];

const EMPTY = { engine_type: "petrol", maintenance_status: "healthy", odometer_km: 0, is_available: true };

const Vehicles = () => {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null);

  const load = () => fetchList("/vehicles/").then(setRows);
  useEffect(() => {
    load();
  }, []);

  const save = async (form) => {
    if (form.id) await api.patch(`/vehicles/${form.id}/`, form);
    else await api.post("/vehicles/", form);
    load();
  };

  const remove = async (row) => {
    if (!window.confirm(`Remove vehicle ${row.plate_number}?`)) return;
    try {
      await api.delete(`/vehicles/${row.id}/`);
      load();
    } catch (e) {
      window.alert(errorMessage(e));
    }
  };

  const columns = [
    {
      field: "plate_number",
      headerName: "Car plate",
      flex: 1,
      renderCell: ({ row }) => (
        <Box>
          <Typography fontWeight={700}>{row.plate_number}</Typography>
          <Typography variant="caption">{row.model_name}</Typography>
        </Box>
      ),
    },
    { field: "driver_name", headerName: "Driver in charge", flex: 1, valueGetter: ({ row }) => row.driver_name || "—" },
    {
      field: "contact",
      headerName: "Contact number",
      flex: 1,
      valueGetter: ({ row }) => row.driver_phone || row.contact_number || "—",
    },
    { field: "engine_type", headerName: "Engine", flex: 0.7 },
    {
      field: "maintenance_status",
      headerName: "Health status",
      flex: 0.9,
      renderCell: ({ value }) => <StatusChip value={value} />,
    },
    {
      field: "is_operational",
      headerName: "On duty",
      flex: 0.6,
      renderCell: ({ value }) => (value ? "Yes" : "No"),
    },
    { field: "next", headerName: "Next location", flex: 1.2, valueGetter: ({ row }) => row.next_location?.name || "—" },
    { field: "route_mileage_km", headerName: "This patrol (km)", flex: 0.8, valueFormatter: ({ value }) => fmt(value) },
    { field: "patrol_mileage_km", headerName: "Patrol km (total)", flex: 0.8, valueFormatter: ({ value }) => fmt(value, 0) },
    { field: "odometer_km", headerName: "Odometer (km)", flex: 0.8, valueFormatter: ({ value }) => fmt(value, 0) },
    {
      field: "actions",
      headerName: "",
      sortable: false,
      width: 100,
      renderCell: ({ row }) => <RowActions onEdit={() => setEditing(row)} onDelete={() => remove(row)} />,
    },
  ];

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="VEHICLES" subtitle="Patrol fleet — vehicles in service/out of service are excluded from planning" />
        <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={() => setEditing(EMPTY)}>
          Add vehicle
        </Button>
      </Box>
      <DataTable rows={rows} columns={columns} rowHeight={60} />
      <FormDialog
        open={Boolean(editing)}
        title={editing?.id ? `Edit ${editing.plate_number}` : "Add vehicle"}
        fields={FIELDS}
        initial={editing}
        onClose={() => setEditing(null)}
        onSubmit={save}
      />
    </Box>
  );
};

export default Vehicles;
