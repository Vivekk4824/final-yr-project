import VendorDetails from "./VendorDetails.jsx";
import {zoneName, officialZoneDivision} from "../../shared/utils/displayLabels.js";
import {AdminHome, PendingRequests, RequestReviewModal, ZoneManagement, AllocationRecords, ZoneExplorer} from "./AdminTabPanels.jsx";
import React, {useEffect, useMemo, useReducer, useRef, useState} from "react";

import "leaflet/dist/leaflet.css";
import {Activity, AlertTriangle, Building2, Check, ClipboardList, RefreshCw, ShieldCheck, Users, X, XCircle} from "lucide-react";
import {approveAllocationRequest, getAdminOverview, getAllocationRequests, getAllocations, getZoneCatalog, getZoneGeometry, getZoneHistoricalVendors, rejectAllocationRequest, updateZoneLiveStatus} from "../../services/api.js";

import ToastRegion from "../../shared/ui/ToastRegion.jsx";
const PilotSlotMap = React.lazy(() => import("../pilot-slots/PilotSlotMap.jsx"));
import {initialPilotState, pilotReducer} from "../pilot-slots/pilotState.js";
import {useDialogFocus} from "../../shared/utils/dialogFocus.js";
import "./AdminDashboard.css";
import "../../shared/maps/MapGrouping.css";

import {TABS, STATUS_COLORS, pretty, display, when} from "./viewModel.js";

import {StatusBadge} from "./AdminPrimitives.jsx";
const ALLOCATION_PAGE_SIZE = 50;

export default function AdminDashboard({adminId = "Officer", slotTarget = null}) {
  const [tab, setTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [pending, setPending] = useState([]);
  const [zones, setZones] = useState([]);
  const PILOT_ZONE_IDS = zones.map(zone => zone.zone_id);
  const [zonesLoaded, setZonesLoaded] = useState(false);
  const [allocations, setAllocations] = useState([]);
  const [allocationTotal, setAllocationTotal] = useState(0);
  const [allocationPage, setAllocationPage] = useState(0);
  const [allocationsLoaded, setAllocationsLoaded] = useState(false);
  const [allocationsLoading, setAllocationsLoading] = useState(false);
  const [allocationsError, setAllocationsError] = useState("");
  const [geometry, setGeometry] = useState(null);
  const [zoneLoad, setZoneLoad] = useState({loading: true, error: "", ready: false});
  const [geometryError, setGeometryError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [zoneFilters, setZoneFilters] = useState({q: "", division: "", zone_type: "", live_status: ""});
  const [allocationFilter, setAllocationFilter] = useState("");
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
  const [historicalVendors, setHistoricalVendors] = useState(null);
  const [historicalVendorsLoading, setHistoricalVendorsLoading] = useState(false);
  const [pilot, dispatchPilot] = useReducer(pilotReducer, initialPilotState);
  const [focusedSlot, setFocusedSlot] = useState(null);
  const [pilotZone,setPilotZone] = useState("NN_F_013");
  const [explorerDivision, setExplorerDivision] = useState("");
  const openPilot = (zone = selectedZone) => {const target = zone?.zone_id ? zone : selectedZone; setExplorerDivision(officialZoneDivision(target || pilotZone)); setPilotZone(target?.zone_id || pilotZone);dispatchPilot({type: "open"}); setTab("map"); setSelectedZone(null);};
  const [requestDetail, setRequestDetail] = useState(null);
  const [requestReview, setRequestReview] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [statusTarget, setStatusTarget] = useState(null);
  useDialogFocus(Boolean(dialog || statusTarget || selectedZone || requestDetail || requestReview), ".admin-modal, .admin-drawer, .admin-request-modal");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const refreshController = useRef(null);

  const refresh = async (message = "") => {
    refreshController.current?.abort();
    const controller = new AbortController();
    refreshController.current = controller;
    setLoading(true); setError("");
    const shouldLoadAllocations = allocationsLoaded || tab === "allocations";
    const results = await Promise.allSettled([
      getAdminOverview(controller.signal),
      getAllocationRequests("PENDING", controller.signal),
      ...(zonesLoaded ? [getZoneCatalog({}, controller.signal)] : []),
      ...(shouldLoadAllocations ? [getAllocations(allocationFilter, controller.signal, {
        limit: ALLOCATION_PAGE_SIZE,
        offset: allocationPage * ALLOCATION_PAGE_SIZE,
      })] : []),
    ]);
    if (controller.signal.aborted) return;
    const [summary, requestData, ...secondary] = results;
    const zoneData = zonesLoaded ? secondary.shift() : null;
    const allocationData = shouldLoadAllocations ? secondary.shift() : null;
    if (summary.status === "fulfilled") setOverview(summary.value);
    if (requestData.status === "fulfilled") setPending(requestData.value.requests);
    if (allocationData?.status === "fulfilled") {
      setAllocations(allocationData.value.allocations);
      setAllocationTotal(allocationData.value.total_count ?? allocationData.value.count);
      setAllocationsLoaded(true);
      setAllocationsError("");
    } else if (allocationData?.status === "rejected") {
      setAllocationsError(allocationData.reason?.message || "Unable to load allocations.");
    }
    if (zoneData?.status === "fulfilled" && Array.isArray(zoneData.value?.zones) && zoneData.value.zones.length) {
      setZones(zoneData.value.zones);
      setZoneLoad({loading: false, error: "", ready: true});
      if (selectedZone) setSelectedZone(zoneData.value.zones.find(zone => zone.zone_id === selectedZone.zone_id) || null);
    } else if (zoneData) setZoneLoad(current => ({...current, loading: false, error: zoneData.reason?.message || "Official zone records are unavailable. Refresh to try again."}));
    const failures = results.filter(result => result.status === "rejected" && result.reason?.name !== "AbortError");
    if (failures.length) setError(failures.map(result => result.reason?.message || "Data unavailable").join("; "));
    else if (message) setNotice(message);
    setLoading(false);
  };
  useEffect(() => {
    refresh();
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
    if (tab !== "allocations") return undefined;
    const controller = new AbortController();
    setAllocationsLoading(true);
    setAllocationsError("");
    getAllocations(allocationFilter, controller.signal, {
      limit: ALLOCATION_PAGE_SIZE,
      offset: allocationPage * ALLOCATION_PAGE_SIZE,
    }).then(result => {
      if (!controller.signal.aborted) {
        setAllocations(result.allocations);
        setAllocationTotal(result.total_count ?? result.count);
        setAllocationsLoaded(true);
      }
    }).catch(err => {if (err.name !== "AbortError") {setError(err.message); setAllocationsError(err.message);}})
      .finally(() => {if (!controller.signal.aborted) setAllocationsLoading(false);});
    return () => controller.abort();
  }, [tab, allocationFilter, allocationPage]);
  useEffect(() => {
    if (tab !== "map" || geometry) return undefined;
    const controller = new AbortController();
    setGeometryError("");
    getZoneGeometry(controller.signal).then(setGeometry).catch(err => {
      if (err.name !== "AbortError") setGeometryError(err.message || "GIS references are unavailable. Use the zone list below.");
    });
    return () => controller.abort();
  }, [tab, geometry]);

  const divisions = useMemo(() => [...new Set(zones.map(zone => zone.division).filter(Boolean))].sort(), [zones]);
  const filteredZones = useMemo(() => zones.filter(zone =>
    (!zoneFilters.division || zone.division === zoneFilters.division)
    && (!zoneFilters.zone_type || zone.zone_type === zoneFilters.zone_type)
    && (!zoneFilters.live_status || zone.live_status === zoneFilters.live_status)
    && (!zoneFilters.q || `${zone.zone_id} ${zone.official_description}`.toLowerCase().includes(zoneFilters.q.toLowerCase()))
  ), [zones, zoneFilters]);
  const filteredAllocations = allocations;
  const changeAllocationFilter = status => {
    setAllocationFilter(status);
    setAllocationPage(0);
  };

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
  const closeSelectedZone = () => {setSelectedZone(null); setHistoricalVendors(null);};
  const loadHistoricalVendors = async () => {
    if (!selectedZone || historicalVendorsLoading) return;
    setHistoricalVendorsLoading(true);
    try { setHistoricalVendors(await getZoneHistoricalVendors(selectedZone.zone_id)); }
    catch (err) { setError(err.message); }
    finally { setHistoricalVendorsLoading(false); }
  };
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
    <header className="admin-header"><div className="admin-header-identity"><img src="/nmc-logo.jpg" alt="Nashik Municipal Corporation emblem"/><div><span className="admin-eyebrow">NASHIK MUNICIPAL CORPORATION</span><h1>Vendor operations</h1><p>Street Vendor Management — Officer Portal</p></div></div><div className="admin-controls"><div className="admin-session-id"><span>Signed in officer</span><strong>{adminId}</strong></div><button onClick={() => refresh("Dashboard data refreshed.")} disabled={loading}><RefreshCw size={15}/>{loading ? "Refreshing…" : "Refresh data"}</button></div></header>
    <nav className="admin-tabs" aria-label="Administration sections">{TABS.map(item => <button key={item.id} className={tab === item.id ? "active" : ""} aria-current={tab === item.id ? "page" : undefined} onClick={() => setTab(item.id)}><item.icon size={16}/>{item.label}{item.id === "requests" && <b>{pending.length}</b>}</button>)}</nav>
    <ToastRegion success={notice} error={error} onDismissSuccess={() => setNotice("")} onDismissError={() => setError("")} retry={() => refresh()}/>
    {loading && !overview && <div className="admin-loading-state" role="status"><RefreshCw size={20}/><div><strong>Loading operational dashboard</strong><span>Retrieving requests, allocations, live zone status, and map references.</span></div></div>}

    {tab === "overview" && <AdminHome pending={pending} allocationCounts={allocationCounts} summaryCards={summaryCards} zoneCounts={zoneCounts} setTab={setTab} setAllocationFilter={setAllocationFilter} setZoneFilters={setZoneFilters}/>}

    {tab === "requests" && <PendingRequests pending={pending} zones={zones} openRequest={openRequest} setDialog={setDialog}/>}

    {tab === "zones" && <ZoneManagement filteredZones={filteredZones} zoneFilters={zoneFilters} setZoneFilters={setZoneFilters} divisions={divisions} setSelectedZone={setSelectedZone}/>}

    {tab === "allocations" && <AllocationRecords filteredAllocations={filteredAllocations} allocationFilter={allocationFilter} setAllocationFilter={changeAllocationFilter} setRequestDetail={setRequestDetail} zones={zones} setSelectedZone={setSelectedZone} loading={allocationsLoading || (loading && tab === "allocations")} loaded={allocationsLoaded} error={allocationsError} onRetry={() => refresh()} total={allocationTotal} page={allocationPage} pageSize={ALLOCATION_PAGE_SIZE} onPageChange={setAllocationPage}/>}

    {tab === "map" && !pilot.open && <ZoneExplorer zoneLoad={zoneLoad} geometryError={geometryError} onRetry={() => refresh()} zones={zones} division={explorerDivision} setDivision={setExplorerDivision} onPilot={openPilot} zoneFilters={zoneFilters} setZoneFilters={setZoneFilters} mapStatuses={mapStatuses} setMapStatuses={setMapStatuses} geometry={geometry} setSelectedZone={setSelectedZone}/>}

    {pilot.visited && <React.Suspense fallback={<p role="status">Loading geographic pilot…</p>}><PilotSlotMap zoneId={pilotZone} zone={zones.find(zone => zone.zone_id === pilotZone)} zones={zones} onZoneChange={zoneId => {setPilotZone(zoneId); setExplorerDivision(officialZoneDivision(zoneId));}} onViewVendor={allocation => setRequestDetail({vendor_id: allocation.vendor_id})} focusSlotId={focusedSlot?.zone_id === pilotZone ? focusedSlot.slot_id : null} admin session={pilot} dispatch={dispatchPilot} visible={tab === "map" && pilot.open} onBack={() => dispatchPilot({type: "close"})} allocations={allocations}/></React.Suspense>}

    {requestDetail && <VendorDetails vendorId={requestDetail.vendor_id || requestDetail.vendor?.vendor_id} requestId={requestDetail.request?.request_id} zones={zones} onClose={() => setRequestDetail(null)} onViewSlot={viewAssignedSlot} onDecision={(type, request) => setDialog({type, ...request})}/>}

    <RequestReviewModal request={requestReview} zones={zones} onClose={() => setRequestReview(null)}/>

    {selectedZone && <div className="admin-drawer-backdrop" onClick={closeSelectedZone}><aside className="admin-drawer" onClick={event => event.stopPropagation()}><button className="drawer-close" onClick={closeSelectedZone}><X size={18}/></button><span className="admin-eyebrow">ZONE DETAILS</span><h2>{selectedZone.zone_id}</h2><p>{zoneName(selectedZone)}</p><StatusBadge status={selectedZone.live_status}/><p className="drawer-description">{selectedZone.official_description}</p><div className="drawer-grid"><div><span>Official division</span><strong>{selectedZone.division}</strong></div><div><span>Official zone type</span><strong>{pretty(selectedZone.zone_type)}</strong></div><div><span>Listed official capacity</span><strong>{display(selectedZone.listed_official_capacity)}</strong></div><div><span>Current active vendors</span><strong>{selectedZone.operational_occupancy}</strong></div><div><span>Operational available</span><strong>{display(selectedZone.operational_available)}</strong></div><div><span>Historical planning count</span><strong>{selectedZone.historical_planning_count}</strong></div><div><span>Estimated planning load</span><strong>{selectedZone.planning_load}</strong></div><div><span>Estimated planning remaining</span><strong>{display(selectedZone.planning_available)}</strong></div>{selectedZone.planning_overcapacity > 0 && <div><span>Estimated planning overcapacity</span><strong>{selectedZone.planning_overcapacity}</strong></div>}<div><span>Capacity pressure</span><strong>{pretty(selectedZone.capacity_pressure_status)}</strong></div><div><span>Pending requests</span><strong>{pending.filter(item => item.zone_id === selectedZone.zone_id).length}</strong></div><div><span>Historical evidence</span><strong>{pretty(selectedZone.historical_evidence_status)}</strong></div></div><section className="zone-historical-evidence"><h3>Historical vendor evidence</h3><p>Accepted historical associations are separate from approved operational allocations and physical slots.</p><div className="historical-zone-summary"><strong>{selectedZone.historical_planning_count || 0}</strong><span>unallocated historical profiles in planning load ({selectedZone.accepted_historical_association_count || 0} accepted associations total)</span></div>{Object.entries(selectedZone.historical_business_categories || {}).length > 0 && <ul className="historical-category-list">{Object.entries(selectedZone.historical_business_categories).sort((a, b) => b[1] - a[1]).map(([category, count]) => <li key={category}><span>{pretty(category)}</span><strong>{count}</strong></li>)}</ul>}<button onClick={loadHistoricalVendors} disabled={historicalVendorsLoading || !selectedZone.accepted_historical_association_count}>{historicalVendorsLoading ? "Loading…" : historicalVendors ? "Refresh associated vendors" : "View associated vendors"}</button>{historicalVendors && <div className="historical-vendor-list"><p>{historicalVendors.notice}</p>{historicalVendors.vendors.map(vendor => <article key={vendor.vendor_id}><div><strong>{vendor.full_name || vendor.vendor_id}</strong><small>{vendor.vendor_id} · {pretty(vendor.business_category)}</small></div><span>{pretty(vendor.account_status)} · {vendor.active_allocation ? `Active in ${vendor.active_allocation.zone_id}` : "No active allocation"}</span></article>)}</div>}</section>{PILOT_ZONE_IDS.includes(selectedZone.zone_id) && <button onClick={openPilot}>View Slot Map</button>}{selectedZone.zone_type === "FREE" ? <div className="zone-status-actions"><span>Manual operational status</span><p>FULL remains capacity-derived. Opening a zero-capacity zone keeps it FULL.</p><div>{["OPEN", "CLOSED", "SUSPENDED"].map(status => <button key={status} disabled={loading || selectedZone.live_status === status} onClick={() => changeStatus(status)}>{status}</button>)}</div></div> : <div className="policy-lock"><ShieldCheck size={17}/> Policy-controlled {pretty(selectedZone.zone_type)} zones cannot be changed here.</div>}</aside></div>}

    {dialog && <div className="admin-modal-backdrop" onClick={() => setDialog(null)}><div className="admin-modal" onClick={event => event.stopPropagation()}><div className={`modal-icon ${dialog.type}`} >{dialog.type === "approve" ? <Check size={24}/> : <XCircle size={24}/>}</div><span className="admin-eyebrow">{dialog.type === "approve" ? "CONFIRM APPROVAL" : "REJECT REQUEST"}</span><h2>{dialog.type === "approve" ? `Approve allocation to ${zoneName(dialog.zone_id)}?` : `Reject ${dialog.request_id}?`}</h2>{dialog.type === "approve" && <p>This will approve the allocation and update the number of occupied places.</p>}{dialog.type === "reject" && <label><span>Rejection reason *</span><textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Explain why this request cannot be approved"/></label>}<label><span>Officer notes <small>optional</small></span><textarea value={notes} onChange={event => setNotes(event.target.value)} placeholder="Internal review note"/></label><div className="modal-capacity"><span>Current occupancy</span><strong>{zones.find(zone => zone.zone_id === dialog.zone_id)?.current_vendor_count ?? "—"}</strong><span>Available before review</span><strong>{display(zones.find(zone => zone.zone_id === dialog.zone_id)?.available_capacity)}</strong></div><div className="modal-actions"><button onClick={() => setDialog(null)}>Cancel</button><button className={dialog.type === "approve" ? "admin-approve" : "admin-reject"} onClick={dialog.type === "approve" ? approve : reject} disabled={loading}>{dialog.type === "approve" ? "Approve allocation" : "Reject request"}</button></div></div></div>}
    {statusTarget && <div className="admin-modal-backdrop" onClick={() => setStatusTarget(null)}><div className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="zone-status-title" onClick={event => event.stopPropagation()}><div className="modal-icon approve"><ShieldCheck size={24}/></div><span className="admin-eyebrow">CONFIRM STATUS CHANGE</span><h2 id="zone-status-title">Change {zoneName(statusTarget.zone_id)} to {pretty(statusTarget.status)}?</h2><p>{statusTarget.status === "OPEN" ? "This will reopen the zone for operational use. Capacity rules still apply." : `This will remove the zone from live vendor recommendations while it is ${statusTarget.status.toLowerCase()}.`}</p><div className="modal-capacity"><span>Current status</span><strong>{pretty(statusTarget.from)}</strong><span>New status</span><strong>{pretty(statusTarget.status)}</strong></div><div className="modal-actions"><button onClick={() => setStatusTarget(null)}>Keep current status</button><button className={statusTarget.status === "OPEN" ? "admin-approve" : "admin-reject"} onClick={() => applyStatus(statusTarget.status)} disabled={loading}>Confirm change</button></div></div></div>}
  </main>;
}
