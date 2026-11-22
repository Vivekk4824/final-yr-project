import React, {useEffect, useMemo, useState} from "react";
import {GeoJSON, MapContainer, TileLayer, Tooltip, useMap} from "react-leaflet";
import L from "leaflet";

import {getPilotLayout} from "../../services/api.js";

const MAPTILER_API_KEY = (import.meta.env.VITE_MAPTILER_API_KEY || "").trim();
const MAPTILER_ATTRIBUTION = '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
const COLORS = {AVAILABLE:"#218657", RESERVED:"#e5b93b", OCCUPIED:"#c43e3e", BLOCKED:"#788491"};

function FitGeometry({geometry}) {
  const map = useMap();
  useEffect(() => {
    if (!geometry) return;
    const bounds = L.geoJSON(geometry).getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(3), {maxZoom:20, animate:false});
  }, [geometry, map]);
  return null;
}

export default function RequestSlotPreview({zoneId, slotId}) {
  const [layout,setLayout] = useState(null), [error,setError] = useState("");
  const [basemap,setBasemap] = useState(MAPTILER_API_KEY ? "satellite" : "street");
  const [satelliteFailed,setSatelliteFailed] = useState(false);
  useEffect(() => {
    let active = true;
    setLayout(null); setError("");
    getPilotLayout(zoneId).then(value => {if (active) setLayout(value);})
      .catch(reason => {if (active) setError(reason.message || "Slot map could not be loaded.");});
    return () => {active = false;};
  }, [zoneId]);
  const requested = useMemo(() => layout?.slots?.find(slot => slot.slot_id === slotId), [layout,slotId]);
  if (!slotId) return <div className="request-slot-preview-empty">This is a zone-only request. No particular slot was selected.</div>;
  if (error) return <div className="request-slot-preview-empty" role="alert">{error}</div>;
  if (!layout) return <div className="request-slot-preview-empty" role="status">Loading requested slot map…</div>;
  if (!requested?.geometry) return <div className="request-slot-preview-empty" role="alert">Requested slot {slotId} is no longer present in the saved zone layout.</div>;
  const satellite = basemap === "satellite" && MAPTILER_API_KEY && !satelliteFailed;
  return <section className="request-slot-preview" aria-label={`Requested slot ${slotId} map`}>
    <div className="request-slot-preview-heading"><div><span>Requested physical slot</span><strong>{zoneId} / {slotId}</strong><small>{requested.status === "RESERVED" ? "Reserved for this pending request" : requested.status}</small></div><div className="slot-basemap-toggle" role="group" aria-label="Map background"><button type="button" aria-pressed={satellite} disabled={!MAPTILER_API_KEY || satelliteFailed} onClick={() => setBasemap("satellite")}>Satellite</button><button type="button" aria-pressed={!satellite} onClick={() => setBasemap("street")}>Street Map</button></div></div>
    <MapContainer center={[20,73.78]} zoom={18} maxZoom={22} scrollWheelZoom className="request-slot-map">
      {satellite ? <TileLayer tileSize={512} zoomOffset={-1} maxZoom={22} crossOrigin attribution={MAPTILER_ATTRIBUTION} url={`https://api.maptiler.com/maps/satellite-v4/{z}/{x}/{y}.jpg?key=${encodeURIComponent(MAPTILER_API_KEY)}`} eventHandlers={{tileerror:()=>{setSatelliteFailed(true);setBasemap("street");}}}/>
        : <TileLayer maxNativeZoom={19} maxZoom={22} attribution={OSM_ATTRIBUTION} url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>}
      <FitGeometry geometry={requested.geometry}/>
      {layout.boundaries?.features?.map(feature => <GeoJSON key={feature.properties?.boundary_id || JSON.stringify(feature.geometry)} data={feature} style={{color:"#687b8b",weight:2,fillOpacity:.03,dashArray:"6 5"}}/>)}
      {layout.slots.map(slot => slot.geometry && <GeoJSON key={slot.slot_id} data={slot.geometry} style={{color:slot.slot_id === slotId ? "#ffd43b" : "#fff",weight:slot.slot_id === slotId ? 5 : 2,fillColor:COLORS[slot.status] || "#788491",fillOpacity:satellite ? .4 : .68}}><Tooltip permanent direction="center" className={slot.slot_id === slotId ? "pilot-map-label pilot-label-focused" : "pilot-map-label"}>{slot.slot_id}</Tooltip></GeoJSON>)}
    </MapContainer>
    <p>The highlighted slot is the exact WGS84 position requested by the vendor. Approval rechecks that it is still reserved for this request.</p>
  </section>;
}
