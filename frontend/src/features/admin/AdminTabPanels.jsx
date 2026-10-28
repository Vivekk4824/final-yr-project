import {zoneName, officialZoneDivision, zoneMapLocation} from "../../shared/utils/displayLabels.js";
import React, {useEffect, useMemo, useState} from "react";

import {ChevronLeft, ChevronRight, ClipboardList, Eye, Search, Users, X} from "lucide-react";

import {STATUS_COLORS, pretty, display, when} from "./viewModel.js";
import {PILOT_ZONE_IDS} from "../pilot-slots/pilotState.js";
import {AdminZoneMap, divisionFeatures, spatialDivisionZones} from "./AdminZoneMap.jsx";
import {StatusBadge, DataTable} from "./AdminPrimitives.jsx";

export function AdminHome({pending, allocationCounts, summaryCards, zoneCounts, setTab, setAllocationFilter, setZoneFilters}) {
  return <section className="service-home"><div className="admin-section-heading"><div><span className="admin-eyebrow">TODAY’S WORK</span><h2>Welcome, officer</h2><p>Review vendor applications and manage designated zones.</p></div></div><article className="service-action"><span className="admin-eyebrow">PENDING REVIEW</span><h3>{pending.length} allocation requests</h3><p>{pending.length ? "Applications are waiting for your decision." : "You’re up to date. New applications will appear here."}</p><button className="admin-approve" onClick={() => setTab("requests")}>Open pending requests <ChevronRight size={15}/></button></article><div className="service-quick-actions"><button onClick={() => setTab("map")}>Explore zones <ChevronRight size={15}/></button><button onClick={() => {setAllocationFilter("ACTIVE"); setTab("allocations");}}>Active allocations · {allocationCounts.ACTIVE ?? "Not recorded"} <ChevronRight size={15}/></button><button onClick={() => {setZoneFilters(current => ({...current, live_status: "FULL"})); setTab("zones");}}>Full zones · {zoneCounts.FULL ?? "Not recorded"} <ChevronRight size={15}/></button></div><details className="service-disclosure"><summary>Operational totals and status counts</summary><p>Historical associations are not counted as occupancy.</p><div className="admin-summary-grid">{summaryCards.map(([label,value,Icon,tone]) => <article className={`admin-summary-card ${tone}`} key={label}><div><span>{label}</span><strong>{value ?? "Not recorded"}</strong></div><Icon size={20}/></article>)}</div></details></section>;
}

export function PendingRequests({pending, zones, openRequest, setDialog}) {
  return <section className="admin-pending-requests">
    <div className="admin-section-heading">
      <div><span className="admin-eyebrow">OFFICER REVIEW</span><h2>Pending allocation requests</h2></div>
      <span className="admin-count">{pending.length} pending</span>
    </div>
    {pending.length === 0
      ? <div className="admin-empty"><ClipboardList size={28}/><h3>No pending requests</h3><p>New vendor submissions will appear here automatically.</p></div>
      : <DataTable className="requests-table">
        <thead><tr><th>Request</th><th>Vendor</th><th>Business</th><th>Type</th><th>Current zone</th><th>Selected zone</th><th>Division</th><th>Created</th><th>Target status</th><th>Operational available</th><th>Actions</th></tr></thead>
        <tbody>{pending.map(request => {
          const zone = zones.find(item => item.zone_id === request.zone_id);
          const currentZoneId = request.current_zone_id;
          const shortRequestId = request.request_id.length > 16
            ? `${request.request_id.slice(0, 12)}…`
            : request.request_id;
          return <tr key={request.request_id}>
            <td><strong className="request-short-id">{shortRequestId}</strong></td>
            <td><strong>{request.vendor_name || "Registered Vendor"}</strong><small className="admin-secondary-id">{request.application_vendor_id || request.vendor_id}</small></td>
            <td>{request.business_name || pretty(request.business_category)}</td>
            <td>{pretty(request.request_type)}</td>
            <td>{request.request_type === "RELOCATION" ? currentZoneId || "Not recorded" : "—"}</td>
            <td>{zoneName(zone || request.zone_id)}</td>
            <td>{request.preferred_division || "Not recorded"}</td>
            <td>{when(request.created_at)}</td>
            <td><StatusBadge status={zone?.live_status}/></td>
            <td>{display(zone?.operational_available)}</td>
            <td><div className="table-actions">
              <button onClick={() => openRequest({...request, current_zone_id: currentZoneId})}><Eye size={14}/> Details</button>
              <button className="approve" onClick={() => setDialog({type: "approve", ...request})}>Approve</button>
              <button className="reject" onClick={() => setDialog({type: "reject", ...request})}>Reject</button>
            </div></td>
          </tr>;
        })}</tbody>
      </DataTable>}
  </section>;
}

export function RequestReviewModal({request, zones, onClose}) {
  if (!request) return null;
  const targetZone = zones.find(zone => zone.zone_id === request.zone_id);
  const currentZoneId = request.current_zone_id;
  const requestCards = [
    {
      title: "Vendor",
      fields: [
        ["Name", request.vendor_name || "Registered Vendor"],
        ["Vendor ID", request.application_vendor_id || request.vendor_id],
        ["Business", request.business_name || pretty(request.business_category)],
      ],
    },
    {
      title: "Request",
      fields: [
        ["Request ID", request.request_id],
        ["Type", pretty(request.request_type)],
        ["Submitted", when(request.created_at)],
        ["Preferred division", request.preferred_division || "Not recorded"],
      ],
    },
    {
      title: "Zones",
      zones: true,
      fields: [
        ["Current zone", currentZoneId || "No active zone recorded", currentZoneId ? zoneName(zones.find(zone => zone.zone_id === currentZoneId) || currentZoneId) : "—"],
        ["Requested zone", request.zone_id, zoneName(targetZone || request.zone_id)],
      ],
    },
  ];
  return <div className="admin-modal-backdrop admin-request-backdrop" onClick={onClose}>
    <section className="admin-request-modal" role="dialog" aria-modal="true" aria-labelledby="request-review-title" onClick={event => event.stopPropagation()}>
      <button className="drawer-close" type="button" aria-label="Close request details" onClick={onClose}><X size={18}/></button>
      <span className="admin-eyebrow">REQUEST DETAILS</span>
      <h2 id="request-review-title">{request.vendor_name || "Allocation request"}</h2>
      <div className="admin-request-card-grid">
        {requestCards.map(card => <article className={`admin-request-card ${card.zones ? "zones-card" : ""}`} key={card.title}>
          <h3>{card.title}</h3>
          <div className="admin-request-fields">
            {card.fields.map(([label, value, detail]) => <div className={label === "Current zone" ? "current-zone" : ""} key={label}>
              <span>{label}</span>
              <strong title={label === "Request ID" ? request.request_id : undefined}>{value}</strong>
              {detail && <small>{detail}</small>}
            </div>)}
          </div>
        </article>)}
      </div>
      <div className="admin-request-modal-footer"><StatusBadge status={request.status}/><button className="vendor-secondary" type="button" onClick={onClose}>Close</button></div>
    </section>
  </div>;
}

export function ZoneManagement({filteredZones, zoneFilters, setZoneFilters, divisions, setSelectedZone}) {
  return <section>
    <div className="admin-section-heading">
      <div><span className="admin-eyebrow">OPERATIONAL REGISTRY</span><h2>Zone management</h2></div>
      <span className="admin-count">{filteredZones.length} zones</span>
    </div>
    <div className="admin-filters">
      <label className="admin-search"><Search size={15}/><input value={zoneFilters.q} onChange={event => setZoneFilters(current => ({...current, q: event.target.value}))} placeholder="Search zone ID or description"/></label>
      <details className="service-disclosure service-filters">
        <summary>Filters</summary>
        <div className="service-filter-fields">
          <select value={zoneFilters.division} onChange={event => setZoneFilters(current => ({...current, division: event.target.value}))}><option value="">All divisions</option>{divisions.map(item => <option key={item}>{item}</option>)}</select>
          <select value={zoneFilters.zone_type} onChange={event => setZoneFilters(current => ({...current, zone_type: event.target.value}))}><option value="">All zone types</option><option>FREE</option><option>RESTRICTED</option><option>NO_VENDING</option></select>
          <select value={zoneFilters.live_status} onChange={event => setZoneFilters(current => ({...current, live_status: event.target.value}))}><option value="">All live statuses</option>{Object.keys(STATUS_COLORS).map(item => <option key={item}>{item}</option>)}</select>
        </div>
      </details>
    </div>
    <DataTable className="zone-management-table">
      <thead><tr><th>Zone ID</th><th>Description</th><th>Division</th><th>Type</th><th>Listed capacity</th><th>Active vendors</th><th>Available</th><th>Historical planning</th><th>Planning load</th><th>Pressure</th><th aria-label="Details"/></tr></thead>
      <tbody>{filteredZones.map(zone => <tr key={zone.zone_id}>
        <td><strong>{zone.zone_id}</strong></td>
        <td className="description-cell">{zone.official_description || zoneName(zone)}</td>
        <td>{zone.division}</td>
        <td>{pretty(zone.zone_type)}</td>
        <td>{display(zone.listed_official_capacity)}</td>
        <td>{zone.operational_occupancy}</td>
        <td>{display(zone.operational_available)}</td>
        <td>{zone.historical_planning_count}</td>
        <td>{zone.planning_load}</td>
        <td><StatusBadge status={zone.capacity_pressure_status}/>{zone.planning_overcapacity > 0 && <small>{zone.planning_overcapacity} estimated over</small>}</td>
        <td><button className="row-detail" aria-label={`View ${zone.zone_id} details`} onClick={() => setSelectedZone(zone)}><ChevronRight size={16}/></button></td>
      </tr>)}</tbody>
    </DataTable>
  </section>;
}

export function AllocationRecords({filteredAllocations, allocationFilter, setAllocationFilter, setRequestDetail, zones, setSelectedZone, loading, loaded, error, onRetry, total, page, pageSize, onPageChange}) {
  const firstRecord = total ? page * pageSize + 1 : 0;
  const lastRecord = Math.min((page + 1) * pageSize, total);
  return <section>
    <div className="admin-section-heading">
      <div><span className="admin-eyebrow">CONFIRMED RECORDS</span><h2>Allocations</h2></div>
      <span className="admin-count">{loading || !loaded ? "Loading…" : `${firstRecord}–${lastRecord} of ${total} records`}</span>
    </div>
    <div className="admin-filters compact"><select value={allocationFilter} onChange={event => setAllocationFilter(event.target.value)}><option value="">All allocations</option><option>ACTIVE</option><option>RELEASED</option></select></div>
    {loading
      ? <div className="admin-empty" role="status"><Users size={28}/><h3>Loading allocations…</h3><p>Fetching allocated vendors and their zones.</p></div>
      : error
        ? <div className="admin-empty" role="alert"><Users size={28}/><h3>Allocations could not be loaded</h3><p>{error}</p><button className="row-detail" type="button" onClick={onRetry}>Retry</button></div>
        : !loaded
          ? <div className="admin-empty" role="status"><Users size={28}/><h3>Loading allocations…</h3><p>Fetching allocated vendors and their zones.</p></div>
      : filteredAllocations.length === 0
        ? <div className="admin-empty"><Users size={28}/><h3>No allocations found</h3><p>There are no allocation records for this filter.</p></div>
        : <>
          <DataTable><thead><tr><th>Allocation ID</th><th>Vendor</th><th>Zone</th><th>Status</th><th>Source</th><th>Allocated</th><th>Released</th><th>Approved by</th><th>Request</th><th>Links</th></tr></thead><tbody>{filteredAllocations.map(item => <tr key={item.allocation_id}>
            <td><strong>{item.allocation_id}</strong></td>
            <td><strong>{item.vendor_name || "Registered Vendor"}</strong><small className="admin-secondary-id">{item.vendor_type === "NEW" ? item.application_vendor_id || "Application ID pending" : item.vendor_id}</small></td>
            <td>{zoneName(item)}</td>
            <td><StatusBadge status={item.status}/></td>
            <td>{item.allocation_source === "LEGACY_IMPORT" ? "Imported existing allocation" : "Admin-approved allocation"}</td>
            <td>{when(item.allocated_at)}</td>
            <td>{when(item.released_at)}</td>
            <td>{item.allocation_source === "LEGACY_IMPORT" ? "Not individually approved" : item.approved_by || "Not recorded"}</td>
            <td>{item.request_id || "Not applicable"}</td>
            <td><div className="table-actions"><button onClick={() => setRequestDetail({vendor_id: item.vendor_id})}>Vendor</button><button onClick={() => setSelectedZone(zones.find(zone => zone.zone_id === item.zone_id))}>Zone</button></div></td>
          </tr>)}</tbody></DataTable>
          {total > pageSize && <nav className="allocation-pagination" aria-label="Allocation pages">
            <button type="button" className="row-detail" disabled={page === 0 || loading} onClick={() => onPageChange(page - 1)}><ChevronLeft size={15}/>Previous</button>
            <span>Page {page + 1} of {Math.ceil(total / pageSize)}</span>
            <button type="button" className="row-detail" disabled={(page + 1) * pageSize >= total || loading} onClick={() => onPageChange(page + 1)}>Next<ChevronRight size={15}/></button>
          </nav>}
        </>}
  </section>;
}

export function ZoneExplorer({zoneLoad, geometryError, onRetry, zones, zoneFilters, setZoneFilters, mapStatuses, setMapStatuses, geometry, setSelectedZone, division, setDivision, onPilot}) {
  const [referenceEnabled, setReferenceEnabled] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [sheetExpanded, setSheetExpanded] = useState(false);

  useEffect(() => {setSelectedId(null); setSheetExpanded(false);}, [division]);
  const divisionRecords = useMemo(() => spatialDivisionZones(zones, division, geometry, referenceEnabled), [zones, division, geometry, referenceEnabled]);
  const records = useMemo(() => divisionRecords.filter(zone => (!zoneFilters.q || `${zoneName(zone)} ${zone.zone_id} ${zone.official_description || ""}`.toLowerCase().includes(zoneFilters.q.toLowerCase()))
    && (!zoneFilters.zone_type || zone.zone_type === zoneFilters.zone_type)
    && (!zone.live_status || mapStatuses.includes(zone.live_status))), [divisionRecords, zoneFilters.q, zoneFilters.zone_type, mapStatuses]);
  const selected = zones.find(zone => zone.zone_id === selectedId);
  const selectZone = zone => {setSelectedId(zone.zone_id); setSheetExpanded(true);};
  const citywide = zones.filter(zone => officialZoneDivision(zone) === "Citywide" && zone.zone_type === "NO_VENDING");
  if (!zoneLoad.ready || zoneLoad.error) return <section className="admin-division-explorer"><h2>Zone Explorer</h2><p role={zoneLoad.error ? "alert" : "status"}>{zoneLoad.error || "Loading official zone records..."}</p>{zoneLoad.error && <button onClick={onRetry} disabled={zoneLoad.loading}>Retry loading zones</button>}</section>;
  const showAllZones = () => {
    setZoneFilters(current => ({...current, q: "", zone_type: ""}));
    setMapStatuses(Object.keys(STATUS_COLORS));
    setDivision("");
  };
  return <section className="admin-division-explorer">
    <div className="admin-section-heading">
      <div>{division && <button type="button" className="admin-explorer-back" onClick={showAllZones}><ChevronLeft size={16}/>All zones map</button>}<h2>{division || "Choose a division"}</h2><p>{division ? `${records.length} zones` : "Select a division on the map to browse its zones."}</p></div>
    </div>

    {zoneLoad.loading && <p role="status">Refreshing official records...</p>}
    {geometryError && <p role="alert">{geometryError}</p>}
    {!division && <div className="admin-division-buttons">{divisionFeatures.map(feature => <button key={feature.properties.division_id} onClick={() => setDivision(feature.properties.division)}><i style={{background: feature.properties.display_color}}/>{feature.properties.name}<small>{spatialDivisionZones(zones, feature.properties.division, geometry, referenceEnabled).length} zones</small></button>)}</div>}
    <div className={`admin-zone-workspace ${division ? "has-division" : ""}`}>
      <AdminZoneMap zones={records} geometry={geometry} onZone={selectZone} selectedZoneId={selected?.zone_id} referenceEnabled={referenceEnabled} onReferenceChange={setReferenceEnabled} division={division} onDivision={setDivision}/>
      {division && <aside className={`admin-zone-browser ${sheetExpanded ? "expanded" : ""}`} aria-label="Division zones">
        <button className="admin-zone-sheet-toggle" onClick={() => setSheetExpanded(value => !value)} aria-expanded={sheetExpanded}><span className="admin-zone-sheet-title">{division}</span><span>{sheetExpanded ? "Hide list" : `${records.length} zones · Browse`}</span></button>
        <div className="admin-zone-browser-content">
          <label className="admin-search"><Search size={15}/><input aria-label="Search division zones" value={zoneFilters.q} onChange={event => setZoneFilters(current => ({...current, q: event.target.value}))} placeholder="Search zones"/></label>
          <select aria-label="Zone type" value={zoneFilters.zone_type} onChange={event => setZoneFilters(current => ({...current, zone_type: event.target.value}))}><option value="">All zone types</option><option value="FREE">Free vending</option><option value="RESTRICTED">Restricted vending</option><option value="NO_VENDING">No vending</option></select>
          <details className="service-disclosure admin-zone-status-filter"><summary>Status filters</summary><div className="map-status-filters">{Object.keys(STATUS_COLORS).map(status => <label key={status}><input type="checkbox" checked={mapStatuses.includes(status)} onChange={() => setMapStatuses(current => current.includes(status) ? current.filter(item => item !== status) : [...current, status])}/>{pretty(status)}</label>)}</div></details>
          {selected && <article className="admin-zone-selection" aria-live="polite">
            <div className="admin-zone-selection-heading"><span>{selected.zone_id}</span><StatusBadge status={selected.live_status}/></div>
            <h3>{zoneName(selected)}</h3>
            <div className="admin-zone-quick-facts">
              <span>{pretty(selected.zone_type)}</span>
              <span>{display(selected.operational_available)} available</span>
              <span>{display(selected.operational_occupancy)} allocated</span>
            </div>
            <p className="admin-zone-map-note">{zoneMapLocation(selected).coordinates ? "Map pin is an approximate reference, not a confirmed vending spot." : "No map location is available for this zone."}</p>
            {officialZoneDivision(selected) !== division && <p className="admin-zone-map-note">Officially listed in {officialZoneDivision(selected)}; shown here for map browsing.</p>}
            <div className="admin-zone-selection-actions"><button onClick={() => setSelectedZone(selected)}>Zone details</button><button onClick={() => onPilot(selected)}>Slot map</button></div>
          </article>}
          <div className="admin-zone-record-list">{records.map(zone => <button key={zone.zone_id} className={`${selected?.zone_id === zone.zone_id ? "selected" : ""} ${PILOT_ZONE_IDS.includes(zone.zone_id) ? "pilot" : ""}`} aria-pressed={selected?.zone_id === zone.zone_id} onClick={() => selectZone(zone)}>
            <span className="admin-zone-list-title"><strong>{zone.zone_id}</strong><i style={{background: STATUS_COLORS[zone.live_status] || "#64748b"}} aria-label={pretty(zone.live_status)} title={pretty(zone.live_status)}/></span>
            <small>{zoneName(zone)}</small>
            <small>{pretty(zone.zone_type)} · {display(zone.operational_available)} available</small>
          </button>)}</div>
          {!records.length && <p className="admin-zone-no-results">No zones match these filters.</p>}
          {(zoneFilters.q || zoneFilters.zone_type || mapStatuses.length !== Object.keys(STATUS_COLORS).length) && <button className="admin-zone-clear-filters" onClick={() => {setZoneFilters(current => ({...current, q: "", zone_type: ""})); setMapStatuses(Object.keys(STATUS_COLORS));}}>Clear filters</button>}
        </div>
      </aside>}
    </div>
    <details className="service-disclosure admin-citywide-zones"><summary>Citywide no-vending zones ({citywide.length})</summary><div className="admin-zone-record-list">{citywide.map(zone => <button key={zone.zone_id} onClick={() => setSelectedZone(zone)}><strong>{zone.zone_id}</strong><small>{zoneName(zone)}</small></button>)}</div></details>
  </section>;
}
