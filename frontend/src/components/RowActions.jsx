import { IconButton, Tooltip } from "@mui/material";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";

const RowActions = ({ onEdit, onDelete, children }) => (
  <>
    {children}
    <Tooltip title="Edit">
      <IconButton size="small" onClick={onEdit}>
        <EditOutlinedIcon fontSize="small" />
      </IconButton>
    </Tooltip>
    <Tooltip title="Remove">
      <IconButton size="small" onClick={onDelete}>
        <DeleteOutlineIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  </>
);

export default RowActions;
