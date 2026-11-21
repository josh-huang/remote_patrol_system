import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Box, Button, List, ListItemButton, ListItemText, TextField, Typography, useTheme } from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import Header from "../../components/Header";
import Panel from "../../components/Panel";
import { tokens } from "../../theme";
import api from "../../api/client";

const Messages = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [inbox, setInbox] = useState([]);
  const [vehicle, setVehicle] = useState(null);
  const [thread, setThread] = useState([]);
  const [text, setText] = useState("");
  const endRef = useRef(null);

  const loadInbox = useCallback(() => api.get("/messages/inbox/").then((r) => setInbox(r.data)), []);

  const loadThread = useCallback(async () => {
    if (!vehicle) return;
    const { data } = await api.get("/messages/", { params: { vehicle: vehicle.id } });
    setThread(data);
    if (data.some((m) => !m.from_command_centre && !m.read_at)) {
      await api.post("/messages/mark_read/", { vehicle: vehicle.id });
      loadInbox();
    }
  }, [vehicle, loadInbox]);

  useEffect(() => {
    loadInbox();
    const t = setInterval(loadInbox, 5000);
    return () => clearInterval(t);
  }, [loadInbox]);

  useEffect(() => {
    loadThread();
    const t = setInterval(loadThread, 5000);
    return () => clearInterval(t);
  }, [loadThread]);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [thread.length]);

  const send = async () => {
    if (!text.trim()) return;
    await api.post("/messages/", { vehicle: vehicle.id, body: text.trim() });
    setText("");
    loadThread();
  };

  return (
    <Box m="20px">
      <Header title="MESSAGES" subtitle="Two-way messages with the duty phone on each vehicle" />
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "280px 1fr" }} gap="16px">
        <Panel title="Vehicles">
          <List dense>
            {inbox.map((row) => (
              <ListItemButton key={row.id} selected={vehicle?.id === row.id} onClick={() => setVehicle(row)}>
                <ListItemText
                  primary={row.plate_number}
                  secondary={row.last_at ? new Date(row.last_at).toLocaleString() : "No messages yet"}
                />
                <Badge color="error" badgeContent={row.unread} />
              </ListItemButton>
            ))}
          </List>
        </Panel>
        <Panel title={vehicle ? `Conversation with ${vehicle.plate_number}` : "Select a vehicle"}>
          {vehicle && (
            <Typography variant="caption" display="block" mb={1}>
              Duty phone: {vehicle.contact_number || "—"}
            </Typography>
          )}
          <Box height="55vh" overflow="auto" display="flex" flexDirection="column" gap={1} p={1}>
            {thread.map((m) => (
              <Box
                key={m.id}
                alignSelf={m.from_command_centre ? "flex-end" : "flex-start"}
                maxWidth="70%"
                p="8px 12px"
                borderRadius="10px"
                backgroundColor={m.from_command_centre ? colors.blueAccent[700] : colors.primary[500]}
              >
                <Typography variant="body2">{m.body}</Typography>
                <Typography variant="caption" color={colors.grey[300]}>
                  {m.sender_name} · {new Date(m.created_at).toLocaleTimeString()}
                </Typography>
              </Box>
            ))}
            <div ref={endRef} />
          </Box>
          {vehicle && (
            <Box display="flex" gap={1} mt={1}>
              <TextField
                fullWidth
                size="small"
                placeholder="Message the vehicle…"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
              />
              <Button variant="contained" color="secondary" endIcon={<SendIcon />} onClick={send}>
                Send
              </Button>
            </Box>
          )}
        </Panel>
      </Box>
    </Box>
  );
};

export default Messages;
