import React, {useEffect, useMemo, useRef, useState} from "react";
import {CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap} from "react-leaflet";
import L from "leaflet";
import {ArrowLeft, List, Map as MapIcon, MapPin, Search} from "lucide-react";
import {getZoneDisplayGeometry} from "../../services/api.js";
import {buildVendorExplorerMapModel, uniqueMapPositions, vendorVisibleContextZones} from "../../shared/utils/mapGrouping.js";
import {zoneDescription} from "../../shared/utils/displayLabels.js";
import {useI18n} from "../../i18n/react.jsx";
import {statusLabel} from "../../i18n/index.js";
import {RANK_COLORS, score, displayCapacity, suitableZoneSections} from "./viewModel.js";

export function MapFocus({groups, selectedId, markerRefs, viewportKey, focusToken = 0}) {
  const map = useMap();
  const previousSelection = useRef(selectedId);
  const previousFocus = useRef(focusToken);
  const previousViewport = useRef(viewportKey);
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize({pan:false});
      const positions = uniqueMapPositions(groups);
      if (!positions.length) return;
      if (positions.length === 1) map.setView(positions[0], 14, {animate:false});
      else map.fitBounds(L.latLngBounds(positions), {padding:[30,30], maxZoom:14, animate:false});
    }, 0);
    return () => clearTimeout(timer);
  }, [map, groups, viewportKey]);
  useEffect(() => {
    const revealSelection = focusToken > 0 && viewportKey === "map" && previousViewport.current !== viewportKey;
    previousViewport.current = viewportKey;
    if (previousSelection.current === selectedId && previousFocus.current === focusToken && !revealSelection) return;
    previousSelection.current = selectedId;
    previousFocus.current = focusToken;
    const selected = groups.find(group => group.zones.some(zone => zone.zone_id === selectedId));
    if (selected) {
      const timer = setTimeout(() => {
        map.invalidateSize({pan:false});
        map.flyTo(selected.position, Math.max(map.getZoom(),14), {duration:.3});
        markerRefs.current.get(selected.key)?.openPopup();
      },0);
      return () => clearTimeout(timer);
    }
  }, [map, groups, selectedId, markerRefs, focusToken, viewportKey]);
  return null;
}

function ZoneMap({recommendations, zones, selectedId, onFocus, viewportKey, focusToken, onGeometryStatus, onDetails, onRequest, busy}) {
  const {language,t} = useI18n();
  const [geometry,setGeometry] = useState(null);
  const [error,setError] = useState("");
  const markerRefs = useRef(new Map());
  useEffect(() => {
    let active = true;
    getZoneDisplayGeometry().then(data => {if (active) setGeometry(data);}).catch(err => {if (active) setError(err.message);});
    return () => {active = false;};
  }, []);
  const model = useMemo(() => geometry ? buildVendorExplorerMapModel(recommendations,zones,geometry)
    : {groups:[], unavailableZoneIds:[], representedZoneCount:0}, [recommendations,zones,geometry]);
  useEffect(() => {onGeometryStatus?.(geometry ? model.unavailableZoneIds : null);}, [geometry,model.unavailableZoneIds,onGeometryStatus]);
  if (error) return <div className="explorer-map-state" role="alert"><MapPin size={24}/><p>{t("recommend.mapError",{message:error})}</p></div>;
  if (!geometry) return <div className="explorer-map-state" role="status">{t("common.loading")}</div>;
  return <MapContainer center={[19.9975,73.7898]} zoom={12} scrollWheelZoom className="explorer-leaflet">
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
    <MapFocus groups={model.groups} selectedId={selectedId} markerRefs={markerRefs} viewportKey={viewportKey} focusToken={focusToken}/>
    {model.groups.map(group => {
      const selected = group.zones.some(zone => zone.zone_id === selectedId);
      const top = group.zones.find(zone => zone.is_recommendation);
      const selectedZone = group.zones.find(zone => zone.zone_id === selectedId) || group.zones[0];
      return <CircleMarker key={group.key} ref={marker => {if (marker) markerRefs.current.set(group.key,marker); else markerRefs.current.delete(group.key);}}
        center={group.position} radius={selected ? 12 : top ? 9 : group.shared ? 7 : 5}
        eventHandlers={{click:() => onFocus((group.zones.find(zone => zone.zone_id === selectedId) || group.zones[0]).zone_id)}}
        pathOptions={{color:selected ? "#173c4e" : "#fff",weight:selected ? 3 : 1.5,fillColor:top ? RANK_COLORS[top.rank] : "#087f72",fillOpacity:top || selected ? .95 : .65}}>
        <Tooltip permanent={Boolean(top)} direction={top ? "center" : "top"} className={top ? "rank-tooltip" : undefined}>
          {top ? top.rank : group.shared ? t("explorer.sharedCount",{count:group.zones.length}) : group.zones[0].zone_id}
        </Tooltip>
        <Popup className="shared-reference-popup" minWidth={250}>
          <strong>{group.shared ? t("explorer.sharedCount",{count:group.zones.length}) : group.zones[0].zone_id}</strong>
          <div className="shared-zone-list">{group.zones.map(zone => <button key={zone.zone_id} onClick={() => onFocus(zone.zone_id)}>
            <b>{zone.rank ? "#" + zone.rank : ""}</b><span>{zone.zone_id}<small>{zone.zone_division}</small></span>
            <em>{zone.score == null ? statusLabel(language,zone.live_status) : score(zone.personalized_score ?? zone.score)}</em>
          </button>)}</div>
          <p>{zoneDescription(selectedZone,t("common.notRecorded"))}</p>
          <p>{statusLabel(language,selectedZone.live_status)} · {t("explorer.available",{count:displayCapacity(selectedZone.available_capacity,t)})}</p>
          {onDetails && <div className="explorer-popup-actions"><button onClick={() => onDetails(selectedZone.zone_id)}>{t("explorer.details")}</button><button disabled={busy || selectedZone.eligible === false || selectedZone.live_status !== "OPEN" || (selectedZone.available_capacity != null && selectedZone.available_capacity <= 0)} onClick={() => onRequest(selectedZone)}>{t("explorer.request")}</button></div>}
        </Popup>
      </CircleMarker>;
    })}
  </MapContainer>;
}

export function RecommendationMap({recommendations,context,selectedId,onFocus,onGeometryStatus,onExplore}) {
  const {t} = useI18n();
  const zones = useMemo(() => vendorVisibleContextZones(context),[context]);
  return <div className="vendor-map-wrap recommendation-map-preview" id="vendor-recommendation-map">
    <div className="vendor-map-toolbar"><div><strong>{t("recommend.mapTitle")}</strong><span>{t("recommend.recommendationsHelp")}</span></div>
      <button className="vendor-secondary" onClick={onExplore}>{t("recommend.viewAllZones")}</button></div>
    <ZoneMap recommendations={recommendations} zones={zones} selectedId={selectedId} onFocus={onFocus} onGeometryStatus={onGeometryStatus}/>
    <p className="recommendation-map-caption">{t("map.manualNotice")}</p>
  </div>;
}

function ZoneCard({zone,selected,onFocus,onDetails,onRequest,busy,hasLocation}) {
  const {language,t} = useI18n();
  const canRequest = zone.eligible !== false && zone.live_status === "OPEN" && (zone.available_capacity == null || zone.available_capacity > 0);
  return <article className={"explorer-zone-card" + (selected ? " selected" : "")} data-zone-id={zone.zone_id}>
    <button className="explorer-zone-select" aria-pressed={selected} onClick={() => onFocus(zone.zone_id)}>
      <div className="explorer-zone-heading"><div className="explorer-zone-title">
        {zone.rank != null && <span className={"explorer-rank" + (zone.is_top_three ? " top-three" : "")}>#{zone.rank}</span>}
        <h3>{zone.zone_id}</h3>{zone.is_top_three && <small className="explorer-top-label">{t("recommend.topLegend")}</small>}
      </div><strong className="explorer-score">{zone.score == null ? t("explorer.notScored") : score(zone.personalized_score ?? zone.score)}{zone.score != null && <small>/100</small>}</strong></div>
      <p className="explorer-zone-description">{zoneDescription(zone,t("common.notRecorded"))}</p>
      <div className="explorer-zone-meta"><span>{zone.zone_division}</span><span>{statusLabel(language,zone.live_status)}</span><span>{t("explorer.available",{count:displayCapacity(zone.available_capacity,t)})}</span></div>
      {!hasLocation && <span className="explorer-location-note"><MapPin size={13}/>{t("recommend.mapUnavailable")}</span>}
    </button>
    <div className="explorer-zone-actions"><button className="vendor-secondary" onClick={() => onDetails(zone.zone_id)}>{t("explorer.details")}</button>
      <button className="vendor-primary" disabled={busy || !canRequest} onClick={() => onRequest(zone)}>{t("explorer.request")}</button></div>
  </article>;
}

export function ZoneExplorer({data,context,selectedId,onFocus,onDetails,onRequest,onBack,busy}) {
  const {t} = useI18n();
  const [search,setSearch] = useState(""),[division,setDivision] = useState(""),[availability,setAvailability] = useState("");
  const [mobileView,setMobileView] = useState("list");
  const [focusToken,setFocusToken] = useState(0);
  const selectZone = id => {setFocusToken(current => current + 1); onFocus(id);};
  const listRef = useRef(null);
  const [unavailable,setUnavailable] = useState(null);
  const handleGeometryStatus = React.useCallback(ids => setUnavailable(ids ? new Set(ids) : null),[]);
  const filters = useMemo(() => ({search,division,availability}),[search,division,availability]);
  const sections = useMemo(() => suitableZoneSections(data,filters),[data,filters]);
  const allSections = useMemo(() => suitableZoneSections(data),[data]);
  const byId = useMemo(() => new Map((context.zones || []).map(zone => [zone.zone_id,zone])),[context]);
  const visibleZones = useMemo(() => [...sections.scored,...sections.unscored].map(zone => ({...byId.get(zone.zone_id),...zone})),[sections,byId]);
  const divisions = useMemo(() => [...new Set([...allSections.scored,...allSections.unscored].map(zone => zone.zone_division).filter(Boolean))].sort(),[allSections]);
  // Only the filtered Top 3 are passed as highlighted markers; filtering never changes ranks.
  const top = useMemo(() => visibleZones.filter(zone => zone.is_top_three),[visibleZones]);
  useEffect(() => {
    const card = [...(listRef.current?.querySelectorAll("[data-zone-id]") || [])].find(element => element.dataset.zoneId === selectedId);
    if (card && listRef.current) {
      const container = listRef.current.getBoundingClientRect(), bounds = card.getBoundingClientRect();
      if (bounds.top < container.top || bounds.bottom > container.bottom) listRef.current.scrollTop += bounds.top - container.top - 12;
    }
  }, [selectedId,mobileView]);
  const card = zone => <ZoneCard key={zone.zone_id} zone={{...byId.get(zone.zone_id),...zone}} selected={zone.zone_id === selectedId}
    onFocus={selectZone} onDetails={onDetails} onRequest={onRequest} busy={busy} hasLocation={zone.resolved_location ? Boolean(zone.resolved_location.coordinates) : unavailable == null || !unavailable.has(zone.zone_id)}/>;
  return <section className="vendor-zone-explorer" data-mobile-view={mobileView} aria-label={t("explorer.title")}>
    <header className="explorer-heading"><div><button className="vendor-back" onClick={onBack}><ArrowLeft size={16}/>{t("explorer.back")}</button><h2>{t("explorer.title")}</h2><p>{t("explorer.counts",{scored:allSections.totalScored,unscored:allSections.totalUnscored})}</p></div></header>
    <div className="explorer-controls"><label className="explorer-search"><Search size={17}/><input type="search" value={search} onChange={event => setSearch(event.target.value)} aria-label={t("explorer.search")} placeholder={t("explorer.search")}/></label>
      <label><span>{t("common.division")}</span><select value={division} onChange={event => setDivision(event.target.value)}><option value="">{t("common.anyDivision")}</option>{divisions.map(name => <option key={name} value={name}>{name}</option>)}</select></label>
      <label><span>{t("explorer.availability")}</span><select value={availability} onChange={event => setAvailability(event.target.value)}><option value="">{t("explorer.allAvailability")}</option><option value="OPEN">{t("explorer.open")}</option><option value="KNOWN_CAPACITY">{t("explorer.knownCapacity")}</option><option value="UNKNOWN_CAPACITY">{t("explorer.unknownCapacity")}</option></select></label>
      <div className="explorer-mobile-toggle" role="group" aria-label={t("explorer.view")}><button aria-pressed={mobileView === "list"} onClick={() => setMobileView("list")}><List size={16}/>{t("explorer.list")}</button><button aria-pressed={mobileView === "map"} onClick={() => setMobileView("map")}><MapIcon size={16}/>{t("explorer.map")}</button></div>
    </div>
    <div className="explorer-body">
      <div className="explorer-list" ref={listRef} aria-label={t("explorer.ranked")}><div className="explorer-section-heading">{t("explorer.ranked")} <span>{sections.scored.length}</span></div>
        {sections.scored.map(card)}
        {sections.unscored.length > 0 && <><div className="explorer-section-heading unscored-heading">{t("explorer.unscored")} <span>{sections.unscored.length}</span></div><p className="explorer-unscored-note">{t("explorer.unscoredHelp")}</p>{sections.unscored.map(card)}</>}
        {!visibleZones.length && <p className="explorer-empty">{t("explorer.noMatches")}</p>}
      </div>
      <div className="explorer-map"><ZoneMap recommendations={top} zones={visibleZones} selectedId={selectedId} onFocus={selectZone} viewportKey={mobileView} focusToken={focusToken} onGeometryStatus={handleGeometryStatus} onDetails={onDetails} onRequest={onRequest} busy={busy}/>
        <div className="explorer-map-key"><span><i/>{t("explorer.availableMarker")}</span><span><i className="top-three"/>{t("recommend.topLegend")}</span></div></div>
    </div>
    <footer className="explorer-footer"><MapPin size={14}/><span>{t("map.manualNotice")} {t("explorer.missingLocations")}</span></footer>
  </section>;
}
