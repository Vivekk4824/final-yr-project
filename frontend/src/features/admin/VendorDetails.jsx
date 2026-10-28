import React, {useEffect, useState} from "react";
import {X} from "lucide-react";
import {getAdminVendorDetails, getVendorRelocationRecommendations} from "../../services/api.js";
import {zoneName} from "../../shared/utils/displayLabels.js";
import {useDialogFocus} from "../../shared/utils/dialogFocus.js";
import {StatusBadge} from "./AdminPrimitives.jsx";
import {pretty, display, when} from "./viewModel.js";

export default function VendorDetails({vendorId, requestId, onClose, onViewSlot, onDecision, zones = []}) {
  const [data, setData] = useState(null), [error, setError] = useState("");
  const [relocation, setRelocation] = useState(null), [relocationLoading, setRelocationLoading] = useState(false);
  useDialogFocus(Boolean(vendorId), ".vendor-management-details");
  useEffect(() => {
    const controller = new AbortController(); setData(null); setError("");
    getAdminVendorDetails(vendorId, controller.signal).then(result => {if (!controller.signal.aborted) setData(result);}).catch(err => {if (!controller.signal.aborted) setError(err.message);});
    return () => controller.abort();
  }, [vendorId]);
  useEffect(() => {
    const close = event => {if (event.key === "Escape") onClose();};
    document.addEventListener("keydown", close); return () => document.removeEventListener("keydown", close);
  }, [onClose]);
  const relevant = data?.requests.find(request => request.request_id === requestId);
  const association = data?.historical_association;
  const acceptedZone = zones.find(zone => zone.zone_id === association?.matched_zone_id);
  const loadRelocation = async () => {
    setRelocationLoading(true); setError("");
    try { setRelocation(await getVendorRelocationRecommendations(vendorId)); }
    catch (err) { setError(err.message); }
    finally { setRelocationLoading(false); }
  };
  const account = {PHONE_VERIFIED: "Phone verified", UNCLAIMED: "Not yet claimed", NO_LINKED_IDENTITY: "No linked login identity"};
  return <div className="admin-drawer-backdrop" onClick={onClose}><aside className="admin-drawer vendor-management-details" role="dialog" aria-modal="true" aria-labelledby="management-vendor-title" onClick={event => event.stopPropagation()}><button className="drawer-close" aria-label="Close vendor details" onClick={onClose}><X size={18}/></button><span className="admin-eyebrow">VENDOR DETAILS</span><h2 id="management-vendor-title">{data?.profile.full_name || data?.profile.business_name || "Vendor details"}</h2>{error && <p role="alert">{error}</p>}{!data && !error && <p role="status">Loading vendor relationships...</p>}{data && <>
    <div className="drawer-grid">{[["Vendor reference", data.profile.application_vendor_id || vendorId], ["Business name", display(data.profile.business_name)], ["Business category", pretty(data.profile.business_category)], ["Record source", data.record_source === "HISTORICAL" ? "Historical record" : "Registered vendor"], ["Registration", data.registration_status === "PROFILE_REGISTERED" ? "Profile registered" : "Historical record only"], ["Account", account[data.account_status]], ["Source division", display(data.source_division)]].map(([label,value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    {data.record_source === "HISTORICAL" && association && <section className="historical-association-review" aria-labelledby="historical-association-title"><div className="historical-association-heading"><div><h3 id="historical-association-title">Historical registry location</h3><p>Read-only source evidence. It is not a permit, live occupancy, allocation, or individual GPS position.</p></div></div><div className="drawer-grid"><div><span>Accepted official zone ID</span><strong>{association.accepted && association.matched_zone_id ? association.matched_zone_id : "Unresolved"}</strong></div><div><span>Official description</span><strong>{acceptedZone?.official_description || "No accepted association"}</strong></div><div><span>Official division</span><strong>{acceptedZone?.division || "No accepted association"}</strong></div><div><span>Recorded division</span><strong>{display(association.recorded_division)}</strong></div><div><span>Recorded location</span><strong>{display(association.location_text_english || association.original_location_text)}</strong></div><div><span>Association result</span><strong>{association.accepted ? "Accepted strong association" : "Unresolved / not accepted"}</strong></div></div></section>}
    {data.record_source === "HISTORICAL" && !association && <p className="drawer-description">No reconciled historical zone association is available. This does not affect the vendor's current operational record.</p>}
    <h3>Current operational allocation</h3>{data.active_allocation ? <><strong>{zoneName(data.active_allocation.zone_id)}</strong><p><StatusBadge status={data.active_allocation.status}/> {when(data.active_allocation.allocated_at)}</p><p>{data.active_allocation.allocation_source === "LEGACY_IMPORT" ? "Imported existing allocation — not individually admin-approved" : "Admin-approved allocation"}</p></> : <p>No current operational allocation recorded.</p>}
    <h3>Assigned geographic slot</h3>{data.assigned_slot ? <><p><strong>{data.assigned_slot.slot_id}</strong> - {zoneName(data.assigned_slot.zone_id)} <StatusBadge status={data.assigned_slot.status}/></p><p>{data.assigned_slot.width_m} m x {data.assigned_slot.depth_m} m</p><button className="admin-approve" onClick={() => onViewSlot(data.assigned_slot)}>View Assigned Slot on Map</button></> : <p>No geographic slot assignment recorded.</p>}
    {(data.active_allocation || association?.accepted) && <section className="relocation-planning"><h3>Relocation planning</h3><p>Read-only alternatives use current operational vacancy and the existing MCDA model. No application or allocation is created.</p><button onClick={loadRelocation} disabled={relocationLoading}>{relocationLoading ? "Calculating alternatives…" : relocation ? "Refresh alternatives" : "View relocation alternatives"}</button>{relocation && <><p><strong>Source:</strong> {relocation.source_zone_id} · {pretty(relocation.source_type)}</p><div className="relocation-alternatives">{relocation.recommendations.map(item => <article key={item.zone_id}><div><strong>#{item.relocation_rank} {item.zone_id}</strong><span>{item.official_description}</span></div><StatusBadge status={item.proximity_tier}/><p>MCDA score {item.mcda_score.toFixed(2)} · {item.distance_m == null ? "Distance unavailable" : `${(item.distance_m / 1000).toFixed(2)} km`} · {display(item.operational_available)} operationally available</p><p>Estimated planning remaining: {display(item.planning_available)}{item.planning_overcapacity ? ` · estimated overcapacity ${item.planning_overcapacity}` : ""}</p></article>)}</div><small>{relocation.notice}</small></>}</section>}
    {relevant && <section><h3>Selected application</h3><p>{relevant.request_id} <StatusBadge status={relevant.status}/></p><p>{pretty(relevant.request_type)} - {zoneName(relevant.zone_id)}</p>{relevant.status === "PENDING" && onDecision && <div className="drawer-actions"><button className="admin-approve" onClick={() => onDecision("approve", relevant)}>Approve request</button><button className="admin-reject" onClick={() => onDecision("reject", relevant)}>Reject request</button></div>}</section>}
    <h3>Application history</h3>{data.requests.length ? data.requests.map(request => <article className="drawer-description" key={request.request_id}><strong>{zoneName(request.zone_id)}</strong><p>{pretty(request.request_type)} <StatusBadge status={request.status}/></p><small>{request.request_id} - {when(request.created_at)}</small>{request.rejection_reason && <p>Reason: {request.rejection_reason}</p>}</article>) : <p>No applications recorded.</p>}
    <h3>Allocation history</h3>{data.allocations.length ? data.allocations.map(allocation => <article className="drawer-description" key={allocation.allocation_id}><strong>{zoneName(allocation.zone_id)}</strong><p><StatusBadge status={allocation.status}/> Allocated: {when(allocation.allocated_at)}</p><p>{allocation.allocation_source === "LEGACY_IMPORT" ? "Imported existing allocation" : "Admin-approved allocation"}</p>{allocation.released_at && <p>Released: {when(allocation.released_at)}</p>}</article>) : <p>No allocation history recorded.</p>}
  </>}</aside></div>;
}
