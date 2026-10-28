import React, {useEffect, useState} from "react";
import {ArrowUpRight, MapPin, RefreshCw} from "lucide-react";
import {getCapacityPressure, getZoneHistoricalVendors} from "../../services/api.js";
import VendorDetails from "./VendorDetails.jsx";
import {display} from "./viewModel.js";

export default function RelocationPlanning({onViewSlot}) {
  const [data, setData] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [zone, setZone] = useState(null), [vendors, setVendors] = useState(null), [selected, setSelected] = useState(null);
  const refresh = async () => {setBusy(true); setError(""); try {setData(await getCapacityPressure());} catch (err) {setError(err.message);} finally {setBusy(false);}};
  useEffect(() => {refresh();}, []);
  const review = async item => {setZone(item); setVendors(null); setBusy(true); setError(""); try {setVendors(await getZoneHistoricalVendors(item.zone_id));} catch (err) {setError(err.message);} finally {setBusy(false);}};
  const pressure = (data?.zones || []).filter(item => item.planning_overcapacity > 0 || item.near_planning_capacity);
  return <main className="admin-dashboard vm-planning"><header className="admin-header"><div><span className="admin-eyebrow">PLAN WITH CARE</span><h1>Room to move forward.</h1><p>Review estimated capacity pressure, then explore alternatives for an individual vendor.</p></div><button className="vm-refresh" onClick={refresh} disabled={busy}><RefreshCw size={16}/>Refresh</button></header>
    <p className="vm-planning-notice">Historical planning load is separate from current occupancy. Alternatives are read-only; no vendor is moved automatically.</p>
    {error && <p role="alert">{error}</p>}{busy && <p role="status">Loading planning evidence…</p>}
    {!busy && data && !pressure.length && <div className="admin-empty"><MapPin size={28}/><h2>No capacity pressure flagged</h2><p>You can still review relocation alternatives in an allocated vendor’s directory record.</p></div>}
    <div className="vm-planning-zones">{pressure.map(item => <article key={item.zone_id}><span className="admin-eyebrow">{item.division}</span><h2>{item.zone_id}</h2><p>{item.official_description}</p><dl><div><dt>Current occupancy</dt><dd>{display(item.operational_occupancy)}</dd></div><div><dt>Historical planning load</dt><dd>{display(item.planning_load)}</dd></div><div><dt>Estimated overcapacity</dt><dd>{display(item.planning_overcapacity)}</dd></div></dl><button className="vendor-secondary" onClick={() => review(item)} disabled={busy}>Review associated vendors<ArrowUpRight size={16}/></button></article>)}</div>
    {zone && vendors && <section className="vm-planning-vendors"><h2>Historical associations · {zone.zone_id}</h2><p>{vendors.notice}</p>{vendors.vendors.map(vendor => <button key={vendor.vendor_id} onClick={() => setSelected(vendor.vendor_id)}><span><strong>{vendor.full_name || vendor.vendor_id}</strong><small>{vendor.vendor_id}</small></span><span>Review alternatives <ArrowUpRight size={16}/></span></button>)}{!vendors.vendors.length && <p>No accepted historical associations for this zone.</p>}</section>}
    {selected && <VendorDetails vendorId={selected} onClose={() => setSelected(null)} onViewSlot={onViewSlot} zones={data?.zones || []}/>}
  </main>;
}
