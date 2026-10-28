import {ShieldCheck, Languages, Download, FileText, Fingerprint} from "lucide-react";
import React, {useEffect, useState} from "react";
import {getVendorAccountSettings} from "../../services/api.js";
import {statusLabel, formatDate} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";
import {zoneName} from "../../shared/utils/displayLabels.js";
import {LANGUAGES} from "./viewModel.js";

export default function AccountSettings({profile, busy, activeAllocation, onSaveLanguage}) {
  const {language, t} = useI18n();
  const [data, setData] = useState(null), [error, setError] = useState(""), [reload, setReload] = useState(0);
  const [chosenLanguage, setChosenLanguage] = useState(profile.preferred_language || "en");
  const [saved, setSaved] = useState(false), [downloading, setDownloading] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setData(null); setError("");
    getVendorAccountSettings(controller.signal).then(result => {if (!controller.signal.aborted) {setData(result); setChosenLanguage(result.profile.preferred_language);}}).catch(err => {if (!controller.signal.aborted) setError(err.message);});
    return () => controller.abort();
  }, [profile.vendor_id, reload]);
  const saveLanguage = async event => {
    event.preventDefault(); setSaved(false);
    const result = await onSaveLanguage(chosenLanguage);
    if (result) {setData(current => ({...current, profile: result})); setSaved(true);}
  };
  const download = async () => {
    setError(""); setDownloading(true);
    try {
      const own = await getVendorAccountSettings();
      const blob = new Blob([JSON.stringify(own, null, 2)], {type: "application/json"});
      const url = URL.createObjectURL(blob), link = document.createElement("a");
      link.href = url; link.download = "my-vendor-information.json"; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {setError(err.message);} finally {setDownloading(false);}
  };
  if (!data) return <section className="vendor-panel"><h2>{t("account.settings")}</h2><p role={error ? "alert" : "status"}>{error || t("common.loading")}</p>{error && <button className="vendor-secondary" onClick={() => setReload(value => value + 1)}>{t("common.refresh")}</button>}</section>;
  const identity = data.profile;
  const rows = [...(identity.application_vendor_id ? [[t("account.applicationReference"), identity.application_vendor_id]] : []), [t("account.mobile"), data.masked_mobile || t("account.mobileUnavailable")], [t("account.currentZoneId"), activeAllocation?.zone_id || t("display.noSlot")], [t("account.contact"), t(!data.identity_verification_recorded ? "account.phoneUnverified" : data.development_authentication ? "account.developmentOnly" : "account.verificationUnproven")], [t("account.linkage"), t(data.historical_identity_linked ? "account.historicalLinked" : "account.noHistoricalLink")], [t("account.registered"), t(data.has_operational_profile ? "common.yes" : "common.no")]];
  return <section className="vendor-settings-workspace">
    {error && <p role="alert" className="vendor-action-notice">{error}</p>}
    <article className="vendor-panel"><h2><Fingerprint size={18}/>{t("account.accountInformation")}</h2><dl className="vendor-settings-values">{rows.map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></article>
    <article className="vendor-panel"><h2><Languages size={18}/>{t("profile.preferredLanguage")}</h2><form onSubmit={saveLanguage}><label className="language-control"><span>{t("language.label")}</span><select value={chosenLanguage} disabled={busy} onChange={event => {setChosenLanguage(event.target.value); setSaved(false);}}>{LANGUAGES.map(item => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label><button className="vendor-primary" disabled={busy || chosenLanguage === identity.preferred_language}>{t(busy ? "common.loading" : "profile.save")}</button></form>{saved && <p role="status">{t("profile.saved")}</p>}</article>
    <article className="vendor-panel"><h2><ShieldCheck size={18}/>{t("account.security")}</h2><p>{t(data.development_authentication ? "account.developmentWarning" : "account.verificationUnproven")}</p><p className="field-note">{t("account.secureChanges")}</p><p className="field-note">{t("account.nextStep")}</p></article>
    <article className="vendor-panel"><h2><FileText size={18}/>{t("account.personalInformation")}</h2><div className="profile-actions"><button className="vendor-secondary" disabled={downloading} onClick={download}><Download size={16}/>{t(downloading ? "common.loading" : "account.download")}</button></div><details className="vendor-settings-records"><summary>{t("requests.history")} ({data.requests.length})</summary>{data.requests.length ? data.requests.map(request => <p key={request.request_id}>{zoneName(request.zone_id)} - {statusLabel(language, request.status)} - {formatDate(language, request.created_at)}</p>) : <p>{t("account.noRequests")}</p>}</details><details className="vendor-settings-records"><summary>{t("account.allocations")} ({data.allocations.length})</summary>{data.allocations.length ? data.allocations.map(allocation => <p key={allocation.allocation_id}>{zoneName(allocation.zone_id)} - {statusLabel(language, allocation.status)} - {formatDate(language, allocation.allocated_at)}</p>) : <p>{t("account.noAllocations")}</p>}</details></article>
  </section>;
}
