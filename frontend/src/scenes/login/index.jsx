import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Alert,
  useTheme,
} from "@mui/material";
import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import { tokens } from "../../theme";
import { useAuth } from "../../context/AuthContext";

const Login = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin12345");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      width="100%"
    >
      <Paper
        elevation={4}
        sx={{
          p: 4,
          width: 380,
          backgroundColor: colors.primary[400],
        }}
      >
        <Box textAlign="center" mb={3}>
          <ShieldOutlinedIcon sx={{ fontSize: 48, color: colors.greenAccent[400] }} />
          <Typography variant="h3" fontWeight="bold">
            Remote Patrol System
          </Typography>
          <Typography variant="body2" color={colors.grey[300]}>
            Command Center Sign In
          </Typography>
        </Box>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="Username"
            margin="normal"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <TextField
            fullWidth
            label="Password"
            type="password"
            margin="normal"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            color="secondary"
            disabled={loading}
            sx={{ mt: 3, py: 1.2 }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </Button>
        </form>
        <Typography variant="caption" color={colors.grey[300]} display="block" mt={2}>
          Demo: admin / admin12345
        </Typography>
      </Paper>
    </Box>
  );
};

export default Login;
