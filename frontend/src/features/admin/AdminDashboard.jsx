import VendorDetails from "./VendorDetails.jsx";
import ZoneDetailsModal from "./ZoneDetailsModal.jsx";
import {zoneName, officialZoneDivision} from "../../shared/utils/displayLabels.js";
import {AdminHome, PendingRequests, RequestReviewModal, ZoneManagement, ZoneExplorer} from "./AdminTabPanels.jsx";
import React, {useEffect, useMemo, useReducer, useRef, useState} from "react";

import "leaflet/dist/leaflet.css";
import {Activity, AlertTriangle, Building2, Check, ClipboardList, RefreshCw, ShieldCheck, Users, XCircle} from "lucide-react";
import {approveAllocationRequest, getAdminOverview, getAllocationRequests, getAllocations, getZoneCatalog, getZoneGeometry, rejectAllocationRequest, updateZoneLiveStatus} from "../../services/api.js";

import ToastRegion from "../../shared/ui/ToastRegion.jsx";
const PilotSlotMap = React.lazy(() => import("../pilot-slots/PilotSlotMap.jsx"));
const VendorHeatmap = React.lazy(() => import("./VendorHeatmap.jsx"));
import {initialPilotState, pilotReducer} from "../pilot-slots/pilotState.js";
import {useDialogFocus} from "../../shared/utils/dialogFocus.js";
import "./AdminDashboard.css";
import "../../shared/maps/MapGrouping.css";

import {TABS, STATUS_COLORS, pretty, display} from "./viewModel.js";

import {StatusBadge} from "./AdminPrimitives.jsx";
export default function AdminDashboard({adminId = "Officer", slotTarget = null, section, onSectionChange, onContextualBackChange = () => {}}) {
  const [localTab, setLocalTab] = useState("overview");
  const [zoneView, setZoneView] = useState("list");
  const tab = section || localTab;
  const setTab = next => {setLocalTab(next); onSectionChange?.(next);};
  useEffect(() => {
    if (section === "map") dispatchPilot({type: "open"});
    else if (section) dispatchPilot({type: "close"});
  }, [section]);
  const [overview, setOverview] = useState(null);
  const [pending, setPending] = useState([]);
  const [zones, setZones] = useState([]);
  const [zonesLoaded, setZonesLoaded] = useState(false);
  const [allocations, setAllocations] = useState([]);
  const [allocationReloadToken, setAllocationReloadToken] = useState(0);
  const [geometry, setGeometry] = useState(null);
  const [zoneLoad, setZoneLoad] = useState({loading: true, error: "", ready: false});
  const [geometryError, setGeometryError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [heatmapRefreshToken, setHeatmapRefreshToken] = useState(0);
  const [zoneFilters, setZoneFilters] = useState({q: "", division: "", zone_type: "", live_status: ""});
  const [mapStatuses, setMapStatuses] = useState(Object.keys(STATUS_COLORS));
  const [selectedZoneSnapshot, setSelectedZone] = useState(null);
  // Always bind the drawer to the latest zone payload after Refresh data.
  // The snapshot only preserves the selected identity between fetches.
  const selectedZone = useMemo(
    () => selectedZoneSnapshot
      ? zones.find(zone => zone.zone_id === selectedZoneSnapshot.zone_id) || selectedZoneSnapshot
      : null,
    [zones, selectedZoneSnapshot],
  );
  const [pilot, dispatchPilot] = useReducer(pilotReducer, initialPilotState);
  const [focusedSlot, setFocusedSlot] = useState(null);
  const [zoneDivisionBack, setZoneDivisionBack] = useState(false);
  const [pilotZone,setPilotZone] = useState("NN_F_013");
  const [explorerDivision, setExplorerDivision] = useState("");
  const openPilot = (zone = selectedZone) => {const target = zone?.zone_id ? zone : selectedZone; setExplorerDivision(officialZoneDivision(target || pilotZone)); setPilotZone(target?.zone_id || pilotZone);dispatchPilot({type: "open"}); setTab("map"); setSelectedZone(null);};
  const [requestDetail, setRequestDetail] = useState(null);
  const [requestReview, setRequestReview] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [statusTarget, setStatusTarget] = useState(null);
  useDialogFocus(Boolean(dialog || statusTarget || selectedZone || requestDetail || requestReview), ".admin-modal, .admin-detail-modal, .admin-request-modal");
  useEffect(() => {
    const hasContextualBack = pilot.open
      || (zoneDivisionBack && (tab === "map" || tab === "zones" && zoneView === "map"));
    onContextualBackChange(hasContextualBack);
    return () => onContextualBackChange(false);
  }, [pilot.open, zoneDivisionBack, tab, zoneView, onContextualBackChange]);
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const refreshController = useRef(null);

  const refresh = async (message = "", reloadMapAllocations = true) => {
    refreshController.current?.abort();
    const controller = new AbortController();
    refreshController.current = controller;
    setLoading(true); setError("");
    const results = await Promise.allSettled([
      getAdminOverview(controller.signal),
      getAllocationRequests("PENDING", controller.signal),
      ...(zonesLoaded ? [getZoneCatalog({}, controller.signal)] : []),
    ]);
    if (controller.signal.aborted) return;
    const [summary, requestData, ...secondary] = results;
    const zoneData = zonesLoaded ? secondary.shift() : null;
    if (summary.status === "fulfilled") setOverview(summary.value);
    if (requestData.status === "fulfilled") setPending(requestData.value.requests);
    if (zoneData?.status === "fulfilled" && Array.isArray(zoneData.value?.zones) && zoneData.value.zones.length) {
      setZones(zoneData.value.zones);
      setZoneLoad({loading: false, error: "", ready: true});
      if (selectedZone) setSelectedZone(zoneData.value.zones.find(zone => zone.zone_id === selectedZone.zone_id) || null);
    } else if (zoneData) setZoneLoad(current => ({...current, loading: false, error: zoneData.reason?.message || "Official zone records are unavailable. Refresh to try again."}));
    const failures = results.filter(result => result.status === "rejected" && result.reason?.name !== "AbortError");
    if (failures.length) setError(failures.map(result => result.reason?.message || "Data unavailable").join("; "));
    else if (message) setNotice(message);
    setHeatmapRefreshToken(value => value + 1);
    if (tab === "map" && reloadMapAllocations) setAllocationReloadToken(value => value + 1);
    setLoading(false);
  };
  useEffect(() => {
    refresh("", false);
    return () => refreshController.current?.abort();
  }, []);
  useEffect(() => {
    if (tab === "overview" || zonesLoaded) return undefined;
    const controller = new AbortController();
    setZoneLoad({loading: true, error: "", ready: false});
    getZoneCatalog({}, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      setZones(result.zones || []);
      setZonesLoaded(true);
      setZoneLoad({loading: false, error: "", ready: true});
    }).catch(err => {
      if (err.name !== "AbortError") {
        setZonesLoaded(true);
        setZoneLoad({loading: false, error: err.message, ready: false});
      }
    });
    return () => controller.abort();
  }, [tab, zonesLoaded]);
  useEffect(() => {
    if (tab !== "map") return undefined;
    const controller = new AbortController();
    getAllocations("ACTIVE", controller.signal, {limit: 100, offset: 0}).then(result => {
      if (!controller.signal.aborted) {
        setAllocations(result.allocations);
      }
    }).catch(err => {if (err.name !== "AbortError") setError(err.message);});
    return () => controller.abort();
  }, [tab, allocationReloadToken]);
  useEffect(() => {
    if ((tab !== "map" && !(tab === "zones" && zoneView === "map")) || geometry) return undefined;
    const controller = new AbortController();
    setGeometryError("");
    getZoneGeometry(controller.signal).then(setGeometry).catch(err => {
      if (err.name !== "AbortError") setGeometryError(err.message || "GIS references are unavailable. Use the zone list below.");
    });
    return () => controller.abort();
  }, [tab, zoneView, geometry]);

  const divisions = useMemo(() => [...new Set(zones.map(zone => zone.division).filter(Boolean))].sort(), [zones]);
  const filteredZones = useMemo(() => zones.filter(zone =>
    (!zoneFilters.division || zone.division === zoneFilters.division)
    && (!zoneFilters.zone_type || zone.zone_type === zoneFilters.zone_type)
    && (!zoneFilters.live_status || zone.live_status === zoneFilters.live_status)
    && (!zoneFilters.q || `${zone.zone_id} ${zone.official_description}`.toLowerCase().includes(zoneFilters.q.toLowerCase()))
  ), [zones, zoneFilters]);
  const openRequest = request => setRequestReview(request);
  const viewAssignedSlot = slot => {setRequestDetail(null); setFocusedSlot(slot); setPilotZone(slot.zone_id); setExplorerDivision(officialZoneDivision(slot.zone_id)); dispatchPilot({type: "open"}); setTab("map");};
  useEffect(() => {if (slotTarget) viewAssignedSlot(slotTarget);}, [slotTarget]);
  const approve = async () => {
    if (!adminId.trim()) { setError("Enter an Admin ID before approval."); return; }
    setLoading(true); setError("");
    try {
      await approveAllocationRequest(dialog.request_id, notes || null);
      setDialog(null); setRequestDetail(null); setNotes("");
      await refresh(`Request ${dialog.request_id} approved. Allocation and occupancy were refreshed.`);
    } catch (err) { setError(err.message); setLoading(false); }
  };
  const reject = async () => {
    if (!adminId.trim()) { setError("Enter an Admin ID before rejection."); return; }
    if (!reason.trim()) { setError("A rejection reason is required."); return; }
    setLoading(true); setError("");
    try {
      await rejectAllocationRequest(dialog.request_id, reason.trim(), notes || null);
      setDialog(null); setRequestDetail(null); setReason(""); setNotes("");
      await refresh(`Request ${dialog.request_id} rejected. Zone occupancy was not changed.`);
    } catch (err) { setError(err.message); setLoading(false); }
  };
  const applyStatus = async status => {
    if (!adminId.trim()) { setError("Enter an Admin ID before changing zone status."); return; }
    setLoading(true); setError("");
    try {
      const zoneId = statusTarget?.zone_id || selectedZone?.zone_id;
      const updated = await updateZoneLiveStatus(zoneId, status);
      setStatusTarget(null);
      await refresh(`${zoneId} updated to ${updated.status}.`);
    } catch (err) { setError(err.message); setLoading(false); }
  };
  const changeStatus = status => setStatusTarget({zone_id: selectedZone.zone_id, from: selectedZone.live_status, status});
  const closeSelectedZone = () => setSelectedZone(null);
  useEffect(() => {
    if (!dialog && !statusTarget && !selectedZone && !requestDetail && !requestReview) return undefined;
    const close = event => {
      if (event.key !== "Escape") return;
      setDialog(null); setStatusTarget(null); closeSelectedZone(); setRequestDetail(null); setRequestReview(null);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [dialog, statusTarget, selectedZone, requestDetail, requestReview]);

  const zoneCounts = overview?.zone_status_counts || {};
  const requestCounts = overview?.request_status_counts || {};
  const allocationCounts = overview?.allocation_status_counts || {};
  const pressure = overview?.capacity_pressure || {};
  const summaryCards = [
    ["Official zones", overview?.total_official_zones, Building2, "neutral"],
    ["Open zones", zoneCounts.OPEN, Activity, "open"], ["Full zones", zoneCounts.FULL, AlertTriangle, "full"],
    ["Closed zones", zoneCounts.CLOSED, XCircle, "closed"], ["Suspended", zoneCounts.SUSPENDED, AlertTriangle, "suspended"],
    ["Restricted", zoneCounts.RESTRICTED, ShieldCheck, "restricted"], ["No vending", zoneCounts.NO_VENDING, XCircle, "novending"],
    ["Active allocations", allocationCounts.ACTIVE, Users, "active"], ["Pending requests", requestCounts.PENDING, ClipboardList, "pending"],
    ["Approved", requestCounts.APPROVED, Check, "approved"], ["Rejected", requestCounts.REJECTED, XCircle, "rejected"],
    ["Estimated overcapacity", pressure.planning_overcapacity_zone_count, AlertTriangle, "full"],
    ["Near planning capacity", pressure.near_planning_capacity_zone_count, Activity, "pending"],
  ];

  return <main className="admin-dashboard" aria-busy={loading}>
    <header className="admin-header"><div><span className="admin-eyebrow">NASHIK · OPERATIONS</span><h1>{({overview:"A better place to do business.",requests:"Application inbox",zones:"Places across the city",map:"Every spot, clearly mapped",heatmap:"Vendor density and competition"})[tab]}</h1></div><button className="vm-refresh" onClick={() => refresh("Workspace refreshed.")} disabled={loading}><RefreshCw size={16}/>Refresh</button></header>
    {!section && <nav className="admin-tabs" aria-label="Administration sections">{TABS.map(item => <button key={item.id} className={tab === item.id ? "active" : ""} aria-current={tab === item.id ? "page" : undefined} onClick={() => setTab(item.id)}><item.icon size={16}/>{item.label}{item.id === "requests" && <b>{pending.length}</b>}</button>)}</nav>}
    <ToastRegion success={notice} error={error} onDismissSuccess={() => setNotice("")} onDismissError={() => setError("")} retry={() => refresh()}/>
    {loading && !overview && <div className="admin-loading-state" role="status"><RefreshCw size={20}/><div><strong>Loading operational dashboard</strong><span>Retrieving requests, allocations, live zone status, and map references.</span></div></div>}

    {tab === "overview" && <AdminHome pending={pending} allocationCounts={allocationCounts} summaryCards={summaryCards} zoneCounts={zoneCounts} setTab={setTab} setZoneFilters={setZoneFilters}/>}

    {tab === "requests" && <PendingRequests pending={pending} zones={zones} openRequest={openRequest} setDialog={setDialog}/>}

    {tab === "zones" && <div className="vm-view-switch" role="group" aria-label="Zone view"><button aria-pressed={zoneView === "list"} onClick={() => setZoneView("list")}>Zone list</button><button aria-pressed={zoneView === "map"} onClick={() => setZoneView("map")}>City map</button></div>}
    {tab === "zones" && zoneView === "list" && <ZoneManagement filteredZones={filteredZones} zoneFilters={zoneFilters} setZoneFilters={setZoneFilters} divisions={divisions} setSelectedZone={setSelectedZone}/>}

    {(tab === "map" && !pilot.open || tab === "zones" && zoneView === "map") && <ZoneExplorer zoneLoad={zoneLoad} geometryError={geometryError} onRetry={() => refresh()} zones={zones} division={explorerDivision} setDivision={setExplorerDivision} onPilot={openPilot} onContextualBackChange={setZoneDivisionBack} zoneFilters={zoneFilters} setZoneFilters={setZoneFilters} mapStatuses={mapStatuses} setMapStatuses={setMapStatuses} geometry={geometry} setSelectedZone={setSelectedZone}/>}

    {tab === "heatmap" && <React.Suspense fallback={<p role="status">Loading vendor heatmap…</p>}><VendorHeatmap refreshToken={heatmapRefreshToken}/></React.Suspense>}

    {pilot.visited && <React.Suspense fallback={<p role="status">Loading geographic pilot…</p>}><PilotSlotMap zoneId={pilotZone} zone={zones.find(zone => zone.zone_id === pilotZone)} zones={zones} onZoneChange={zoneId => {setPilotZone(zoneId); setExplorerDivision(officialZoneDivision(zoneId));}} onViewVendor={allocation => setRequestDetail({vendor_id: allocation.vendor_id})} focusSlotId={focusedSlot?.zone_id === pilotZone ? focusedSlot.slot_id : null} admin session={pilot} dispatch={dispatchPilot} visible={tab === "map" && pilot.open} onBack={() => dispatchPilot({type: "close"})} allocations={allocations}/></React.Suspense>}

    {requestDetail && <VendorDetails vendorId={requestDetail.vendor_id || requestDetail.vendor?.vendor_id} requestId={requestDetail.request?.request_id} zones={zones} onClose={() => setRequestDetail(null)} onViewSlot={viewAssignedSlot} onDecision={(type, request) => setDialog({type, ...request})}/>}

    <RequestReviewModal request={requestReview} zones={zones} onClose={() => setRequestReview(null)} onDecision={(type,request) => {setRequestReview(null);setDialog({type,...request});}}/>

    <ZoneDetailsModal zone={selectedZone} pendingCount={selectedZone ? pending.filter(item => item.zone_id === selectedZone.zone_id).length : 0} loading={loading} onClose={closeSelectedZone} onOpenMap={() => openPilot(selectedZone)} onChangeStatus={changeStatus}/>

    {dialog && <div className="admin-modal-backdrop" onClick={() => setDialog(null)}><div className="admin-modal" onClick={event => event.stopPropagation()}><div className={`modal-icon ${dialog.type}`} >{dialog.type === "approve" ? <Check size={24}/> : <XCircle size={24}/>}</div><span className="admin-eyebrow">{dialog.type === "approve" ? "CONFIRM APPROVAL" : "REJECT REQUEST"}</span><h2>{dialog.type === "approve" ? dialog.request_type === "SLOT_CHANGE" ? `Approve change to slot ${dialog.slot_id}?` : `Approve ${dialog.slot_id ? `slot ${dialog.slot_id} in ` : "allocation to "}${zoneName(dialog.zone_id)}?` : `Reject ${dialog.request_id}?`}</h2>{dialog.type === "approve" && <p>{dialog.request_type === "SLOT_CHANGE" ? "This keeps the vendor in the same zone, releases their previous slot, and assigns the requested slot. Zone occupancy will not change." : dialog.slot_id ? "The requested slot will be confirmed only if it is still reserved for this application." : "This zone-only request will create an allocation without assigning a physical slot."}</p>}{dialog.type === "reject" && <label><span>Rejection reason *</span><textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Explain why this request cannot be approved"/></label>}<label><span>Officer notes <small>optional</small></span><textarea value={notes} onChange={event => setNotes(event.target.value)} placeholder="Internal review note"/></label><div className="modal-capacity"><span>Request type</span><strong>{pretty(dialog.request_type)}</strong><span>Requested slot</span><strong>{dialog.slot_id || "Zone only"}</strong><span>Current occupancy</span><strong>{zones.find(zone => zone.zone_id === dialog.zone_id)?.current_vendor_count ?? "—"}</strong><span>Available before review</span><strong>{display(zones.find(zone => zone.zone_id === dialog.zone_id)?.available_capacity)}</strong></div><div className="modal-actions"><button onClick={() => setDialog(null)}>Cancel</button><button className={dialog.type === "approve" ? "admin-approve" : "admin-reject"} onClick={dialog.type === "approve" ? approve : reject} disabled={loading}>{dialog.type === "approve" ? dialog.request_type === "SLOT_CHANGE" ? "Approve slot change" : "Approve allocation" : "Reject request"}</button></div></div></div>}
    {statusTarget && <div className="admin-modal-backdrop" onClick={() => setStatusTarget(null)}><div className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="zone-status-title" onClick={event => event.stopPropagation()}><div className="modal-icon approve"><ShieldCheck size={24}/></div><span className="admin-eyebrow">CONFIRM STATUS CHANGE</span><h2 id="zone-status-title">Change {zoneName(statusTarget.zone_id)} to {pretty(statusTarget.status)}?</h2><p>{statusTarget.status === "OPEN" ? "This will reopen the zone for operational use. Capacity rules still apply." : `This will remove the zone from live vendor recommendations while it is ${statusTarget.status.toLowerCase()}.`}</p><div className="modal-capacity"><span>Current status</span><strong>{pretty(statusTarget.from)}</strong><span>New status</span><strong>{pretty(statusTarget.status)}</strong></div><div className="modal-actions"><button onClick={() => setStatusTarget(null)}>Keep current status</button><button className={statusTarget.status === "OPEN" ? "admin-approve" : "admin-reject"} onClick={() => applyStatus(statusTarget.status)} disabled={loading}>Confirm change</button></div></div></div>}
  </main>;
}
