import React, {useEffect, useState} from "react";
import {MapContainer, Marker, TileLayer, useMap, useMapEvents} from "react-leaflet";
import L from "leaflet";
import markerUrl from "leaflet/dist/images/marker-icon.png";
import markerRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
import "leaflet/dist/leaflet.css";
import {formatNumber} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";

const NASHIK_CENTER = [19.9975, 73.7898];
const PIN_ICON = L.icon({
  iconUrl: markerUrl, iconRetinaUrl: markerRetinaUrl, shadowUrl: markerShadowUrl,
  iconSize: [25, 41], iconAnchor: [12, 41], shadowSize: [41, 41],
});

function MapPicker({position, disabled, onPick, t}) {
  const map = useMap();
  useMapEvents({click: event => {
    if (!disabled) onPick(event.latlng.wrap());
  }});
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({pan: false}));
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return <>
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
    {position && <Marker position={position} icon={PIN_ICON} alt={t("profile.pinSet")}/>}
  </>;
}

export function WorkingLocationFields({draft, setDraft, disabled}) {
  const {language, t} = useI18n();
  const [open, setOpen] = useState(false);
  const [map, setMap] = useState(null);
  const position = draft.preferred_latitude == null || draft.preferred_longitude == null
    ? null : [draft.preferred_latitude, draft.preferred_longitude];
  const setPin = point => setDraft(current => ({
    ...current,
    preferred_latitude: point?.lat ?? null,
    preferred_longitude: point?.lng ?? null,
    preferred_radius_km: point ? current.preferred_radius_km : null,
  }));
  return <fieldset className="vendor-working-location vendor-wide-field">
    <legend>{t("profile.workingLocation")}</legend>
    <p className="field-note">{t("profile.workingLocationHelp")}</p>
    <div className="vendor-location-actions">
      <button className="vendor-secondary" type="button" disabled={disabled} aria-expanded={open}
        onClick={() => setOpen(value => !value)}>{t(open ? "profile.hideLocationMap" : "profile.openLocationMap")}</button>
      {position && <button className="vendor-secondary" type="button" disabled={disabled}
        onClick={() => setPin(null)}>{t("profile.clearPin")}</button>}
    </div>
    {open && <>
      <p className="field-note">{t("profile.pinInstructions")}</p>
      <div role="group" aria-label={t("profile.workingLocation")}>
        <MapContainer ref={setMap} className="vendor-location-map" center={position || NASHIK_CENTER}
          zoom={position ? 15 : 12} scrollWheelZoom={false} minZoom={4} maxZoom={19}>
          <MapPicker position={position} disabled={disabled} onPick={setPin} t={t}/>
        </MapContainer>
      </div>
      <button className="vendor-secondary vendor-location-center" type="button" disabled={disabled || !map}
        onClick={() => setPin(map.getCenter().wrap())}>{t("profile.useMapCenter")}</button>
    </>}
    <p className="field-note" role="status">{t(position ? "profile.pinSet" : "profile.noPin")}</p>
    <label><span>{t("profile.preferredDistance")}</span>
      <select disabled={disabled || !position} value={draft.preferred_radius_km ?? ""}
        onChange={event => {
          const value = event.target.value;
          setDraft(current => ({...current, preferred_radius_km: value ? Number(value) : null}));
        }}>
        <option value="">{t("profile.anywhere")}</option>
        {[1, 3, 5, 10].map(radius => <option key={radius} value={radius}>
          {t("profile.distanceOption", {distance: formatNumber(language, radius)})}
        </option>)}
      </select>
    </label>
  </fieldset>;
}
