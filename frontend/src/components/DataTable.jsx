import { Box, useTheme } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { tokens } from "../theme";

// DataGrid with the dashboard's theme applied.
const DataTable = ({ height = "65vh", ...props }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  return (
    <Box
      height={height}
      sx={{
        "& .MuiDataGrid-root": { border: "none" },
        "& .MuiDataGrid-cell": { borderBottom: "none" },
        "& .MuiDataGrid-columnHeaders": { backgroundColor: colors.blueAccent[700], borderBottom: "none" },
        "& .MuiDataGrid-virtualScroller": { backgroundColor: colors.primary[400] },
        "& .MuiDataGrid-footerContainer": { borderTop: "none", backgroundColor: colors.blueAccent[700] },
      }}
    >
      <DataGrid
        pageSize={25}
        rowsPerPageOptions={[25, 50, 100]}
        disableSelectionOnClick
        getRowId={(r) => r.id}
        {...props}
      />
    </Box>
  );
};

export default DataTable;
