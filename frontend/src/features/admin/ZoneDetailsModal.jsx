import React from "react";
import {Building2, MapPin, X} from "lucide-react";

import {zoneName} from "../../shared/utils/displayLabels.js";
import {StatusBadge} from "./AdminPrimitives.jsx";
import {display, pretty} from "./viewModel.js";

export default function ZoneDetailsModal({zone,pendingCount=0,loading=false,onClose,onOpenMap,onChangeStatus}) {
  if (!zone) return null;
  return <div className="admin-detail-backdrop" onClick={onClose}>
    <section className="admin-detail-modal zone-detail-modal" role="dialog" aria-modal="true" aria-labelledby="zone-detail-title" onClick={event => event.stopPropagation()}>
      <button className="admin-detail-close" type="button" aria-label="Close zone details" onClick={onClose}><X size={19}/></button>
      <span className="admin-eyebrow">ZONE DETAILS</span>
      <div className="zone-detail-heading"><div><h2 id="zone-detail-title">{zone.zone_id}</h2><p>{zoneName(zone)}</p></div><StatusBadge status={zone.live_status}/></div>
      <div className="zone-detail-description"><MapPin size={18}/><span>{zone.official_description || zoneName(zone)}</span></div>
      <div className="admin-key-facts zone-key-facts">
        <div><span>Division</span><strong>{zone.division}</strong></div>
        <div><span>Vending type</span><strong>{pretty(zone.zone_type)}</strong></div>
        <div className="emphasis"><span>Active vendors</span><strong>{display(zone.operational_occupancy)}</strong></div>
        <div className="emphasis"><span>Available places</span><strong>{display(zone.operational_available)}</strong></div>
        <div><span>Listed capacity</span><strong>{display(zone.listed_official_capacity)}</strong></div>
        <div><span>Pending requests</span><strong>{pendingCount}</strong></div>
      </div>
      {zone.zone_type !== "FREE" && <div className="zone-policy-note"><Building2 size={17}/><span>This zone’s status is controlled by municipal policy.</span></div>}
      <footer className="admin-detail-footer zone-detail-actions">
        <button type="button" onClick={onClose}>Cancel</button>
        {zone.zone_type === "FREE" && zone.live_status !== "OPEN" && <button type="button" disabled={loading} onClick={() => onChangeStatus("OPEN")}>Reopen zone</button>}
        {zone.zone_type === "FREE" && zone.live_status === "OPEN" && <button type="button" disabled={loading} onClick={() => onChangeStatus("SUSPENDED")}>Suspend</button>}
        <button className="admin-approve" type="button" onClick={onOpenMap}>View slot map</button>
      </footer>
    </section>
  </div>;
}
