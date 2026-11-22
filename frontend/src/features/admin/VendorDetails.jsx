import React, {useEffect, useMemo, useState} from "react";
import {Building2, CheckCircle2, MapPin, X} from "lucide-react";

import {getAdminVendorDetails} from "../../services/api.js";
import {zoneName} from "../../shared/utils/displayLabels.js";
import {useDialogFocus} from "../../shared/utils/dialogFocus.js";
import {StatusBadge} from "./AdminPrimitives.jsx";
import {pretty, display, when} from "./viewModel.js";

export default function VendorDetails({vendorId, requestId, onClose, onViewSlot, onDecision, zones = []}) {
  const [data,setData] = useState(null), [error,setError] = useState("");
  useDialogFocus(Boolean(vendorId), ".admin-detail-modal");
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError("");
    getAdminVendorDetails(vendorId,controller.signal)
      .then(result => {if (!controller.signal.aborted) setData(result);})
      .catch(reason => {if (!controller.signal.aborted) setError(reason.message);});
    return () => controller.abort();
  },[vendorId]);
  useEffect(() => {
    const close = event => {if (event.key === "Escape") onClose();};
    document.addEventListener("keydown",close);
    return () => document.removeEventListener("keydown",close);
  },[onClose]);

  const relevant = data?.requests.find(request => request.request_id === requestId);
  const latestRequest = data?.requests?.[0];
  const association = data?.historical_association;
  const related = useMemo(() => {
    if (!data) return null;
    if (data.active_allocation?.zone_id) return {zone_id:data.active_allocation.zone_id,source:"Active allocation"};
    if (data.assigned_slot?.zone_id) return {zone_id:data.assigned_slot.zone_id,source:"Assigned slot"};
    if (association?.accepted && association.matched_zone_id) return {zone_id:association.matched_zone_id,source:"Accepted historical association"};
    if (data.historical_proposed_zone_id) return {zone_id:data.historical_proposed_zone_id,source:"Recorded historical vending-zone relationship"};
    if (association?.candidate_zone_ids?.[0]) return {zone_id:association.candidate_zone_ids[0],source:"Candidate vending-zone relationship · not yet confirmed"};
    if (latestRequest?.zone_id) return {zone_id:latestRequest.zone_id,source:"Latest application"};
    return null;
  },[data,association,latestRequest]);
  const relatedZone = zones.find(zone => zone.zone_id === related?.zone_id);
  const account = {PHONE_VERIFIED:"Phone verified",UNCLAIMED:"Not yet claimed",NO_LINKED_IDENTITY:"No linked login"};

  return <div className="admin-detail-backdrop" onClick={onClose}>
    <section className="admin-detail-modal vendor-management-details" role="dialog" aria-modal="true" aria-labelledby="management-vendor-title" onClick={event => event.stopPropagation()}>
      <button className="admin-detail-close" aria-label="Close vendor details" onClick={onClose}><X size={19}/></button>
      <span className="admin-eyebrow">VENDOR DETAILS</span>
      <h2 id="management-vendor-title">{data?.profile.full_name || data?.profile.business_name || "Vendor details"}</h2>
      {error && <div className="admin-detail-error" role="alert">{error}</div>}
      {!data && !error && <p role="status">Loading vendor details…</p>}
      {data && <>
        <div className="admin-detail-tags"><span>{pretty(data.profile.business_category)}</span><span>{data.profile.application_vendor_id || vendorId}</span></div>
        <div className="admin-key-facts">
          <div><span>Business</span><strong>{display(data.profile.business_name)}</strong></div>
          <div><span>Record</span><strong>{data.record_source === "HISTORICAL" ? "Historical vendor" : "Registered vendor"}</strong></div>
          <div><span>Account</span><strong>{account[data.account_status] || "Not recorded"}</strong></div>
          <div><span>Source division</span><strong>{display(data.source_division)}</strong></div>
        </div>
        <section className="admin-zone-highlight">
          <div className="admin-zone-highlight-icon"><MapPin size={21}/></div>
          <div><span>RELATED VENDING ZONE</span>{related ? <><h3>{related.zone_id}</h3><strong>{zoneName(relatedZone || related.zone_id)}</strong><small>{related.source}</small></> : <><h3>Not yet linked</h3><small>No zone relationship is recorded yet.</small></>}</div>
          {data.active_allocation && <StatusBadge status={data.active_allocation.status}/>} 
        </section>
        <div className="admin-operational-summary">
          <div><Building2 size={17}/><span>Allocation</span><strong>{data.active_allocation ? "Active" : "Not allocated"}</strong></div>
          <div><CheckCircle2 size={17}/><span>Physical slot</span><strong>{data.assigned_slot ? data.assigned_slot.slot_id : "Not assigned"}</strong></div>
          {latestRequest && <div><span>Latest application</span><strong>{pretty(latestRequest.request_type)} · {pretty(latestRequest.status)}</strong><small>{when(latestRequest.created_at)}</small></div>}
        </div>
        {data.allocations?.length > 0
          ? <details className="service-disclosure admin-vendor-allocation-history"><summary>Allocation history ({data.allocations.length})</summary><div className="admin-vendor-allocation-list">{data.allocations.map(allocation => <article key={allocation.allocation_id}>
            <div className="admin-vendor-allocation-heading"><div><strong>{zoneName(allocation.zone_id)}</strong><small>{allocation.zone_id} · {allocation.allocation_id}</small></div><StatusBadge status={allocation.status}/></div>
            <dl><div><dt>Allocated</dt><dd>{when(allocation.allocated_at)}</dd></div>{allocation.released_at && <div><dt>Released</dt><dd>{when(allocation.released_at)}</dd></div>}
              <div><dt>Source</dt><dd>{allocation.allocation_source === "LEGACY_IMPORT" ? "Imported existing allocation" : "Admin-approved allocation"}</dd></div>
              <div><dt>Approved by</dt><dd>{allocation.allocation_source === "LEGACY_IMPORT" ? "Not individually approved" : allocation.approved_by || "Not recorded"}</dd></div>
              {allocation.request_id && <div><dt>Request</dt><dd>{allocation.request_id}</dd></div>}
            </dl>
          </article>)}</div></details>
          : <p className="admin-vendor-no-allocation-history">No allocation history recorded.</p>}
        {relevant && <section className="admin-selected-request"><div><span>Selected application</span><strong>{pretty(relevant.request_type)} · {relevant.zone_id}{relevant.slot_id ? ` / ${relevant.slot_id}` : ""}</strong><small>{relevant.request_id}</small></div><StatusBadge status={relevant.status}/>{relevant.status === "PENDING" && onDecision && <div><button className="admin-reject" onClick={() => onDecision("reject",relevant)}>Reject</button><button className="admin-approve" onClick={() => onDecision("approve",relevant)}>Approve</button></div>}</section>}
      </>}
      <footer className="admin-detail-footer"><button type="button" onClick={onClose}>Cancel</button>{data?.assigned_slot && <button className="admin-approve" type="button" onClick={() => onViewSlot(data.assigned_slot)}>View assigned slot</button>}</footer>
    </section>
  </div>;
}
