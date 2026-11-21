import { useEffect, useState } from "react";
import { Box, Dialog, DialogContent, DialogTitle, MenuItem, TextField, Typography } from "@mui/material";
import PhotoLibraryOutlinedIcon from "@mui/icons-material/PhotoLibraryOutlined";
import Header from "../../components/Header";
import DataTable from "../../components/DataTable";
import { fetchList, fmt } from "../../api/resources";

const Records = () => {
  const [rows, setRows] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [filters, setFilters] = useState({ vehicle: "", from: "", to: "" });
  const [photos, setPhotos] = useState(null);

  useEffect(() => {
    fetchList("/vehicles/").then(setVehicles);
  }, []);

  useEffect(() => {
    const params = { ordering: "-created_at" };
    if (filters.vehicle) params.vehicle = filters.vehicle;
    if (filters.from) params.created_at__date__gte = filters.from;
    if (filters.to) params.created_at__date__lte = filters.to;
    fetchList("/records/", params).then(setRows);
  }, [filters]);

  const columns = [
    { field: "created_at", headerName: "Visited at", flex: 1, valueFormatter: ({ value }) => new Date(value).toLocaleString() },
    { field: "vehicle_plate", headerName: "Vehicle", flex: 0.7 },
    { field: "location_name", headerName: "Site", flex: 1.2 },
    { field: "guard_name", headerName: "Guard", flex: 0.9, valueGetter: ({ value }) => value || "—" },
    { field: "plan_name", headerName: "Plan", flex: 1.1, valueGetter: ({ value }) => value || "—" },
    { field: "distance_km", headerName: "Leg km", flex: 0.5, valueFormatter: ({ value }) => fmt(value, 2) },
    { field: "emission_kg", headerName: "CO2e kg", flex: 0.5, valueFormatter: ({ value }) => fmt(value, 3) },
    { field: "notes", headerName: "Notes", flex: 1 },
    {
      field: "images",
      headerName: "Photos",
      flex: 0.5,
      renderCell: ({ row }) =>
        row.images.length ? (
          <Box display="flex" alignItems="center" gap={0.5} sx={{ cursor: "pointer" }} onClick={() => setPhotos(row)}>
            <PhotoLibraryOutlinedIcon fontSize="small" /> {row.images.length}
          </Box>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <Box m="20px">
      <Header title="PATROL RECORDS" subtitle="Past site visits with the photos guards submitted from the duty phone" />
      <Box display="flex" gap={2} mb={2} flexWrap="wrap">
        <TextField select label="Vehicle" value={filters.vehicle} onChange={(e) => setFilters({ ...filters, vehicle: e.target.value })} sx={{ minWidth: 180 }}>
          <MenuItem value="">All vehicles</MenuItem>
          {vehicles.map((v) => (
            <MenuItem key={v.id} value={v.id}>
              {v.plate_number}
            </MenuItem>
          ))}
        </TextField>
        <TextField type="date" label="From" InputLabelProps={{ shrink: true }} value={filters.from} onChange={(e) => setFilters({ ...filters, from: e.target.value })} />
        <TextField type="date" label="To" InputLabelProps={{ shrink: true }} value={filters.to} onChange={(e) => setFilters({ ...filters, to: e.target.value })} />
        <Typography alignSelf="center" variant="body2">
          {rows.length} visit(s)
        </Typography>
      </Box>
      <DataTable rows={rows} columns={columns} />
      <Dialog open={Boolean(photos)} onClose={() => setPhotos(null)} maxWidth="md" fullWidth>
        <DialogTitle>
          {photos?.location_name} — {photos && new Date(photos.created_at).toLocaleString()}
        </DialogTitle>
        <DialogContent>
          <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(220px, 1fr))" gap={2}>
            {photos?.images.map((img) => (
              <a key={img.id} href={img.image} target="_blank" rel="noreferrer">
                <img src={img.image} alt="site" style={{ width: "100%", borderRadius: 6 }} />
              </a>
            ))}
          </Box>
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default Records;
