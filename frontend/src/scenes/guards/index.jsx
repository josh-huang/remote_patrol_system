import { useEffect, useState } from "react";
import { Box, Button } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import Header from "../../components/Header";
import DataTable from "../../components/DataTable";
import FormDialog from "../../components/FormDialog";
import RowActions from "../../components/RowActions";
import api from "../../api/client";
import { fetchList } from "../../api/resources";

const Guards = () => {
  const [rows, setRows] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [editing, setEditing] = useState(null);

  const load = () => fetchList("/guards/").then(setRows);
  useEffect(() => {
    load();
    fetchList("/vehicles/").then(setVehicles);
  }, []);

  const fields = [
    { name: "username", label: "Login username", required: true, createOnly: true },
    { name: "password", label: "Password", type: "password", helperText: "Leave blank to keep the current password." },
    { name: "first_name", label: "First name" },
    { name: "last_name", label: "Last name" },
    { name: "phone", label: "Phone" },
    { name: "badge_number", label: "Badge number", required: true },
    {
      name: "assigned_vehicle",
      label: "Linked vehicle (duty phone)",
      type: "select",
      options: [{ value: "", label: "— none —" }, ...vehicles.map((v) => ({ value: v.id, label: v.plate_number }))],
    },
    { name: "is_driver", label: "Driver in charge", type: "checkbox" },
    { name: "on_duty", label: "On duty", type: "checkbox" },
    { name: "is_available", label: "Available", type: "checkbox" },
  ];

  const toForm = (row) => ({
    ...row,
    first_name: row.user.first_name,
    last_name: row.user.last_name,
    phone: row.user.phone,
    assigned_vehicle: row.assigned_vehicle ?? "",
  });

  const save = async (form) => {
    const body = { ...form, assigned_vehicle: form.assigned_vehicle || null };
    delete body.user;
    if (!body.password) delete body.password;
    if (form.id) await api.patch(`/guards/${form.id}/`, body);
    else await api.post("/guards/", body);
    load();
  };

  const remove = async (row) => {
    if (!window.confirm(`Remove ${row.full_name} and their login?`)) return;
    await api.delete(`/guards/${row.id}/`);
    load();
  };

  const columns = [
    { field: "full_name", headerName: "Name", flex: 1 },
    { field: "username", headerName: "Login", flex: 0.8, valueGetter: ({ row }) => row.user.username },
    { field: "badge_number", headerName: "Badge", flex: 0.6 },
    { field: "phone", headerName: "Phone", flex: 0.8, valueGetter: ({ row }) => row.user.phone || "—" },
    { field: "vehicle_plate", headerName: "Vehicle", flex: 0.8, valueGetter: ({ value }) => value || "—" },
    { field: "is_driver", headerName: "Driver", flex: 0.5, renderCell: ({ value }) => (value ? "Yes" : "No") },
    { field: "on_duty", headerName: "On duty", flex: 0.5, renderCell: ({ value }) => (value ? "Yes" : "No") },
    {
      field: "actions",
      headerName: "",
      sortable: false,
      width: 100,
      renderCell: ({ row }) => <RowActions onEdit={() => setEditing(toForm(row))} onDelete={() => remove(row)} />,
    },
  ];

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="SECURITY GUARDS" subtitle="Duty-phone accounts — each account is linked to one vehicle" />
        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => setEditing({ is_available: true, is_driver: false, on_duty: false, assigned_vehicle: "" })}
        >
          Add guard
        </Button>
      </Box>
      <DataTable rows={rows} columns={columns} />
      <FormDialog
        open={Boolean(editing)}
        title={editing?.id ? `Edit ${editing.full_name}` : "Add guard"}
        fields={fields}
        initial={editing}
        onClose={() => setEditing(null)}
        onSubmit={save}
      />
    </Box>
  );
};

export default Guards;
