import api from "./client";

// Unwrap DRF pagination and fetch large pages for lookup lists.
export const fetchList = (path, params = {}) =>
  api
    .get(path, { params: { page_size: 500, ...params } })
    .then((r) => (Array.isArray(r.data) ? r.data : r.data.results || []));

export const errorMessage = (e, fallback = "Request failed.") => {
  const data = e?.response?.data;
  if (!data) return fallback;
  if (typeof data === "string") return fallback;
  if (data.detail) return data.detail;
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : JSON.stringify(v)}`)
    .join("; ");
};

export const ALGORITHMS = [
  { value: "dijkstra", label: "Dijkstra" },
  { value: "bellman_ford", label: "Bellman-Ford" },
  { value: "floyd_warshall", label: "Floyd-Warshall" },
];

export const ENGINE_TYPES = ["petrol", "diesel", "hybrid", "electric"];
export const HEALTH_STATUSES = [
  { value: "healthy", label: "Healthy" },
  { value: "due", label: "Service due" },
  { value: "in_service", label: "In service" },
  { value: "out_of_service", label: "Out of service" },
];

// One stable colour per vehicle for maps and charts.
export const ROUTE_COLORS = [
  "#4cceac",
  "#6870fa",
  "#f2b134",
  "#db4f4a",
  "#a259ff",
  "#2ec4f1",
  "#ff8a3d",
  "#8bd346",
];
export const colorFor = (index) => ROUTE_COLORS[index % ROUTE_COLORS.length];

export const fmt = (n, digits = 1) =>
  n === null || n === undefined || Number.isNaN(n) ? "–" : Number(n).toFixed(digits);
