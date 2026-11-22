import React, {useEffect, useMemo, useState} from "react";
import {Circle, CircleMarker, MapContainer, Popup, Tooltip, useMap} from "react-leaflet";
import {Flame, MapPin, RefreshCw} from "lucide-react";
import {categoryLabel, formatNumber} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";
import {Basemap, hasSatelliteTiles, HeatLayer} from "../../shared/maps/HeatmapLayers.jsx";
import {getVendorLocationInsights} from "../../services/api.js";
import "./LocationInsights.css";

const CITY_CENTER = [19.9975, 73.7898];
const RADII = [100, 250, 500];
const competitionColor = count => count === 0 ? "#2563eb"
  : count <= 2 ? "#16a34a"
    : count <= 5 ? "#fde047"
      : count <= 10 ? "#f97316" : "#dc2626";

function MapExtent({zones}) {
  const map = useMap();
  useEffect(() => {
    const positions = zones
      .filter(zone => Array.isArray(zone.coordinates) && zone.coordinates.length === 2)
      .map(zone => [zone.coordinates[1], zone.coordinates[0]]);
    if (positions.length === 1) map.setView(positions[0], 14, {animate: false});
    else if (positions.length > 1) map.fitBounds(positions, {padding: [35, 35], maxZoom: 14, animate: false});
  }, [map, zones]);
  return null;
}

function WeightedHeatLayer({cells}) {
  const maximum = Math.max(1, ...cells.map(cell => cell.count));
  const weightForPoint = useMemo(() => point => Math.max(0.25, point.count / maximum), [maximum]);
  return <HeatLayer points={cells} weightForPoint={weightForPoint}/>;
}

const formatCount = (language, value, t) => value == null
  ? t("insights.unavailable")
  : `${formatNumber(language, value)} recorded`;

export default function LocationInsights({
  recommendations = [],
  recommendationData,
  businessCategory,
  onRefresh,
  busy = false,
  pendingRequest = false,
}) {
  const {language, t} = useI18n();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshToken, setRefreshToken] = useState(0);
  const [view, setView] = useState("competition");
  const [satelliteFailed, setSatelliteFailed] = useState(false);
  const recommendedZones = useMemo(() => recommendations.slice(0, 3), [recommendations]);
  const zoneIds = recommendedZones.map(zone => zone.zone_id);
  const zoneIdsKey = zoneIds.join(",");
  const zoneStats = useMemo(
    () => new Map((data?.recommended_zones || []).map(zone => [zone.zone_id, zone])),
    [data?.recommended_zones],
  );
  const comparedZones = useMemo(() => recommendedZones.map(zone => ({
    ...zone,
    ...(zoneStats.get(zone.zone_id) || {}),
  })), [recommendedZones, zoneStats]);
  const cells = data?.heatmap?.cells || [];
  const hasZoneCounts = comparedZones.some(zone =>
    zone.counts_status === "AVAILABLE" && zone.nearby_same_category?.["500m"] != null
  );
  const satelliteAvailable = hasSatelliteTiles && !satelliteFailed;
  const satelliteActive = view === "satellite" && satelliteAvailable;

  useEffect(() => {
    if (businessCategory === undefined) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getVendorLocationInsights(zoneIds, controller.signal)
      .then(result => {if (!controller.signal.aborted) setData(result);})
      .catch(failure => {if (!controller.signal.aborted) setError(failure.message);})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [businessCategory, zoneIdsKey, refreshToken]);

  const refresh = () => {
    if ((!recommendationData || !recommendedZones.length) && !pendingRequest) onRefresh?.({navigate: false});
    setRefreshToken(value => value + 1);
  };
  const satelliteFailure = () => {
    if (!satelliteFailed) {
      setSatelliteFailed(true);
      setView("street");
    }
  };
  const heatmapMessage = data?.heatmap?.status === "NO_DATA"
    ? t("insights.noCategoryData")
    : data?.heatmap?.status === "NO_MAPPED_COORDINATES"
      ? t("insights.noCoordinates")
      : data?.heatmap?.status === "INSUFFICIENT_AGGREGATION"
        ? t("insights.sparseData")
        : "";

  return <section className="vendor-location-insights">
    <header className="insights-heading">
      <div><span className="vendor-eyebrow">{t("insights.kicker")}</span><h1>{t("insights.title")}</h1>
        <p>{t("insights.intro", {category: categoryLabel(language, data?.business_category || businessCategory)})}</p>
      </div>
      <button className="vendor-secondary" type="button" onClick={refresh} disabled={loading || busy}>
        <RefreshCw size={15}/>{t("common.refresh")}
      </button>
    </header>

    {error && <div className="insights-message error" role="alert">{error}</div>}
    {loading && !data && <p role="status">{t("common.loading")}</p>}
    {data && <>
      <div className="insights-coverage" role="status">
        <strong>{t("insights.coverage", {
          mapped: data.coverage.status === "NO_CATEGORY" ? t("insights.unavailable") : formatNumber(language, data.coverage.mapped_records ?? 0),
          total: data.coverage.status === "NO_CATEGORY" ? t("insights.unavailable") : formatNumber(language, data.coverage.total_records ?? 0),
        })}</strong>
        <span>{data.coverage.status === "NO_CATEGORY" ? t("insights.categoryMissing")
          : data.coverage.status === "PARTIAL" ? t("insights.partialCoverage", {
          count: formatNumber(language, data.coverage.unmapped_records),
        }) : data.coverage.status === "NO_DATA" || data.coverage.status === "NO_MAPPED_COORDINATES"
          ? t("insights.coverageUnavailable") : t("insights.aggregateOnly")}</span>
      </div>

      <div className="insights-map-shell">
        <div className="insights-map-controls" role="group" aria-label={t("insights.mapViews")}>
          <button type="button" aria-pressed={view === "satellite" && satelliteAvailable} disabled={!satelliteAvailable}
            title={!hasSatelliteTiles ? t("insights.satelliteUnavailable") : satelliteFailed ? t("insights.satelliteFailed") : ""}
            onClick={() => setView("satellite")}>{t("insights.satellite")}</button>
          <button type="button" aria-pressed={view === "street"} onClick={() => setView("street")}>{t("insights.street")}</button>
          <button type="button" aria-pressed={view === "competition"} onClick={() => setView("competition")}>{t("insights.competitionHeatmap")}</button>
        </div>
        <MapContainer center={CITY_CENTER} zoom={12} maxZoom={22} preferCanvas className="insights-map">
          <Basemap satellite={satelliteActive} onFailure={satelliteFailure}/>
          <MapExtent zones={comparedZones}/>
          {view === "competition" && cells.length > 0 && <WeightedHeatLayer cells={cells}/>}
          {view === "competition" && comparedZones.map(zone => {
            const count = zone.nearby_same_category?.["500m"];
            if (!Array.isArray(zone.coordinates) || zone.counts_status !== "AVAILABLE" || count == null) return null;
            const color = competitionColor(count);
            return <Circle key={`${zone.zone_id}-competition`} center={[zone.coordinates[1], zone.coordinates[0]]}
              radius={500} pathOptions={{color, weight: 1.5, opacity: 0.85, fillColor: color,
                fillOpacity: count === 0 ? 0.18 : 0.24 + Math.min(count / 20, 1) * 0.2}}/>;
          })}
          {comparedZones.map(zone => {
            if (!Array.isArray(zone.coordinates)) return null;
            const center = [zone.coordinates[1], zone.coordinates[0]];
            const count = zone.nearby_same_category?.["500m"];
            const hasCompetitionCount = view === "competition" && zone.counts_status === "AVAILABLE" && count != null;
            const markerColor = hasCompetitionCount ? competitionColor(count) : "#0b6c64";
            return <CircleMarker key={zone.zone_id} center={center} radius={8}
              pathOptions={{color: "#fff", weight: 2, fillColor: markerColor, fillOpacity: 0.95}}>
              <Tooltip>{zone.zone_id}</Tooltip>
              <Popup><strong>{zone.zone_id}</strong><p>{t("insights.sameCategory")} · 500 m: {formatCount(language, zone.nearby_same_category?.["500m"], t)}</p>
                <p>{t("insights.availableCapacity")}: {zone.available_capacity == null ? t("common.unknown") : formatNumber(language, zone.available_capacity)}</p></Popup>
            </CircleMarker>;
          })}
        </MapContainer>
        {view === "competition" && (cells.length > 0 || hasZoneCounts) && <div className="insights-legend"><Flame size={14}/><span>{t("insights.lowConcentration")}</span><i/><span>{t("insights.highConcentration")}</span></div>}
        {view === "competition" && heatmapMessage && <div className="insights-map-note" role="status">{heatmapMessage}</div>}
        {!comparedZones.some(zone => Array.isArray(zone.coordinates)) && <div className="insights-map-note" role="status">{t("insights.zoneLocationsUnavailable")}</div>}
      </div>

      <section className="insights-comparison">
        <div className="insights-section-title"><div><span className="vendor-eyebrow">{t("insights.comparisonKicker")}</span><h2>{t("insights.comparisonTitle")}</h2></div>
          <p>{t("insights.comparisonHelp")}</p>
        </div>
        {comparedZones.length ? <div className="insights-zone-grid">{comparedZones.map(zone => <article className="insights-zone-card" key={zone.zone_id}>
          <div className="insights-zone-heading"><MapPin size={17}/><h3>{zone.zone_id}</h3></div>
          <p>{zone.zone_division || zone.division || t("common.notRecorded")}</p>
          <div className="insights-zone-capacity"><span>{t("insights.availableCapacity")}</span><strong>{zone.available_capacity == null ? t("common.unknown") : formatNumber(language, zone.available_capacity)}</strong></div>
          <div className="insights-radius-counts"><strong>{t("insights.sameCategory")}</strong>{RADII.map(radius => <div key={radius}><span>{radius} m</span><b>{formatCount(language, zone.nearby_same_category?.[`${radius}m`], t)}</b></div>)}</div>
          {zone.counts_status === "LOCATION_UNAVAILABLE" && <small className="insights-unavailable">{t("insights.zoneCountUnavailable")}</small>}
          {zone.counts_status === "NO_MAPPED_COORDINATES" && <small className="insights-unavailable">{t("insights.noCoordinates")}</small>}
        </article>)}</div> : <div className="insights-message">{pendingRequest ? t("insights.pendingRequest") : t("insights.noRecommendations")}
          {!pendingRequest && <button className="vendor-secondary" type="button" onClick={refresh} disabled={busy}>{t("insights.refreshRecommendations")}</button>}
        </div>}
      </section>
      <p className="insights-notice">{data.notice} {t("insights.noRecommendationImpact")}</p>
    </>}
  </section>;
}
