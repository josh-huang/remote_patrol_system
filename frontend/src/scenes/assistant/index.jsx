import { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Chip,
  IconButton,
  TextField,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  useTheme,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import BuildOutlinedIcon from "@mui/icons-material/BuildOutlined";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import {
  sendMessage,
  listPendingActions,
  confirmAction,
  rejectAction,
} from "../../api/agent";

const SUGGESTIONS = [
  "Give me a command overview",
  "Show critical incidents",
  "Where are the vehicles right now?",
  "Plan a route and dispatch vehicles",
  "Generate today's report",
];

const ActionCard = ({ action, onResolved }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [busy, setBusy] = useState(false);

  const resolve = async (fn) => {
    setBusy(true);
    try {
      const updated = await fn(action.id);
      onResolved(updated);
    } finally {
      setBusy(false);
    }
  };

  const isAuto = action.origin === "autonomous";
  const pending = action.status === "pending";

  return (
    <Box
      mt={1}
      p="12px"
      borderRadius="6px"
      border={`1px solid ${isAuto ? colors.redAccent[500] : colors.blueAccent[500]}`}
      backgroundColor={colors.primary[500]}
    >
      <Box display="flex" alignItems="center" gap={1} mb={0.5}>
        <BuildOutlinedIcon fontSize="small" />
        <Typography variant="subtitle2" fontWeight="bold">
          {action.tool_name}
        </Typography>
        {isAuto && <Chip label="AUTONOMOUS" color="error" size="small" />}
        <Chip
          label={action.status}
          size="small"
          color={pending ? "warning" : action.status === "confirmed" ? "success" : "default"}
        />
      </Box>
      <Typography variant="body2" color={colors.grey[100]}>
        {action.summary}
      </Typography>
      {pending ? (
        <Box display="flex" gap={1} mt={1}>
          <Button
            size="small"
            variant="contained"
            color="secondary"
            disabled={busy}
            onClick={() => resolve(confirmAction)}
          >
            Confirm & Execute
          </Button>
          <Button
            size="small"
            variant="outlined"
            disabled={busy}
            onClick={() => resolve(rejectAction)}
          >
            Reject
          </Button>
        </Box>
      ) : (
        action.result &&
        Object.keys(action.result).length > 0 && (
          <Typography variant="caption" color={colors.greenAccent[400]}>
            Result: {JSON.stringify(action.result)}
          </Typography>
        )
      )}
    </Box>
  );
};

const StepsTrace = ({ steps }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  if (!steps || steps.length === 0) return null;
  return (
    <Accordion sx={{ backgroundColor: colors.primary[500], mt: 1 }} disableGutters>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="caption">
          🔧 Reasoning trace — {steps.length} tool call(s)
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        {steps.map((s, i) => (
          <Box key={i} mb={1}>
            <Typography variant="caption" color={colors.greenAccent[400]}>
              {s.kind === "write" ? "✍" : "📖"} {s.tool}({JSON.stringify(s.arguments)})
            </Typography>
            {s.result && (
              <Typography
                variant="caption"
                display="block"
                color={colors.grey[300]}
                sx={{ wordBreak: "break-all" }}
              >
                → {JSON.stringify(s.result).slice(0, 300)}
              </Typography>
            )}
          </Box>
        ))}
      </AccordionDetails>
    </Accordion>
  );
};

const Assistant = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState([]);
  const endRef = useRef(null);

  const loadPending = () => listPendingActions().then(setPending);

  useEffect(() => {
    loadPending();
    const t = setInterval(loadPending, 8000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content }]);
    setBusy(true);
    try {
      const data = await sendMessage(content, conversationId);
      setConversationId(data.conversation_id);
      setMessages((m) => [...m, data.message]);
      loadPending();
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Sorry, I couldn't process that." },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const onResolved = (updated) => {
    setPending((p) => p.filter((a) => a.id !== updated.id));
    setMessages((m) =>
      m.map((msg) =>
        msg.actions
          ? {
              ...msg,
              actions: msg.actions.map((a) => (a.id === updated.id ? updated : a)),
            }
          : msg
      )
    );
  };

  const autonomous = pending.filter((a) => a.origin === "autonomous");

  return (
    <Box m="20px" display="flex" gap={2} height="calc(100vh - 90px)">
      {/* Chat column */}
      <Box flex={2} display="flex" flexDirection="column">
        <Header
          title="AI COMMAND ASSISTANT"
          subtitle="Sentinel — the agent that drives the patrol system"
        />

        <Box
          flex={1}
          overflow="auto"
          backgroundColor={colors.primary[400]}
          borderRadius="6px"
          p="16px"
        >
          {messages.length === 0 && (
            <Box>
              <Typography variant="body2" color={colors.grey[300]} mb={1}>
                Try asking:
              </Typography>
              <Box display="flex" gap={1} flexWrap="wrap">
                {SUGGESTIONS.map((s) => (
                  <Chip
                    key={s}
                    label={s}
                    onClick={() => send(s)}
                    sx={{ cursor: "pointer" }}
                  />
                ))}
              </Box>
            </Box>
          )}

          {messages.map((msg, i) => (
            <Box
              key={i}
              display="flex"
              justifyContent={msg.role === "user" ? "flex-end" : "flex-start"}
              mb={2}
            >
              <Box
                maxWidth="80%"
                p="12px 16px"
                borderRadius="10px"
                backgroundColor={
                  msg.role === "user"
                    ? colors.blueAccent[700]
                    : colors.primary[600]
                }
              >
                {msg.role === "assistant" && (
                  <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                    <AutoAwesomeIcon fontSize="small" sx={{ color: colors.greenAccent[400] }} />
                    <Typography variant="caption" color={colors.greenAccent[400]}>
                      Sentinel
                    </Typography>
                  </Box>
                )}
                <Typography variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
                  {msg.content}
                </Typography>
                {msg.role === "assistant" && <StepsTrace steps={msg.steps} />}
                {msg.actions?.map((a) => (
                  <ActionCard key={a.id} action={a} onResolved={onResolved} />
                ))}
              </Box>
            </Box>
          ))}
          {busy && (
            <Typography variant="caption" color={colors.grey[300]}>
              Sentinel is thinking…
            </Typography>
          )}
          <div ref={endRef} />
        </Box>

        <Box display="flex" gap={1} mt={1}>
          <TextField
            fullWidth
            placeholder="Ask the patrol agent…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          />
          <IconButton color="secondary" onClick={() => send()} disabled={busy}>
            <SendIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Pending actions column */}
      <Box flex={1} overflow="auto">
        <Typography variant="h5" fontWeight="600" mb={1}>
          Pending Actions
        </Typography>
        {autonomous.length > 0 && (
          <Alert severity="error" sx={{ mb: 1 }}>
            {autonomous.length} autonomous action(s) awaiting confirmation.
          </Alert>
        )}
        {pending.length === 0 ? (
          <Typography variant="body2" color={colors.grey[300]}>
            No actions pending confirmation.
          </Typography>
        ) : (
          pending.map((a) => (
            <ActionCard key={a.id} action={a} onResolved={onResolved} />
          ))
        )}
      </Box>
    </Box>
  );
};

export default Assistant;
