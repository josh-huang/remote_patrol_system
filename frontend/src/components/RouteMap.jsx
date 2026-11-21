import { useMemo, useState } from "react";
import { Box, Typography, useTheme } from "@mui/material";
import {
  GoogleMap,
  InfoWindowF,
  MarkerF,
  PolylineF,
  useJsApiLoader,
} from "@react-google-maps/api";
import { tokens } from "../theme";

const MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY || "";
const SINGAPORE = { lat: 1.3521, lng: 103.8198 };

/**
 * Map of patrol sites, vehicles and routes.
 *
 * Uses Google Maps when REACT_APP_GOOGLE_MAPS_API_KEY is set; otherwise falls
 * back to a schematic SVG projection so routes are always visible.
 *
 *   sites:    [{id, name, latitude, longitude, priority, emergency_trigger}]
 *   vehicles: [{id, plate_number, current_latitude, current_longitude, color}]
 *   routes:   [{key, color, label, points: [{lat, lng, label, visited}]}]
 */
const RouteMap = (props) =>
  MAPS_KEY ? <GoogleRouteMap {...props} /> : <SchematicMap {...props} />;

const GoogleRouteMap = ({ sites = [], vehicles = [], routes = [], height = 480 }) => {
  const { isLoaded } = useJsApiLoader({ googleMapsApiKey: MAPS_KEY });
  const [active, setActive] = useState(null);

  const onLoad = (map) => {
    const points = [
      ...sites.map((s) => ({ lat: s.latitude, lng: s.longitude })),
      ...vehicles.filter((v) => v.current_latitude).map((v) => ({ lat: v.current_latitude, lng: v.current_longitude })),
    ];
    if (points.length > 1) {
      const bounds = new window.google.maps.LatLngBounds();
      points.forEach((p) => bounds.extend(p));
      map.fitBounds(bounds);
    }
  };

  if (!isLoaded) return <Box p={2}>Loading map…</Box>;

  return (
    <GoogleMap
      mapContainerStyle={{ width: "100%", height, borderRadius: 8 }}
      center={SINGAPORE}
      zoom={11}
      onLoad={onLoad}
    >
      {routes.map((r) => (
        <PolylineF
          key={r.key}
          path={r.points}
          options={{ strokeColor: r.color, strokeWeight: 4, strokeOpacity: 0.85 }}
        />
      ))}
      {sites.map((s) => (
        <MarkerF
          key={`s${s.id}`}
          position={{ lat: s.latitude, lng: s.longitude }}
          onClick={() => setActive({ title: s.name, body: `Priority ${s.priority}${s.emergency_trigger ? " · EMERGENCY" : ""}`, lat: s.latitude, lng: s.longitude })}
          icon={{
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: s.emergency_trigger ? 9 : 6,
            fillColor: s.emergency_trigger ? "#db4f4a" : "#ffffff",
            fillOpacity: 1,
            strokeColor: "#141b2d",
            strokeWeight: 2,
          }}
        />
      ))}
      {vehicles
        .filter((v) => v.current_latitude)
        .map((v) => (
          <MarkerF
            key={`v${v.id}`}
            position={{ lat: v.current_latitude, lng: v.current_longitude }}
            label={{ text: v.plate_number, fontSize: "11px", fontWeight: "700" }}
            onClick={() =>
              setActive({
                title: v.plate_number,
                body: `${v.driver_name || "No driver"} · ${v.maintenance_status || ""}`,
                lat: v.current_latitude,
                lng: v.current_longitude,
              })
            }
          />
        ))}
      {active && (
        <InfoWindowF position={{ lat: active.lat, lng: active.lng }} onCloseClick={() => setActive(null)}>
          <div style={{ color: "#111" }}>
            <strong>{active.title}</strong>
            <br />
            {active.body}
          </div>
        </InfoWindowF>
      )}
    </GoogleMap>
  );
};

const SchematicMap = ({ sites = [], vehicles = [], routes = [], height = 480 }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const W = 1000;
  const H = 560;
  const PAD = 40;

  const project = useMemo(() => {
    const pts = [
      ...sites.map((s) => [s.latitude, s.longitude]),
      ...vehicles.filter((v) => v.current_latitude).map((v) => [v.current_latitude, v.current_longitude]),
      ...routes.flatMap((r) => r.points.map((p) => [p.lat, p.lng])),
    ];
    if (!pts.length) return () => [W / 2, H / 2];
    const lats = pts.map((p) => p[0]);
    const lngs = pts.map((p) => p[1]);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const kx = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
    const spanX = Math.max((maxLng - minLng) * kx, 1e-3);
    const spanY = Math.max(maxLat - minLat, 1e-3);
    const scale = Math.min((W - 2 * PAD) / spanX, (H - 2 * PAD) / spanY);
    const offX = (W - spanX * scale) / 2;
    const offY = (H - spanY * scale) / 2;
    return (lat, lng) => [offX + (lng - minLng) * kx * scale, H - offY - (lat - minLat) * scale];
  }, [sites, vehicles, routes]);

  return (
    <Box position="relative">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ height, background: colors.primary[500], borderRadius: 8 }}>
        {routes.map((r) => {
          const d = r.points.map((p) => project(p.lat, p.lng).join(",")).join(" ");
          return (
            <g key={r.key}>
              <polyline points={d} fill="none" stroke={r.color} strokeWidth={4} strokeOpacity={0.85} strokeLinejoin="round" />
              {r.points.map((p, i) => {
                const [x, y] = project(p.lat, p.lng);
                return (
                  <text key={i} x={x + 8} y={y - 8} fontSize={13} fill={r.color} fontWeight={700}>
                    {p.order ?? ""}
                  </text>
                );
              })}
            </g>
          );
        })}
        {sites.map((s) => {
          const [x, y] = project(s.latitude, s.longitude);
          return (
            <g key={`s${s.id}`}>
              {s.emergency_trigger && (
                <circle cx={x} cy={y} r={16} fill="#db4f4a" opacity={0.35}>
                  <animate attributeName="r" values="10;20;10" dur="1.6s" repeatCount="indefinite" />
                </circle>
              )}
              <circle
                cx={x}
                cy={y}
                r={5 + Math.min(s.priority || 1, 3) * 1.5}
                fill={s.emergency_trigger ? "#db4f4a" : colors.grey[100]}
                stroke={colors.primary[500]}
                strokeWidth={2}
              >
                <title>{`${s.name} · priority ${s.priority}${s.emergency_trigger ? " · EMERGENCY" : ""}`}</title>
              </circle>
              <text x={x + 10} y={y + 14} fontSize={12} fill={colors.grey[300]}>
                {s.name}
              </text>
            </g>
          );
        })}
        {vehicles
          .filter((v) => v.current_latitude)
          .map((v) => {
            const [x, y] = project(v.current_latitude, v.current_longitude);
            return (
              <g key={`v${v.id}`}>
                <rect x={x - 9} y={y - 9} width={18} height={18} rx={4} fill={v.color || colors.blueAccent[500]} stroke="#fff" strokeWidth={2}>
                  <title>{`${v.plate_number} · ${v.driver_name || "no driver"}`}</title>
                </rect>
                <text x={x - 9} y={y - 14} fontSize={13} fontWeight={700} fill={colors.grey[100]}>
                  {v.plate_number}
                </text>
              </g>
            );
          })}
      </svg>
      <Typography variant="caption" color={colors.grey[400]} position="absolute" bottom={8} left={12}>
        Schematic view — set REACT_APP_GOOGLE_MAPS_API_KEY for Google Maps
      </Typography>
    </Box>
  );
};

/** Build map routes from plan stops (grouped by vehicle, in visiting order). */
export const routesFromStops = (stops, vehicleColor) => {
  const byVehicle = {};
  stops.forEach((s) => {
    (byVehicle[s.vehicle] = byVehicle[s.vehicle] || { plate: s.vehicle_plate, stops: [] }).stops.push(s);
  });
  return Object.entries(byVehicle).map(([vid, { plate, stops: list }]) => ({
    key: `r${vid}`,
    label: plate,
    color: vehicleColor(Number(vid)),
    points: list
      .sort((a, b) => a.order - b.order)
      .map((s) => ({ lat: s.latitude, lng: s.longitude, order: s.order + 1, visited: s.is_visited })),
  }));
};

// Plans arrive newest first; each vehicle follows its most recent active plan.
export const currentStops = (plans) => {
  const claimed = new Set();
  const result = [];
  plans.forEach((plan) => {
    const vehiclesInPlan = new Set();
    plan.stops.forEach((s) => {
      if (!claimed.has(s.vehicle)) {
        result.push(s);
        vehiclesInPlan.add(s.vehicle);
      }
    });
    vehiclesInPlan.forEach((v) => claimed.add(v));
  });
  return result;
};

export default RouteMap;
