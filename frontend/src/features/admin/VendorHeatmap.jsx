import React, {useEffect, useMemo, useState} from "react";
import L from "leaflet";
import {Circle, CircleMarker, MapContainer, Popup, Tooltip, useMap, useMapEvents} from "react-leaflet";
import {getAdminVendorHeatmap} from "../../services/api.js";
import {Basemap, HeatLayer, hasSatelliteTiles} from "../../shared/maps/HeatmapLayers.jsx";
import {pretty} from "./viewModel.js";
import {zoneName} from "../../shared/utils/displayLabels.js";
import {competitionWithinRadius, distanceMetres, groupVendorMarkers, vendorsWithinRadius} from "./vendorHeatmap.js";
import "./VendorHeatmap.css";

const NASHIK_CENTER = [19.9975, 73.7898];
const number = value => Number(value || 0).toLocaleString("en-IN");

function MapInteraction({points, onSelect}) {
  const map = useMap();
  useMapEvents({click: event => onSelect?.({latitude: event.latlng.lat, longitude: event.latlng.lng})});
  useEffect(() => {
    if (!points.length) return;
    map.fitBounds(L.latLngBounds(points.map(point => [point.latitude, point.longitude])), {padding: [35, 35], maxZoom: 16});
  }, [map, points]);
  return null;
}

export default function VendorHeatmap({refreshToken = 0}) {
  const [data, setData] = useState(null);
  const [analysis, setAnalysis] = useState("density");
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");
  const [view, setView] = useState("heatmap");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [radius, setRadius] = useState(250);
  const [satelliteFailed, setSatelliteFailed] = useState(false);
  const [basemap, setBasemap] = useState(hasSatelliteTiles ? "satellite" : "street");
  const [liveRevision, setLiveRevision] = useState(0);
  const [updatedAt, setUpdatedAt] = useState(null);

  useEffect(() => {
    const refresh = () => setLiveRevision(value => value + 1);
    const visible = () => {if (document.visibilityState === "visible") refresh();};
    const timer = window.setInterval(refresh, 15000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    return () => {window.clearInterval(timer); window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", visible);};
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    getAdminVendorHeatmap({business_category: category, location_key: location}, controller.signal)
      .then(result => {setData(result); setUpdatedAt(new Date());})
      .catch(failure => {if (!controller.signal.aborted) setError(failure.message);})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [category, location, refreshToken, liveRevision]);

  const points = analysis === "competition" && !category ? [] : data?.points || [];
  const competitionPoints = data?.competition_points || [];
  const markerGroups = useMemo(() => groupVendorMarkers(points), [points]);
  const competition = useMemo(
    () => competitionWithinRadius(competitionPoints, selectedLocation, category, radius),
    [competitionPoints, selectedLocation, category, radius],
  );
  const nearbyVendors = useMemo(
    () => vendorsWithinRadius(points, selectedLocation, radius),
    [points, selectedLocation, radius],
  );
  const nearestAreaVendor = useMemo(
    () => nearbyVendors.reduce((nearest, vendor) => (
      !nearest || distanceMetres(selectedLocation, vendor) < distanceMetres(selectedLocation, nearest)
        ? vendor
        : nearest
    ), null),
    [nearbyVendors, selectedLocation],
  );
  const nearestAreaName = nearestAreaVendor
    ? nearestAreaVendor.location_type === "zone"
      ? zoneName(nearestAreaVendor.zone_id, nearestAreaVendor.location_label)
      : nearestAreaVendor.location_label || "Area name not recorded"
    : "No vendor nearby";
  const selectedVendorCount = analysis === "competition" ? competition.length : nearbyVendors.length;
  const satelliteAvailable = hasSatelliteTiles && !satelliteFailed;
  const satelliteActive = basemap === "satellite" && satelliteAvailable;
  const locations = data?.filters?.locations || [];
  const zones = locations.filter(item => item.type === "zone");
  const localities = locations.filter(item => item.type === "locality");
  const unrecorded = locations.filter(item => item.type === "unrecorded");
  const mapping = data?.mapping_summary || {};

  const selectAnalysis = next => {
    setAnalysis(next);
    setView(next === "density" ? "heatmap" : "markers");
    setSelectedLocation(null);
  };
  const failSatellite = () => {if (!satelliteFailed) {setSatelliteFailed(true); setBasemap("street");}};

  return <section className="vendor-heatmap-page">
    <div className="admin-section-heading"><div><span className="admin-eyebrow">LIVE OPERATIONAL LOCATION EVIDENCE</span><h2>Vendor Mapping &amp; Competition</h2><p>Assigned geographic slots and vendor-provided working pins update this view. No missing location is invented.</p></div>{data && <span className="admin-count">{number(mapping.mapped_records)} of {number(mapping.total_records)} mapped</span>}</div>

    <div className="vendor-analysis-switch" role="tablist" aria-label="Vendor analysis type">
      <button role="tab" aria-selected={analysis === "density"} onClick={() => selectAnalysis("density")}><strong>Vendor Density</strong><span>Mapping coverage, heat intensity and individual vendors</span></button>
      <button role="tab" aria-selected={analysis === "competition"} onClick={() => selectAnalysis("competition")}><strong>Business Competition</strong><span>Same-category vendors around a selected point</span></button>
    </div>

    <div className="vendor-heatmap-filters">
      <label><span>{analysis === "competition" ? "Business type (required)" : "Business type"}</span><select value={category} onChange={event => {setCategory(event.target.value); setSelectedLocation(null);}}><option value="">{analysis === "competition" ? "Select a business category" : "All vendor categories"}</option>{data?.filters.categories.map(item => <option key={item.value} value={item.value}>{pretty(item.value)} ({number(item.located_count)} mapped / {number(item.total_count)} total)</option>)}</select></label>
      <label><span>Municipal zone / locality</span><select value={location} onChange={event => {setLocation(event.target.value); setSelectedLocation(null);}}><option value="">All recorded locations</option>{zones.length > 0 && <optgroup label="Municipal zones">{zones.map(item => <option key={item.value} value={item.value}>{item.label} ({number(item.mapped_count)} mapped / {number(item.total_count)} total)</option>)}</optgroup>}{localities.length > 0 && <optgroup label="Profile localities">{localities.map(item => <option key={item.value} value={item.value}>{item.label} ({number(item.mapped_count)} mapped / {number(item.total_count)} total)</option>)}</optgroup>}{unrecorded.map(item => <option key={item.value} value={item.value}>{item.label} ({number(item.mapped_count)} mapped / {number(item.total_count)} total)</option>)}</select></label>
      {analysis === "density" && <label><span>Nearby count radius</span><select value={radius} onChange={event => setRadius(Number(event.target.value))}>{[100,250,500].map(value => <option key={value} value={value}>{value} m</option>)}</select></label>}
      <div className="vendor-heatmap-view-toggle" role="group" aria-label="Vendor map display"><button aria-pressed={view === "heatmap"} onClick={() => setView("heatmap")}>{analysis === "density" ? "Heatmap" : "Business Heat"}</button><button aria-pressed={view === "markers"} onClick={() => setView("markers")}>{analysis === "density" ? "Vendor Markers" : "Business Markers"}</button></div>
      {updatedAt && <small className="vendor-live-update">Auto-updates every 15 seconds · Updated {updatedAt.toLocaleTimeString()}</small>}
    </div>

    {error && <div className="pilot-error" role="alert">{error}</div>}
    {loading && !data && <p role="status">Loading vendor mapping data…</p>}
    {data && <>
      {analysis === "density" ? <div className="vendor-heatmap-summary">
        <article><span>Tracked vendor records</span><strong>{number(mapping.total_records)}</strong></article>
        <article><span>Mapped vendors</span><strong>{number(mapping.mapped_records)}</strong></article>
        <article><span>Unmapped vendors</span><strong>{number(mapping.unmapped_records)}</strong></article>
        <article><span>Mapping coverage</span><strong>{number(mapping.mapping_coverage_percent)}%</strong></article>
      </div> : <div className="vendor-heatmap-summary">
        <article><span>Selected business</span><strong className="summary-text">{category ? pretty(category) : "Select one"}</strong></article>
        <article><span>Mapped competitors</span><strong>{category ? number(points.length) : "—"}</strong></article>
        <article><span>Analysis radius</span><strong>{radius} m</strong></article>
        <article><span>Selected point</span><strong className="summary-text">{selectedLocation ? "Ready" : "Click map"}</strong></article>
      </div>}

      <div className={`vendor-heatmap-layout ${analysis === "density" ? "density-only" : ""}`}>
        <div className="vendor-heatmap-map-wrap">
          <div className="vendor-heatmap-basemap" role="group" aria-label="Map background"><button aria-pressed={satelliteActive} disabled={!satelliteAvailable} title={!hasSatelliteTiles ? "MapTiler API key is not configured" : satelliteFailed ? "Satellite imagery could not be loaded" : "Show satellite imagery"} onClick={() => setBasemap("satellite")}>Satellite</button><button aria-pressed={!satelliteActive} onClick={() => setBasemap("street")}>Street Map</button></div>
          <MapContainer center={NASHIK_CENTER} zoom={12} maxZoom={22} preferCanvas className="vendor-heatmap-map">
            <Basemap satellite={satelliteActive} onFailure={failSatellite}/>
            <MapInteraction points={points} onSelect={analysis === "density" || category ? setSelectedLocation : undefined}/>
            {view === "heatmap" && <HeatLayer points={points}/>} 
            {view === "markers" && markerGroups.map(group => <CircleMarker key={group.key} center={[group.latitude, group.longitude]} radius={group.vendors.length > 1 ? 8 : 5} pathOptions={{color:"#fff",weight:2,fillColor:"#174b77",fillOpacity:.86}}><Tooltip>{group.vendors.length === 1 ? pretty(group.vendors[0].business_category) : `${group.vendors.length} vendor records at this coordinate`}</Tooltip><Popup><strong>{group.vendors.length === 1 ? "Vendor record" : `${group.vendors.length} vendor records`}</strong><ul>{Object.entries(group.categories).map(([name,count]) => <li key={name}>{pretty(name)}: {number(count)}</li>)}</ul>{group.vendors.slice(0,10).map(vendor => <small key={vendor.vendor_id}>{vendor.vendor_id} · {vendor.location_label}<br/></small>)}</Popup></CircleMarker>)}
            {selectedLocation && <><Circle center={[selectedLocation.latitude, selectedLocation.longitude]} radius={radius} pathOptions={{color:analysis === "competition" ? "#7c3aed" : "#0b6c64",weight:2,fillColor:analysis === "competition" ? "#8b5cf6" : "#16a394",fillOpacity:.08}}/><CircleMarker center={[selectedLocation.latitude, selectedLocation.longitude]} radius={6} pathOptions={{color:"#fff",weight:2,fillColor:analysis === "competition" ? "#7c3aed" : "#0b6c64",fillOpacity:1}}><Tooltip permanent direction="top" offset={[0,-8]} className="vendor-heatmap-selected-tooltip"><strong>{number(selectedVendorCount)} vendor{selectedVendorCount === 1 ? "" : "s"}</strong><br/><span>within {radius} m · matching filters</span>{analysis === "density" && <span>Area: {nearestAreaName}</span>}</Tooltip></CircleMarker></>}
          </MapContainer>
          {view === "heatmap" && points.length > 0 && <div className="vendor-heatmap-legend" aria-label="Heatmap density legend"><span><i className="low"/>Low recorded density</span><span><i className="moderate"/>Moderate</span><span><i className="high"/>High</span></div>}
          {!points.length && <div className="vendor-heatmap-empty">{analysis === "competition" && !category ? "Select a business category to begin competition analysis." : "No mapped vendor coordinates match these filters."}</div>}
        </div>

        {analysis === "competition" && <aside className="vendor-competition-panel">
          <span className="admin-eyebrow">BUSINESS COMPETITION</span><h3>Nearby same-category vendors</h3><p>Select a business type, click any map location, and choose a radius.</p>
          <label><span>Radius</span><select value={radius} onChange={event => setRadius(Number(event.target.value))}>{[100,250,500].map(value => <option key={value} value={value}>{value} m</option>)}</select></label>
          {!category && <div className="competition-result muted">Select a business type first.</div>}
          {category && !selectedLocation && <div className="competition-result muted">Click the map to select an analysis location.</div>}
          {category && selectedLocation && <div className="competition-result"><strong>{number(competition.length)}</strong><span>{pretty(category)} vendor record{competition.length === 1 ? "" : "s"} within {radius} m</span></div>}
          {selectedLocation && <small>Selected point: {selectedLocation.latitude.toFixed(5)}, {selectedLocation.longitude.toFixed(5)}</small>}
          <p className="competition-caution">Only vendors with real assigned-slot or profile coordinates are counted. This does not measure sales, demand or every vendor operating nearby.</p>
        </aside>}
      </div>

      {analysis === "density" && <div className="vendor-heatmap-evidence">
        <section><h3>Mapping status by vendor</h3><div className="vendor-mapping-records">{data.mapping_records.length ? data.mapping_records.slice(0,100).map(record => <article key={record.vendor_id}><div><strong>{record.vendor_id}</strong><span>{pretty(record.business_category)}</span></div><b className={record.mapping_status}>{record.mapping_status === "mapped" ? `Mapped · ${record.coordinate_source === "assigned_slot" ? "assigned slot" : "profile pin"}` : `Unmapped · ${record.mapping_issue === "invalid_coordinates" ? "invalid coordinates" : "coordinates missing"}`}</b></article>) : <p>No operational vendors match these filters.</p>}{data.mapping_records.length > 100 && <small>Showing the first 100 of {number(data.mapping_records.length)} matching records.</small>}</div></section>
        <section><h3>Category mapping coverage</h3><ul>{data.filters.categories.map(item => <li key={item.value}><span>{pretty(item.value)}</span><strong>{number(item.located_count)} mapped / {number(item.unmapped_count)} unmapped</strong></li>)}</ul><h3 className="location-coverage-heading">Locations with operational vendors</h3><div className="vendor-location-stats">{locations.filter(item => item.total_count > 0).map(item => <article key={item.value}><strong>{item.label}</strong><span>{number(item.mapped_count)} mapped</span><span>{number(item.unmapped_count)} unmapped</span></article>)}</div></section>
      </div>}
      <details className="service-disclosure"><summary>Data quality and interpretation</summary><p>{data.location_semantics}</p><p>{data.density_notice}</p><ul><li>{number(data.data_quality.active_operational_records)} active operational profiles were inspected.</li><li>{number(data.data_quality.assigned_slot_records)} active vendors have assigned WGS84 slots, including {number(data.data_quality.assigned_slot_only_records)} imported vendors without an operational profile.</li><li>{number(data.data_quality.profile_coordinate_records)} use a saved vendor-profile coordinate.</li><li>{number(data.data_quality.assigned_slot_coordinate_records)} use an assigned WGS84 slot coordinate.</li><li>{number(data.data_quality.missing_coordinate_records)} have no coordinate source.</li><li>{number(data.data_quality.invalid_coordinate_records)} have invalid coordinates and are excluded from maps.</li></ul></details>
    </>}
  </section>;
}
