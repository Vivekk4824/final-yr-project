import {zoneName, officialZoneDivision, zoneMapLocation, zoneDisplayGeometry, illustrativeDivisions} from "../../shared/utils/displayLabels.js";
import React, {useEffect, useMemo, useState} from "react";
import {CircleMarker, Polygon, LayersControl, LayerGroup, MapContainer, Popup, TileLayer, Tooltip, useMap} from "react-leaflet";
import L from "leaflet";
export const divisionFeatures = illustrativeDivisions.features;

// Inclusive boundary check for display browsing only; never administrative membership.
function inRing([x, y], ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[j], [bx, by] = ring[i];
    const cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax);
    if (Math.abs(cross) < 1e-12 && x >= Math.min(ax, bx) && x <= Math.max(ax, bx) && y >= Math.min(ay, by) && y <= Math.max(ay, by)) return true;
    if ((ay > y) !== (by > y) && x < (bx - ax) * (y - ay) / (by - ay) + ax) inside = !inside;
  }
  return inside;
}
export function insideDivision(coordinates, division) {
  const shape = divisionFeatures.find(feature => feature.properties.division === division)?.geometry;
  if (!coordinates || !shape) return false;
  const polygons = shape.type === "MultiPolygon" ? shape.coordinates : [shape.coordinates];
  return polygons.some(rings => inRing(coordinates, rings[0]) && !rings.slice(1).some(ring => inRing(coordinates, ring)));
}
export function analyticalDisplayGeometry(zones, geometry) {
  const csv = zoneDisplayGeometry(zones, true);
  const ids = new Set(csv.features.map(feature => feature.properties.zone_id));
  return {type: "FeatureCollection", features: [...csv.features, ...(geometry?.features || []).filter(feature => !ids.has(feature.properties?.zone_id))]};
}
export function spatialDivisionZones(zones, division, geometry, includeReferences = false) {
  const references = new Map(analyticalDisplayGeometry(zones, geometry).features.filter(feature => feature.geometry?.type === "Point").map(feature => [feature.properties.zone_id, feature.geometry.coordinates]));
  return zones.filter(zone => {
    const preferred = zoneMapLocation(zone).coordinates;
    return insideDivision(preferred, division) || (includeReferences && !preferred && insideDivision(references.get(zone.zone_id), division));
  });
}

function DivisionFocus({division, resetVersion, groups}) {
  const map = useMap();
  useEffect(() => {
    const features = division ? divisionFeatures.filter(feature => feature.properties.division === division) : divisionFeatures;
    const bounds = division && groups.length ? L.latLngBounds(groups.map(group => group.position)) : L.geoJSON({type: "FeatureCollection", features}).getBounds();
    map.invalidateSize({pan: false});
    if (bounds.isValid()) map.flyToBounds(bounds, {padding: [28, 28], maxZoom: 14, duration: .65});
  }, [map, division, resetVersion, groups]);
  return null;
}

import {buildAdminMapModel, uniqueMapPositions} from "../../shared/utils/mapGrouping.js";

import {PILOT_ZONE_IDS} from "../pilot-slots/pilotState.js";
import {STATUS_COLORS, pretty} from "./viewModel.js";

export function AdminMapFocus({groups, resetVersion}) {
  const map = useMap();
  useEffect(() => {
    const positions = uniqueMapPositions(groups);
    if (!positions.length) return;
    map.invalidateSize({pan: false});
    if (positions.length === 1) map.setView(positions[0], 14, {animate: false});
    else {
      const bounds = L.latLngBounds(positions);
      if (bounds.isValid()) map.fitBounds(bounds, {padding: [32, 32], maxZoom: 14, animate: false});
    }
    const timer = setTimeout(() => map.invalidateSize({pan: false}), 0);
    return () => clearTimeout(timer);
  }, [map, groups, resetVersion]);
  return null;
}

export function AdminZoneMap({zones, geometry, onZone, division = "", onDivision, selectedZoneId, referenceEnabled, onReferenceChange}) {
  const [resetVersion, setResetVersion] = useState(0);
  const displayGeometry = useMemo(() => ({type: "FeatureCollection", features: zoneDisplayGeometry(zones).features.filter(feature => feature.geometry?.type === "Point" && insideDivision(feature.geometry.coordinates, division))}), [zones, division]);
  const model = useMemo(() => buildAdminMapModel(zones, displayGeometry), [zones, displayGeometry]);
  const referenceModel = useMemo(() => {
    const reference = analyticalDisplayGeometry(zones, geometry);
    reference.features = reference.features.filter(feature => !zoneMapLocation(zones.find(zone => zone.zone_id === feature.properties.zone_id) || feature.properties.zone_id).coordinates && insideDivision(feature.geometry?.type === "Point" ? feature.geometry.coordinates : null, division));
    return buildAdminMapModel(zones, reference);
  }, [zones, geometry, division]);
  const focusGroups = useMemo(() => referenceEnabled ? [...model.groups, ...referenceModel.groups] : model.groups, [model.groups, referenceModel.groups, referenceEnabled]);
  return <div className="admin-map-shell">
    <button className="admin-map-reset" onClick={() => setResetVersion(value => value + 1)}>{division ? "Recenter division" : "View city"}</button>
    <MapContainer center={[19.9975, 73.7898]} zoom={12} scrollWheelZoom className="admin-map-canvas">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
      <DivisionFocus division={division} resetVersion={resetVersion} groups={focusGroups}/>
      {divisionFeatures.filter(feature => !division || feature.properties.division === division).map(feature => <Polygon key={feature.properties.division_id} positions={feature.geometry.coordinates.map(ring => ring.map(([lng, lat]) => [lat, lng]))} pathOptions={{color: feature.properties.display_color, weight: 2, fillOpacity: division ? .08 : .3}} eventHandlers={{click: () => onDivision?.(feature.properties.division)}}><Tooltip sticky>{feature.properties.name} - Illustrative boundary</Tooltip></Polygon>)}
      {division && model.groups.map(group => {const primary = group.zones[0]; const location = zoneMapLocation(primary); const selected = group.zones.some(zone => zone.zone_id === selectedZoneId); const pilot = group.zones.some(zone => PILOT_ZONE_IDS.includes(zone.zone_id)); return <CircleMarker key={group.key} center={group.position} radius={selected ? 13 : pilot ? 10 : group.shared ? 7 : 5}
        eventHandlers={{click: () => {if (!group.shared) onZone(primary);}}}
        pathOptions={{color: selected ? "#0f172a" : pilot ? "#075985" : group.shared ? "#3f586c" : "#fff", weight: selected ? 4 : pilot ? 3 : group.shared ? 2 : 1.5, dashArray: location.kind === "approximate" ? "3 3" : undefined, fillOpacity: location.kind === "approximate" ? .35 : .85, fillColor: location.kind === "pilot" ? "#075985" : location.kind === "manual" ? "#087f72" : location.kind === "landmark" ? "#b45309" : "#718596"}}>
        <Tooltip direction="top">{group.shared ? `${group.zones.length} zones share this display location` : `${zoneName(primary)} - ${location.label}`}</Tooltip>
        <Popup className="admin-zone-map-popup" minWidth={280} maxWidth={360}>
          <strong>{group.shared ? `${group.zones.length} zones at this map location` : "Zone"}</strong>
          <div className="admin-shared-list">{group.zones.map(zone => <button key={zone.zone_id} onClick={() => onZone(zone)}>
            <span className="admin-popup-zone-title"><b>{zone.zone_id}</b><em><i style={{background: STATUS_COLORS[zone.live_status] || "#64748b"}}/>{pretty(zone.live_status)}</em></span>
            <span className="admin-popup-zone-name">{zoneName(zone)}</span>
            <small>{pretty(zone.zone_type)} · {zone.operational_available == null ? "Availability not recorded" : `${zone.operational_available} available`}</small>
            {officialZoneDivision(zone) !== division && <small>Officially listed in {officialZoneDivision(zone)}</small>}
            <span className="admin-popup-action">View zone</span>
          </button>)}</div>
        </Popup>
      </CircleMarker>;})}
      {division && <LayersControl position="topright"><LayersControl.Overlay name="Unverified reference locations" checked={referenceEnabled}><LayerGroup eventHandlers={{add: () => onReferenceChange?.(true), remove: () => onReferenceChange?.(false)}}>{referenceModel.groups.map(group => <CircleMarker key={`reference-${group.key}`} center={group.position} radius={6} pathOptions={{color: "#64748b", fillOpacity: .12, dashArray: "2 4"}}><Tooltip>Unverified analytical reference - not an exact vending site</Tooltip><Popup><strong>Unverified reference locations</strong><p>Analytical points only. These do not establish actual vending locations.</p>{group.zones.map(zone => <button key={zone.zone_id} onClick={() => onZone(zone)}>{zoneName(zone)} - Official division: {officialZoneDivision(zone)} - Listed capacity: {zone.listed_official_capacity ?? "Not recorded"} - Operationally available: {zone.operational_available ?? "unknown"} - {pretty(zone.live_status)}{officialZoneDivision(zone) !== division ? ` (inside ${division} illustrative polygon)` : ""}</button>)}</Popup></CircleMarker>)}</LayerGroup></LayersControl.Overlay></LayersControl>}
    </MapContainer>
    {division && <div className="admin-map-legend">{Object.keys(STATUS_COLORS).map(status => <span key={status}><i style={{background: STATUS_COLORS[status]}}/>{pretty(status)}</span>)}<span><i style={{background: "#b45309"}}/>Landmark candidate</span><span><i style={{background: "#087f72"}}/>Manual reference (unverified)</span><span><i style={{background: "#718596"}}/>Approximate reference</span><span><i style={{background: "#075985"}}/>Provisional pilot</span></div>}
    <div className="admin-map-disclaimer">Map pins are approximate references, not confirmed vending spots. Zone records determine official division and status.{division && model.unavailableZoneIds.length > 0 && ` ${model.unavailableZoneIds.length} zones have no map pin.`}</div>
  </div>;
}
