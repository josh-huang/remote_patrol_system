import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  TextField,
} from "@mui/material";
import { errorMessage } from "../api/resources";

/**
 * Generic create/edit dialog.
 *   fields: [{ name, label, type: "text"|"number"|"password"|"select"|"checkbox"|"textarea",
 *              options: [{value, label}], required, helperText, createOnly }]
 */
const FormDialog = ({ open, title, fields, initial, onClose, onSubmit, submitLabel = "Save" }) => {
  const [form, setForm] = useState(initial || {});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const editing = Boolean(initial?.id);

  useEffect(() => {
    if (open) {
      setForm(initial || {});
      setError("");
    }
  }, [open, initial]);

  const set = (name, value) => setForm((f) => ({ ...f, [name]: value }));

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await onSubmit(form);
      onClose();
    } catch (e) {
      setError(errorMessage(e, "Could not save."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: "8px !important" }}>
        {error && <Alert severity="error">{error}</Alert>}
        {fields
          .filter((f) => !(f.createOnly && editing))
          .map((f) =>
            f.type === "checkbox" ? (
              <FormControlLabel
                key={f.name}
                control={<Checkbox checked={Boolean(form[f.name])} onChange={(e) => set(f.name, e.target.checked)} />}
                label={f.label}
              />
            ) : (
              <TextField
                key={f.name}
                label={f.label}
                required={f.required}
                type={f.type === "select" || f.type === "textarea" ? undefined : f.type || "text"}
                select={f.type === "select"}
                multiline={f.type === "textarea"}
                minRows={f.type === "textarea" ? 3 : undefined}
                helperText={f.helperText}
                value={form[f.name] ?? ""}
                onChange={(e) => set(f.name, e.target.value)}
              >
                {f.type === "select" &&
                  (f.options || []).map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.label}
                    </MenuItem>
                  ))}
              </TextField>
            )
          )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={submit} variant="contained" color="secondary" disabled={busy}>
          {busy ? "Saving…" : submitLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FormDialog;
