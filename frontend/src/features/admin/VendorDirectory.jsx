import React, {useEffect, useState} from "react";
import {Search} from "lucide-react";
import {getAdminVendors} from "../../services/api.js";
import VendorDetails from "./VendorDetails.jsx";
import DirectoryResults from "./DirectoryResults.jsx";
import {DataTable} from "./AdminPrimitives.jsx";
import {zoneName} from "../../shared/utils/displayLabels.js";
import {pretty} from "./viewModel.js";
import "./AdminDashboard.css";

const accountLabels = {PHONE_VERIFIED: "Phone verified", UNCLAIMED: "Not yet claimed", NO_LINKED_IDENTITY: "No linked login identity"};
export default function VendorDirectory({onViewSlot}) {
  const [filters, setFilters] = useState({q: "", business_category: "", division: "", zone_id: ""});
  const [page, setPage] = useState(1), [data, setData] = useState(null);
  const [loading, setLoading] = useState(true), [error, setError] = useState(""), [reload, setReload] = useState(0);
  const [selected, setSelected] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    const timer = setTimeout(() => {
      getAdminVendors({...filters, page, page_size: 25}, controller.signal).then(result => {
        if (!controller.signal.aborted) setData(result);
      }).catch(err => {if (!controller.signal.aborted) setError(err.message);}).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    }, 250);
    return () => {clearTimeout(timer); controller.abort();};
  }, [filters, page, reload]);
  const filter = (key, value) => {setPage(1); setFilters(current => ({...current, [key]: value}));};
  const name = vendor => vendor.full_name || vendor.business_name || "Name not recorded";
  const zones = data?.accepted_zones || [];
  const historicalZone = vendor => zones.find(zone => zone.zone_id === vendor.historical_association?.matched_zone_id);
  return <main className="admin-dashboard vendor-directory" aria-busy={loading}>
    <div className="admin-section-heading"><div><span className="admin-eyebrow">VENDOR DIRECTORY</span><h2>Vendors</h2><p>Historical records and registered profiles. Historical records do not establish current occupancy.</p></div><span className="admin-count">{data ? `${data.total.toLocaleString()} records` : "Loading records"}</span></div>
    <div className="admin-filters"><label className="admin-search"><Search size={16}/><input aria-label="Search vendors" placeholder="Search vendor ID or name" value={filters.q} onChange={event => filter("q", event.target.value)}/></label><select aria-label="Business category" value={filters.business_category} onChange={event => filter("business_category", event.target.value)}><option value="">All business categories</option>{data?.categories.map(category => <option key={category} value={category}>{pretty(category)}</option>)}</select><select aria-label="Source division" value={filters.division} onChange={event => filter("division", event.target.value)}><option value="">All source divisions</option>{data?.divisions.map(division => <option key={division}>{division}</option>)}</select><select aria-label="Accepted historical zone" value={filters.zone_id} onChange={event => filter("zone_id", event.target.value)}><option value="">All accepted historical zones</option>{zones.map(zone => <option key={zone.zone_id} value={zone.zone_id}>{zone.zone_id} · {zone.division || "Division not recorded"}</option>)}</select></div>
    {error && <div role="alert" className="hub-error">{error} <button onClick={() => setReload(value => value + 1)}>Retry</button></div>}
    {loading && <p role="status">Loading vendors...</p>}
    {!loading && !error && data && <><DirectoryResults vendors={data.vendors} onSelect={setSelected}/><details className="vm-directory-table"><summary>View full registry table</summary><DataTable><thead><tr><th>Vendor</th><th>Business category</th><th>Source division</th><th>Accepted historical zone</th><th>Operational allocation</th><th>Registration / account</th><th/></tr></thead><tbody>{data.vendors.map(vendor => {const mappedZone = historicalZone(vendor); return <tr key={vendor.vendor_id}><td><button className="vendor-directory-name" onClick={() => setSelected(vendor)}>{name(vendor)}</button><small className="admin-secondary-id">{vendor.application_vendor_id || vendor.vendor_id}</small></td><td>{pretty(vendor.business_category)}</td><td>{vendor.source_division || (vendor.record_source === "OPERATIONAL" ? "No historical source" : "Not recorded")}</td><td>{mappedZone ? <><strong>{mappedZone.zone_id}</strong><small className="admin-secondary-id">{zoneName(mappedZone)} · {mappedZone.division}</small></> : "Unresolved / not accepted"}</td><td>{vendor.active_allocation ? <><strong>{vendor.active_allocation.zone_id}</strong><small className="admin-secondary-id">{vendor.active_allocation.allocation_source === "LEGACY_IMPORT" ? "Imported existing allocation" : "Admin-approved allocation"}</small></> : "None"}</td><td>{vendor.registration_status === "PROFILE_REGISTERED" ? "Profile registered" : "Historical registry profile"}<small className="admin-secondary-id">{accountLabels[vendor.account_status] || "Not recorded"}</small></td><td><button className="row-detail" onClick={() => setSelected(vendor)}>Details</button></td></tr>;})}</tbody></DataTable></details>{!data.vendors.length && <p>No vendors match these filters.</p>}<nav className="vendor-directory-pagination" aria-label="Vendor directory pages"><button disabled={data.page <= 1} onClick={() => setPage(data.page - 1)}>Previous</button><span>Page {data.page} of {data.pages}</span><button disabled={data.page >= data.pages} onClick={() => setPage(data.page + 1)}>Next</button></nav></>}
    {selected && <VendorDetails vendorId={selected.vendor_id} zones={zones} onClose={() => setSelected(null)} onViewSlot={slot => {setSelected(null); onViewSlot(slot);}}/>}
  </main>;
}
