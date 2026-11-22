import React, {useEffect} from "react";
import L from "leaflet";
import {TileLayer, useMap} from "react-leaflet";

const MAPTILER_API_KEY = (import.meta.env.M_API_KEY || "").trim();
const MAPTILER_ATTRIBUTION = '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
const HEAT_GRADIENT = {0.2: "#2563eb", 0.45: "#16a34a", 0.7: "#fde047", 1: "#dc2626"};
const DEFAULT_HEAT_WEIGHT = () => 1;

export const hasSatelliteTiles = Boolean(MAPTILER_API_KEY);

export function HeatLayer({points, weightForPoint = DEFAULT_HEAT_WEIGHT}) {
  const map = useMap();
  useEffect(() => {
    let disposed = false;
    let layer;
    window.L = L;
    import("leaflet.heat").then(() => {
      if (disposed || !points.length) return;
      layer = L.heatLayer(points.map(point => [point.latitude, point.longitude, weightForPoint(point)]), {
        radius: 28, blur: 20, maxZoom: 19, minOpacity: 0.35, gradient: HEAT_GRADIENT,
      }).addTo(map);
    });
    return () => {disposed = true; if (layer) map.removeLayer(layer);};
  }, [map, points, weightForPoint]);
  return null;
}

export function Basemap({satellite, onFailure}) {
  return satellite
    ? <TileLayer tileSize={512} zoomOffset={-1} minZoom={1} maxZoom={22} attribution={MAPTILER_ATTRIBUTION} crossOrigin eventHandlers={{tileerror: onFailure}} url={`https://api.maptiler.com/maps/satellite-v4/{z}/{x}/{y}.jpg?key=${encodeURIComponent(MAPTILER_API_KEY)}`}/>
    : <TileLayer maxNativeZoom={19} maxZoom={22} attribution={OSM_ATTRIBUTION} url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>;
}
