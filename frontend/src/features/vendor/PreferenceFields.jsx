import React from "react";

import {Bus, CircleParking, Store} from "lucide-react";

import {useI18n} from "../../i18n/react.jsx";

import {categoryLabel, priorityLabel} from "../../i18n/index.js";

import {PROFILES} from "./viewModel.js";
import {WorkingLocationFields} from "./WorkingLocationFields.jsx";

export function PreferenceFields({draft, setDraft, options, disabled = false, requireIdentity = false, mode = "all"}) {
  const {language, t} = useI18n();
  const set = (key, value) => setDraft(current => ({...current, [key]: value}));
  const identity = mode !== "recommendations", ranking = mode !== "profile";
  return <div className="vendor-form-grid">
    {identity && <>{mode === "profile" && <div className="vendor-profile-section-title">{t("account.ownerDetails")}</div>}<label className={mode === "profile" ? "vendor-owner-field" : ""}><span>{t("identity.fullName")}</span><input disabled={disabled} required={requireIdentity} maxLength={120} value={draft.full_name} onChange={event => set("full_name", event.target.value)} placeholder={t("identity.fullNamePlaceholder")}/></label>
    {mode === "profile" && <div className="vendor-profile-section-title">{t("account.stallDetails")}</div>}
    <label><span>{t("identity.businessName")}</span><input disabled={disabled} maxLength={120} value={draft.business_name} onChange={event => set("business_name", event.target.value)} placeholder={t("identity.businessNamePlaceholder")}/></label></>}
    <label><span>{t("profile.businessCategory")}</span><select name="business_category" disabled={disabled} value={draft.business_category} onChange={event => set("business_category", event.target.value)}>{options.categories.map(item => <option value={item} key={item}>{categoryLabel(language, item)}</option>)}</select></label>
    <label><span>{t("profile.preferredDivision")}</span><select name="preferred_division" disabled={disabled} value={draft.preferred_division} onChange={event => set("preferred_division", event.target.value)}><option value="">{t("common.anyDivision")}</option>{options.divisions.map(item => <option value={item} key={item}>{item}</option>)}</select></label>
    <WorkingLocationFields draft={draft} setDraft={setDraft} disabled={disabled}/>
    {ranking && <fieldset id="vendor-profile-preferences" className="vendor-priority-options vendor-wide-field"><legend>{t("profile.priorityProfile")}</legend><div>{PROFILES.map(item => <label className={draft.priority_profile === item ? "selected" : ""} key={item}><input disabled={disabled} type="radio" name="priority_profile" value={item} checked={draft.priority_profile === item} onChange={() => set("priority_profile", item)}/><strong>{priorityLabel(language, item)}</strong><small>{t(item === "BALANCED" ? "profile.balancedHelp" : item === "COMMERCIAL" ? "profile.commercialHelp" : item === "ACCESSIBILITY" ? "profile.accessHelp" : "profile.facilitiesHelp")}</small></label>)}</div></fieldset>}
    {ranking && <div className="vendor-preference-toggles vendor-wide-field">
      <label><input disabled={disabled} type="checkbox" checked={draft.market_preference} onChange={event => set("market_preference", event.target.checked)}/><Store size={17}/><span>{t("profile.market")}</span></label>
      <label><input disabled={disabled} type="checkbox" checked={draft.transport_preference} onChange={event => set("transport_preference", event.target.checked)}/><Bus size={17}/><span>{t("profile.transport")}</span></label>
      <label><input disabled={disabled} type="checkbox" checked={draft.parking_preference} onChange={event => set("parking_preference", event.target.checked)}/><CircleParking size={17}/><span>{t("profile.parking")}</span></label>
    </div>}
  </div>;
}
