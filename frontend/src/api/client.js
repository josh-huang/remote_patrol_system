import axios from "axios";

const baseURL =
  process.env.REACT_APP_API_BASE_URL || "http://localhost:8000/api/v1";

const api = axios.create({ baseURL });

// Attach the JWT access token to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Transparently refresh the access token on a 401 once.
let isRefreshing = false;
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      localStorage.getItem("refresh_token")
    ) {
      original._retry = true;
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const { data } = await axios.post(`${baseURL}/auth/token/refresh/`, {
            refresh: localStorage.getItem("refresh_token"),
          });
          localStorage.setItem("access_token", data.access);
        } catch (e) {
          localStorage.clear();
          window.location.href = "/login";
        } finally {
          isRefreshing = false;
        }
      }
      original.headers.Authorization = `Bearer ${localStorage.getItem(
        "access_token"
      )}`;
      return api(original);
    }
    return Promise.reject(error);
  }
);

export default api;
