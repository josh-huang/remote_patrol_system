import api from "./client";

export const sendMessage = (message, conversationId) =>
  api
    .post("/agent/chat/", { message, conversation_id: conversationId })
    .then((r) => r.data);

export const listPendingActions = () =>
  api
    .get("/agent/actions/", { params: { status: "pending" } })
    .then((r) => r.data.results || r.data);

export const confirmAction = (id) =>
  api.post(`/agent/actions/${id}/confirm/`).then((r) => r.data);

export const rejectAction = (id) =>
  api.post(`/agent/actions/${id}/reject/`).then((r) => r.data);
