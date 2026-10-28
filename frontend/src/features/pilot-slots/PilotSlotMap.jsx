import {zoneName, zoneMapLocation} from "../../shared/utils/displayLabels.js";
import {useI18n} from "../../i18n/react.jsx";
import {statusLabel} from "../../i18n/index.js";
import SlotInspector from "./SlotInspector.jsx";
import {googleWalkingLink} from "./slotPresentation.js";
import React, {useEffect, useReducer, useState, useRef} from "react";
import {CircleMarker, GeoJSON, MapContainer, Marker, Popup, Rectangle, TileLayer, Tooltip, useMap, useMapEvents} from "react-leaflet";
import L from "leaflet";
import {getPilotLayout, initializePilotLayout, updatePilotSlot, validatePilotGeometry, savePilotGeometry, getPilotDestination, createPilotSlot, deletePilotSlot, getPilotEligibleVendors} from "../../services/api.js";
import {initialPilotState, pilotReducer} from "./pilotState.js";
import {geographicCenter} from "../navigation/pilotNavigation.js";
import "./PilotSlotMap.css";
import "./SlotWorkspace.css";

const COLORS = {AVAILABLE: "#218657", OCCUPIED: "#c43e3e", RESERVED: "#e5b93b", BLOCKED: "#788491"};
const handleIcon = L.divIcon({className: "pilot-drag-handle", html: "↔", iconSize: [30, 30], iconAnchor: [15, 15]});
const ll = p => [p[1], p[0]];

function SlotDrawCapture({enabled, onBounds}) {
  const map = useMap();
  const [start,setStart] = useState(null), [end,setEnd] = useState(null);
  useMapEvents({
    mousedown(event) { if (!enabled) return; setStart(event.latlng); setEnd(event.latlng); map.dragging.disable(); },
    mousemove(event) { if (enabled && start) setEnd(event.latlng); },
    mouseup(event) { if (!enabled || !start) return; const finish=event.latlng; map.dragging.enable(); onBounds(L.latLngBounds(start,finish)); setStart(null); setEnd(null); },
  });
  useEffect(() => () => map.dragging.enable(), [map]);
  return start && end ? <Rectangle bounds={L.latLngBounds(start,end)} pathOptions={{color:"#0b5d45",dashArray:"6 4",fillOpacity:.18}}/> : null;
}

import MapLifecycle from "./MapLifecycle.jsx";

export default function PilotSlotMap({admin = false, visible = true, onBack, allocations = [], ownBusinessCategory, onViewVendor, onRequestSlot, focusSlotId = null, session, dispatch: externalDispatch, zoneId = "NN_F_013", zone, zones = [], onZoneChange}) {
  const {language,t} = useI18n();
  const [activeZone,setActiveZone] = useState(zoneId);
  const loadVersion = useRef(0);
  useEffect(() => {setActiveZone(zoneId);},[zoneId]);
  const zoneRecord = zones.find(item => item.zone_id === activeZone) || (zone?.zone_id === activeZone ? zone : null);
  const zoneCoordinates = zoneMapLocation(zoneRecord || activeZone).coordinates;
  const [local, localDispatch] = useReducer(pilotReducer, initialPilotState);
  const {layout, selectedId} = session || local, dispatch = externalDispatch || localDispatch;
  const zoneReference = zoneCoordinates
    ? [zoneCoordinates[1], zoneCoordinates[0]]
    : layout?.reference_point ? [layout.reference_point.latitude, layout.reference_point.longitude] : null;
  const [draft, setDraft] = useState(null), [boundaryId, setBoundaryId] = useState("2974");
  const [status, setStatus] = useState("AVAILABLE"), [vendorId, setVendorId] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [reviewed, setReviewed] = useState(false), [command, setCommand] = useState(null), [clickMode, setClickMode] = useState(null), [angle, setAngle] = useState(0);
  const [obstructionNote, setObstructionNote] = useState(""), [obstructionRadius, setObstructionRadius] = useState(.5);
  const [accessNote, setAccessNote] = useState(""), [accessObserved, setAccessObserved] = useState(false);
  const moveMap = kind => setCommand({kind, id: Date.now() + Math.random()});
  const [destination,setDestination] = useState(null);
  const [drawing,setDrawing] = useState(false), [placingSquare,setPlacingSquare] = useState(false), [drawnBounds,setDrawnBounds] = useState(null), [drawnDimensions,setDrawnDimensions] = useState(null);
  const [vendorSearch,setVendorSearch] = useState(""), [eligibleVendors,setEligibleVendors] = useState([]);
  const workspaceRef = useRef(null), [workspaceHeight,setWorkspaceHeight] = useState(640);
  useEffect(() => {
    if (!visible) return;
    const resize = () => {
      const mobile = window.innerWidth <= 760;
      setWorkspaceHeight(Math.max(mobile ? 520 : 640, mobile ? Math.round(window.innerHeight * .72) : window.innerHeight - 180));
    };
    const timer = setTimeout(resize,0); window.addEventListener("resize",resize);
    return () => {clearTimeout(timer);window.removeEventListener("resize",resize);};
  }, [visible,layout,draft]);
  const NAMES = Object.fromEntries((layout?.boundaries?.features || []).map(f => [f.properties.boundary_id,f.properties.name || f.properties.boundary_id]));
  useEffect(() => {
    if (!admin || !visible || !focusSlotId || layout?.zone_id !== activeZone) return;
    const slot = layout.slots.find(item => item.slot_id === focusSlotId);
    if (slot) {dispatch({type: "select", slotId: slot.slot_id}); setBoundaryId(slot.parent_boundary_id); setCommand({kind: "slot", id: Date.now()});}
  }, [admin, visible, activeZone, focusSlotId, layout?.zone_id]);
  const shown = draft || layout, selected = shown?.slots.find(s => s.slot_id === selectedId), assigned = layout?.slots.find(s => s.slot_id === layout.my_slot_id);
  const slots = shown?.georeferenced ? shown.slots : [], protectedSlot = selected?.assigned_vendor_id || selected?.status === "OCCUPIED";
  const remainingSlotCapacity = layout?.summary?.remaining_uncreated_capacity
    ?? (layout && zoneRecord?.listed_official_capacity != null ? zoneRecord.listed_official_capacity - layout.slots.length : null);
  const slotCapacityReached = remainingSlotCapacity != null && remainingSlotCapacity <= 0;
  const select = slot => {dispatch({type: "select", slotId: slot.slot_id}); if (slot.parent_boundary_id) setBoundaryId(slot.parent_boundary_id);};
  const run = async action => {setBusy(true); setError(""); try {return await action();} catch (e) {setError(e.message); return null;} finally {setBusy(false);}};
  const load = () => run(async () => {
    const version = ++loadVersion.current;
    const data = await (admin ? initializePilotLayout(activeZone) : getPilotLayout(activeZone));
    if(version !== loadVersion.current) return;
    dispatch({type:"loaded",layout:data});
    setBoundaryId(data.boundaries?.features[0]?.properties.boundary_id || "2974");
    if (!admin) { try {setDestination(await getPilotDestination(activeZone));} catch {setDestination(null);} }
  });
  useEffect(() => {dispatch({type:"zone"});setDraft(null);setDestination(null);setNotice("");load();}, [admin,activeZone]);
  useEffect(() => {
    if (!admin || !visible) return;
    const timer=setTimeout(() => getPilotEligibleVendors(activeZone,vendorSearch).then(data=>setEligibleVendors(data.vendors)).catch(error=>setError(error.message)),250);
    return () => clearTimeout(timer);
  },[admin,visible,activeZone,vendorSearch]);
  useEffect(() => {setStatus(selected?.status || "AVAILABLE"); setVendorId(selected?.assigned_vendor_id || ""); setAngle(selected?.pose?.angle || 0);}, [selected]);
  useEffect(() => {
    if (!slotCapacityReached) return;
    setDrawing(false);
    setPlacingSquare(false);
    setDrawnBounds(null);
    setDrawnDimensions(null);
  }, [slotCapacityReached]);
  const beginEdit = () => {const copy = structuredClone(layout); copy.expected_revision = layout.revision; copy.expected_versions = Object.fromEntries(layout.slots.map(s => [s.slot_id, s.updated_at])); setDraft(copy); setReviewed(false); setNotice("Draft edit: drag the selected slot's centre handle. Dimensions stay fixed in metres.");};
  const validateDraft = (next, poses = {}) => run(async () => {const valid = await validatePilotGeometry(next, poses, activeZone); setDraft(valid); setReviewed(false); return valid;});
  const saveDraft = () => run(async () => {const saved = await savePilotGeometry(draft, activeZone); dispatch({type: "loaded", layout: saved}); setDraft(null); setClickMode(null); setNotice("Layout saved.");});
  const saveStatus = (release = false) => run(async () => {const slot = await updatePilotSlot(selected.slot_id, {status: release ? "AVAILABLE" : status, assigned_vendor_id: release ? null : vendorId || null, expected_updated_at: selected.updated_at}, activeZone); dispatch({type: "updated", slot}); setNotice(`${slot.slot_id} assignment updated.`);});
  const createSlotFromBounds = (bounds, dimensions = {}, continuePlacingSquares = false) => run(async () => {
    const west=bounds.getWest(), east=bounds.getEast(), south=bounds.getSouth(), north=bounds.getNorth();
    const geometry={type:"Polygon",coordinates:[[[west,south],[east,south],[east,north],[west,north],[west,south]]]};
    const slot=await createPilotSlot({geometry,review_confirmed:true,...dimensions},activeZone);
    const data=await getPilotLayout(activeZone); dispatch({type:"loaded",layout:data}); dispatch({type:"select",slotId:slot.slot_id});
    const remainingCapacity = data.summary?.remaining_uncreated_capacity
      ?? (zoneRecord?.listed_official_capacity != null ? zoneRecord.listed_official_capacity - data.slots.length : null);
    const capacityReached = remainingCapacity != null && remainingCapacity <= 0;
    setDrawing(false);setPlacingSquare(continuePlacingSquares && !capacityReached);setDrawnBounds(null);setDrawnDimensions(null);moveMap("slot");
    setNotice(capacityReached ? `${slot.slot_id} created. Zone capacity reached.` : `${slot.slot_id} created.${continuePlacingSquares ? " Click the map to place another 2 m square." : ""}`);
  });
  const saveDrawnSlot = () => drawnBounds ? createSlotFromBounds(drawnBounds, drawnDimensions || {}) : null;
  const removeSelected = () => {
    if (!selected || !window.confirm(`Delete ${selected.slot_id}? This cannot be undone.`)) return;
    return run(async () => {
      const deletedSlotId = selected.slot_id;
      await deletePilotSlot(deletedSlotId,selected.updated_at,activeZone);
      dispatch({type:"deleted",slotId:deletedSlotId});
      setNotice(`${deletedSlotId} deleted.`);
      const data=await getPilotLayout(activeZone);
      dispatch({type:"loaded",layout:data});
    });
  };
  const mapClick = async p => {
    if (placingSquare && !busy) {
      const latitudeOffset = 1 / 111320;
      const longitudeOffset = latitudeOffset / Math.cos(p.lat * Math.PI / 180);
      const bounds = L.latLngBounds(
        [p.lat - latitudeOffset, p.lng - longitudeOffset],
        [p.lat + latitudeOffset, p.lng + longitudeOffset],
      );
      setCommand({kind:"placement", position:[p.lat,p.lng], id:Date.now()});
      setNotice("Creating 2 m square…");
      return createSlotFromBounds(bounds, {width_m:2,depth_m:2}, true);
    }
    if (!draft || !clickMode || busy) return;
    const next = clickMode === "access" ? {...draft, access_points: {...draft.access_points, [boundaryId]: {longitude: p.lng, latitude: p.lat, observed: accessObserved, note: accessNote}}}
      : {...draft, obstruction_request: {longitude: p.lng, latitude: p.lat, radius_m: Number(obstructionRadius), note: obstructionNote}};
    if (await validateDraft(next)) setClickMode(null);
  };
  const mapsLink = !admin ? googleWalkingLink(destination,assigned?.slot_id) : null;
  const eligible = eligibleVendors.length ? eligibleVendors : allocations.filter(a => a.zone_id === activeZone && a.status === "ACTIVE");
  const mapCenter = zoneReference || (layout?.reference_point ? [layout.reference_point.latitude,layout.reference_point.longitude] : [19.974,73.7725]);
  return <section className={`pilot-panel pilot-geographic ${admin ? "pilot-admin" : "pilot-vendor"}`} hidden={!visible} aria-label={`${zoneName(activeZone)} slot map`}>
    <header className="pilot-header"><div><h2>{zoneName(activeZone,t("display.zoneMissing"))}</h2><span><small>{activeZone}</small></span></div><button onClick={onBack}>{admin ? "Back to All Zones" : "Back to Dashboard"}</button></header>
    {admin && <label className="pilot-zone-selector"><span>Zone</span><select aria-label="Zone" value={activeZone} disabled={busy || Boolean(draft)} onChange={e => {setActiveZone(e.target.value);onZoneChange?.(e.target.value);}}>{zones.map(item => <option key={item.zone_id} value={item.zone_id}>{item.zone_id} · {zoneName(item)}</option>)}</select></label>}
    {error && <div className="pilot-error" role="alert">{error} <button disabled={busy || Boolean(draft)} onClick={load}>Reload saved layout</button></div>}{notice && <p role="status">{notice}</p>}{busy && !layout && <p role="status">Loading map…</p>}
    {layout && <>
      <div className="pilot-zone-counts"><span>Capacity <b>{layout.summary?.listed_capacity ?? "Not listed"}</b></span><span>Mapped <b>{layout.slots.length}</b></span><span>Active vendors <b>{layout.summary?.active_allocations ?? 0}</b></span>{layout.summary?.unmapped_active_allocations > 0 && <span>Unmapped <b>{layout.summary.unmapped_active_allocations}</b></span>}</div>
      {admin && zoneRecord?.zone_type === "NO_VENDING" && <p className="slot-map-note">No-vending zone: slot creation is disabled.</p>}
      {admin && layout.georeferenced && zoneRecord && zoneRecord.zone_type !== "NO_VENDING" && <div className="pilot-draw-toolbar"><button disabled={busy || slotCapacityReached} aria-pressed={placingSquare} onClick={() => {setDrawing(false);setPlacingSquare(value=>!value);setDrawnBounds(null);setDrawnDimensions(null);setNotice(placingSquare ? "" : "Click the map to place a 2 m square.");}}>{placingSquare ? "Place 2 m square (active)" : "Place 2 m square"}</button><button disabled={busy || slotCapacityReached} aria-pressed={drawing} onClick={() => {setDrawing(value=>!value);setPlacingSquare(false);setDrawnBounds(null);setDrawnDimensions(null);}}>{drawing ? "Cancel drawing" : "Draw custom rectangle"}</button>{placingSquare && <span>Click the map to place a square. Placement stays active for the next slot.</span>}{drawing && <span>Drag on the map to size the rectangle.</span>}{slotCapacityReached && <span>Zone capacity reached.</span>}{drawnBounds && <><span>Custom rectangle preview</span><button disabled={busy} onClick={saveDrawnSlot}>Save slot</button></>}</div>}
      {layout.operational_enabled === false && <div className="pilot-review-status"><span>Pending review · assignments disabled{layout.validation?.issues?.length > 0 ? ` · ${layout.validation.issues.join("; ")}` : ""}</span>{admin && <button disabled={busy || Boolean(draft)} onClick={beginEdit}>Review layout</button>}</div>}
      {!shown.georeferenced && <p className="pilot-assignment">{admin ? "Release assigned slots before changing the layout." : "Layout editing is unavailable."}</p>}
      {draft && <div className="pilot-draft-banner"><strong>EDITING LAYOUT · {draft.slots.length} slots · {draft.validation?.valid ? "Checks passed" : draft.validation?.reason || "Validation required"}</strong><label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)}/> I reviewed the layout.</label><button disabled={busy || !reviewed || !draft.validation?.valid} onClick={saveDraft}>Save layout</button><button disabled={busy} onClick={() => {setDraft(null); setClickMode(null); setError("");}}>Cancel</button></div>}
      <div ref={workspaceRef} style={{"--slot-workspace-height":`${workspaceHeight}px`}} className="pilot-workspace"><div className="pilot-visual"><div className="pilot-map-frame">
        <div className="slot-map-controls"><button onClick={() => moveMap("all")}>Recenter map</button><button disabled={!selected?.geometry} onClick={() => moveMap("slot")}>Zoom to selected slot</button>{!admin && assigned && <button onClick={() => {select(assigned); setCommand({kind:"own",id:Date.now()});}}>{t("display.viewSlot")}</button>}{mapsLink && <a href={mapsLink} target="_blank" rel="noopener noreferrer">Google Maps - my access point</a>}</div>
        <div className="slot-map-legend">{Object.entries(COLORS).map(([name,color]) => <span key={name}><i style={{background:color}}/>{statusLabel(language,name)}</span>)}<span><i className="slot-selected-key"/>Selected</span>{!admin && <span><i className="slot-own-key"/>My slot</span>}</div>
        <MapContainer key={activeZone} center={mapCenter} zoom={17} maxZoom={22} className={`pilot-context-map ${drawing || placingSquare ? "slot-drawing-active" : ""}`} scrollWheelZoom>
          <TileLayer maxNativeZoom={19} maxZoom={22} attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
          <MapLifecycle visible={visible} boundaries={shown.boundaries} slots={slots} command={command} selected={selected} assigned={assigned} boundaryId={boundaryId} zoneReference={zoneReference} onPan={() => {}} onClick={mapClick}/>
          {admin && zoneRecord?.zone_type !== "NO_VENDING" && <SlotDrawCapture enabled={drawing} onBounds={bounds=>{setDrawnBounds(bounds);setDrawnDimensions(null);setDrawing(false);}}/>}
          {drawnBounds && <Rectangle bounds={drawnBounds} pathOptions={{color:"#0b5d45",dashArray:"6 4",fillOpacity:.18}}/>}
          {zoneReference && <CircleMarker center={zoneReference} radius={10} pathOptions={{color:"#ffffff",weight:3,fillColor:"#e14b37",fillOpacity:1}}><Tooltip permanent direction="top" offset={[0,-8]}>Zone · {zoneRecord?.zone_id || activeZone}</Tooltip><Popup>{zoneName(zoneRecord || activeZone)}</Popup></CircleMarker>}
          {shown.boundaries?.features.map(f => <GeoJSON key={`boundary-${f.properties.boundary_id}`} data={f} style={{color: "#687b8b", weight: 2, fillOpacity: .04, dashArray: "6 5"}} eventHandlers={{click: () => setBoundaryId(f.properties.boundary_id)}}><Tooltip>{f.properties.name}</Tooltip></GeoJSON>)}
          {shown.corridors?.map(c => <GeoJSON key={`corridor-${JSON.stringify(c.geometry)}`} data={c.geometry} style={{color: "#347d95", weight: 1, fillColor: "#73c4db", fillOpacity: .2}}><Tooltip>Pedestrian corridor</Tooltip></GeoJSON>)}
          {slots.map(slot => <GeoJSON key={`${slot.slot_id}-${JSON.stringify(slot.geometry)}-${slot.status}`} data={slot.geometry} style={{color: selectedId === slot.slot_id ? "#142e50" : slot.slot_id === layout.my_slot_id ? "#086c72" : "#fff", dashArray: slot.slot_id === layout.my_slot_id ? "5 2" : undefined, weight: selectedId === slot.slot_id || slot.slot_id === layout.my_slot_id ? 4 : 1.5, fillColor: COLORS[slot.status], fillOpacity: .8, className: `pilot-slot-polygon pilot-slot-${slot.slot_id} ${slot.slot_id === layout.my_slot_id ? "pilot-assigned-polygon" : ""}`}} eventHandlers={{click: e => {L.DomEvent.stopPropagation(e); select(slot);}}}><Tooltip permanent direction="center" className={`pilot-map-label ${slot.slot_id === layout.my_slot_id ? "pilot-label-assigned" : selectedId === slot.slot_id ? "pilot-label-focused" : ""}`}>{slot.slot_id}</Tooltip></GeoJSON>)}
          {shown.obstructions?.map((o, i) => <GeoJSON key={`obstruction-${i}-${JSON.stringify(o.geometry)}`} data={o.geometry} style={{color: "#a52828", weight: 2, fillOpacity: .5}}><Tooltip>Obstruction: {o.note || "No note"}</Tooltip></GeoJSON>)}
          {Object.entries(shown.access_points || {}).map(([id, p]) => <CircleMarker key={`access-${id}-${p.longitude}`} center={[p.latitude, p.longitude]} radius={6} pathOptions={{color: "#783fab", fillOpacity: .8}}><Popup>{NAMES[id]} approach<br/>{p.note}</Popup></CircleMarker>)}
          {draft && selected?.geometry && !protectedSlot && <Marker icon={handleIcon} draggable position={ll(geographicCenter(selected.geometry))} eventHandlers={{dragend: e => {const p = e.target.getLatLng(); e.target.setLatLng(ll(geographicCenter(selected.geometry))); validateDraft(structuredClone(draft), {[selected.slot_id]: {longitude: p.lng, latitude: p.lat, angle: selected.pose.angle}});}}}/>}
        </MapContainer>
      </div></div>
      <SlotInspector zoneId={activeZone} operationalEnabled={layout.operational_enabled !== false} selected={selected} selectedId={selectedId} slots={shown.slots} onSelect={select} admin={admin} assigned={assigned} allocations={allocations} ownBusinessCategory={ownBusinessCategory} onViewVendor={onViewVendor}>
        {selected && admin && !draft && <form onSubmit={e => {e.preventDefault(); saveStatus();}}><label>Assignment status<select value={status} onChange={e => {setStatus(e.target.value); if (["AVAILABLE", "BLOCKED"].includes(e.target.value)) setVendorId("");}}>{Object.keys(COLORS).map(s => <option key={s} value={s}>{statusLabel(language,s)}</option>)}</select></label><label>Approved vendor<select value={vendorId} disabled={!["RESERVED", "OCCUPIED"].includes(status)} onChange={e => setVendorId(e.target.value)}><option value="">No linked vendor</option>{selected.assigned_vendor_id && !eligible.some(a => a.vendor_id === selected.assigned_vendor_id) && <option value={selected.assigned_vendor_id}>{t("identity.registeredVendor")} - eligibility changed</option>}{eligible.map(a => <option key={a.allocation_id} value={a.vendor_id}>{a.vendor_name || t("identity.registeredVendor")}</option>)}</select></label><small>Assignments require an available slot and an approved allocation to this zone.</small><button disabled={busy || (layout.operational_enabled === false && (Boolean(vendorId) || ["OCCUPIED","RESERVED"].includes(status)))}>Save slot assignment</button>{selected.assigned_vendor_id && <button type="button" disabled={busy} onClick={() => saveStatus(true)}>Release slot assignment</button>}</form>}
        {selected?.geometry && admin && zoneRecord?.zone_type !== "NO_VENDING" && !draft && <button className="slot-delete-button" type="button" disabled={busy || selected.status !== "AVAILABLE" || selected.assigned_vendor_id || selected.pending_request_id || selected.active_allocation_id} onClick={removeSelected}>Delete slot</button>}
        {!admin && selected?.status === "AVAILABLE" && onRequestSlot && <button className="pilot-request-slot" disabled={busy || (layout.summary?.requestable_slots ?? 0) < 1} onClick={() => onRequestSlot(selected)}>Request {selected.slot_id}</button>}
        {admin && draft && <div className="pilot-edit-controls">{protectedSlot ? <p>Assigned/occupied position is locked. Explicitly release its demo assignment/status before editing geometry.</p> : <><label>Rotation degrees<input type="number" value={angle} onChange={e => setAngle(Number(e.target.value))}/></label><button disabled={busy} onClick={() => validateDraft(structuredClone(draft), {[selected.slot_id]: {...selected.pose, angle}})}>Apply Rotation</button><button disabled={busy} onClick={() => validateDraft({...draft, slots: draft.slots.filter(s => s.slot_id !== selected.slot_id)})}>Delete proposed slot from draft</button></>}</div>}
        {admin && draft && <div className="pilot-edit-controls"><h4>Observed site information</h4><label>Obstruction note<input maxLength={300} value={obstructionNote} onChange={e => setObstructionNote(e.target.value)}/></label><label>Obstruction radius (m)<input type="number" min=".1" max="10" step=".1" value={obstructionRadius} onChange={e => setObstructionRadius(e.target.value)}/></label><button onClick={() => setClickMode("obstruction")}>Record obstruction on map</button><label>Pedestrian approach note<input maxLength={300} value={accessNote} onChange={e => setAccessNote(e.target.value)}/></label><label><input type="checkbox" checked={accessObserved} onChange={e => setAccessObserved(e.target.checked)}/> Approach observed on site (not municipal verification)</label><button onClick={() => setClickMode("access")}>Set boundary access point on map</button>{clickMode && <p role="status">Click the map to place the {clickMode === "access" ? "approach point" : "obstruction"}. Invalid placements are rejected.</p>}{draft.obstructions?.length > 0 && <button onClick={() => validateDraft({...draft, obstructions: draft.obstructions.slice(0, -1)})}>Remove last obstruction from draft</button>}</div>}
      {!admin && <div className="slot-own-access"><span>{assigned ? `${t("display.ownSlot")}: ${assigned.slot_id}` : t("display.noSlot")}</span>{mapsLink ? <a href={mapsLink} target="_blank" rel="noopener noreferrer">Open in Google Maps - recorded access point</a> : <small>No observed pedestrian access point configured; external directions unavailable.</small>}</div>}
      </SlotInspector>
      </div>

    </>}
  </section>;
}
