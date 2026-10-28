import VendorActivity from "./VendorActivity.jsx";
import HelpSupport from "./HelpSupport.jsx";
import {PILOT_ZONE_IDS} from "../pilot-slots/pilotState.js";
import {zoneName} from "../../shared/utils/displayLabels.js";
import React, {useEffect, useRef, useState} from "react";
import AccountSettings from "./AccountSettings.jsx";
import "leaflet/dist/leaflet.css";
import {ArrowLeft, ArrowRight, Building2, Camera, Clock3, Download, Languages, MapPin, RefreshCw, UserRound, Store, Save, ShieldCheck, X} from "lucide-react";
import ToastRegion from "../../shared/ui/ToastRegion.jsx";
const PilotSlotMap = React.lazy(() => import("../pilot-slots/PilotSlotMap.jsx"));
import {categoryLabel, factorLabel, priorityLabel, requestTypeLabel, statusLabel} from "../../i18n/index.js";
import "./VendorPortal.css";
import "../../shared/maps/MapGrouping.css";
import "./VendorDashboard.css";
import "./VendorDashboardCompact.css";
import "./VendorApplications.css";
import {LANGUAGES, RANK_COLORS, pretty, score, displayCapacity} from "./viewModel.js";
import {getVendorAccountSettings, getVendorProfilePhoto, saveVendorProfilePhoto} from "../../services/api.js";
import {RecommendationMap, ZoneExplorer} from "./RecommendationMap.jsx";
import {PreferenceFields} from "./PreferenceFields.jsx";
import RecommendationDetailPage from "./RecommendationDetailPage.jsx";
import {ApplicationAllocationSummary, ApplicationSummary, ProfileSummary, AllocationCard, RequestSummary, RequestHistory, DashboardSkeleton} from "./DashboardSections.jsx";
import useVendorWorkspace from "./useVendorWorkspace.js";

const escapeXml = value => String(value ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&apos;",
}[character]));

const wrapCardText = (value, maxLength = 68, maxLines = 3) => {
  const words = String(value ?? "").trim().split(/\s+/u).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (next.length <= maxLength || !line) {
      line = next;
    } else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    lines.length = maxLines;
    lines[maxLines - 1] = `${lines[maxLines - 1].slice(0, maxLength - 1).trimEnd()}…`;
  }
  return lines;
};

const MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024;

const prepareProfilePhoto = async file => {
  if (file.size > 15 * 1024 * 1024) {
    throw new Error("Choose a photo smaller than 15 MB.");
  }

  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise((resolve, reject) => {
      const candidate = new Image();
      candidate.onload = () => resolve(candidate);
      candidate.onerror = () => reject(new Error("This photo format is not supported. Choose a JPG, PNG, or WebP image."));
      candidate.src = sourceUrl;
    });
    const scale = Math.min(1, 1200 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);

    let blob;
    for (const quality of [0.86, 0.76, 0.66, 0.56]) {
      blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", quality));
      if (blob && blob.size <= MAX_PROFILE_PHOTO_BYTES) break;
    }
    if (!blob || blob.size > MAX_PROFILE_PHOTO_BYTES) {
      throw new Error("This photo could not be compressed small enough. Choose a different image.");
    }

    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => typeof reader.result === "string"
        ? resolve(reader.result)
        : reject(new Error("The selected photo could not be read."));
      reader.onerror = () => reject(new Error("The selected photo could not be read."));
      reader.readAsDataURL(blob);
    });
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
};

export default function VendorPortal({sessionProfile = null, onboarding = false, view = "vendor-dashboard", detailZoneId = "", onNavigate = () => {}, onOpenRecommendation = () => {}, onBackRecommendations = () => {}, onRegistered, onProfileUpdated, focusRequestId = null, openOwnSlot = 0}) {
  const {language, t, options, profile, profileReady, draft, setDraft, activeAllocation, pilot, dispatchPilot, pilotSummary, recommendationData, mapContext, selectedId, setSelectedId, confirmZone, setConfirmZone, cancelTarget, setCancelTarget, preferenceConfirm, setPreferenceConfirm, dashboard, dashboardLoading, busy, error, setError, success, setSuccess, mapUnavailableIds, stage, setStage, handleGeometryStatus, refreshDashboard, register, persistProfile, saveProfile, saveRankingPreferences, saveAccountLanguage, findZones, submitZone, cancelRequest, changeLanguage, recommendations, displayName, greetingPeriod} = useVendorWorkspace({sessionProfile,onboarding,view,onNavigate,onRegistered});
  useEffect(() => {if (profile) onProfileUpdated?.(profile);}, [profile, onProfileUpdated]);
  const [activityRequest, setActivityRequest] = useState(null);
  const [explorerOpen, setExplorerOpen] = useState(false);
  const [profilePhoto, setProfilePhoto] = useState(null), [photoBusy, setPhotoBusy] = useState(false), [idCardBusy, setIdCardBusy] = useState(false), [maskedMobile, setMaskedMobile] = useState(null);
  const photoInputRef = useRef(null);
  useEffect(() => {
    if (!profile?.vendor_id) return;
    const controller = new AbortController();
    getVendorProfilePhoto(controller.signal)
      .then(result => {if (!controller.signal.aborted) setProfilePhoto(result.data_url);})
      .catch(error => {if (!controller.signal.aborted) setError(error.message);});
    getVendorAccountSettings(controller.signal)
      .then(result => {if (!controller.signal.aborted) setMaskedMobile(result.masked_mobile);})
      .catch(error => {if (!controller.signal.aborted) setError(error.message);});
    return () => controller.abort();
  }, [profile?.vendor_id, setError]);
  const uploadProfilePhoto = async event => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setPhotoBusy(true);
    setError("");
    try {
      const dataUrl = await prepareProfilePhoto(file);
      const result = await saveVendorProfilePhoto(dataUrl);
      setProfilePhoto(result.data_url);
    } catch (error) {
      setError(error.message);
    } finally {
      setPhotoBusy(false);
    }
  };
  const downloadVendorCard = async () => {
    if (!profile) return;
    const initials = profile.full_name?.trim().split(/\s+/u).slice(0, 2).map(part => Array.from(part)[0]).join("").toLocaleUpperCase() || "NMC";
    const currentZoneId = dashboard?.active_allocation?.zone_id || "No active vending zone";
    const currentZoneName = dashboard?.active_allocation?.zone_id ? zoneName(dashboard.active_allocation.zone_id) : "No active vending zone";
    const publicId = profile.application_vendor_id || profile.vendor_id;
    const cardName = profile.full_name || "Vendor";
    const cardNameFontSize = Math.min(42, Math.max(24, 42 * (28 / cardName.length)));
    const currentZoneNameLines = wrapCardText(currentZoneName);
    const currentZoneNameSvg = currentZoneNameLines.map((line, index) =>
      `<tspan x="520" dy="${index === 0 ? 0 : 20}">${escapeXml(line)}</tspan>`).join("");
    const photo = profilePhoto
      ? `<image href="${escapeXml(profilePhoto)}" x="72" y="190" width="256" height="300" preserveAspectRatio="xMidYMid slice" clip-path="url(#portraitClip)"/>`
      : `<rect x="72" y="190" width="256" height="300" rx="24" fill="#d6e9df"/><text x="200" y="363" text-anchor="middle" font-family="Arial,sans-serif" font-size="72" font-weight="700" fill="#17634e">${escapeXml(initials)}</text>`;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760"><defs><linearGradient id="green" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#155e4b"/><stop offset="1" stop-color="#0b4438"/></linearGradient><clipPath id="cardClip"><rect width="1200" height="760" rx="36"/></clipPath><clipPath id="portraitClip"><rect x="72" y="190" width="256" height="300" rx="24"/></clipPath></defs><g clip-path="url(#cardClip)"><rect width="1200" height="760" fill="#f5f8f6"/><rect width="390" height="760" fill="url(#green)"/><circle cx="354" cy="90" r="190" fill="#ffffff" opacity=".045"/><circle cx="8" cy="720" r="230" fill="#ffffff" opacity=".035"/><text x="64" y="76" font-family="Arial,sans-serif" font-size="20" font-weight="700" letter-spacing="2" fill="#ffffff">NASHIK</text><text x="64" y="108" font-family="Arial,sans-serif" font-size="14" font-weight="600" letter-spacing="1.5" fill="#cfe6db">VENDOR IDENTIFICATION</text><rect x="72" y="190" width="256" height="300" rx="24" fill="#d6e9df"/>${photo}<text x="200" y="540" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="700" letter-spacing="2" fill="#cfe6db">REGISTERED VENDOR</text><text x="200" y="688" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#cfe6db">NASHIK MUNICIPAL CORPORATION</text><text x="450" y="112" font-family="Arial,sans-serif" font-size="14" font-weight="700" fill="#628174">VENDOR ID CARD</text><text x="450" y="180" font-family="Arial,sans-serif" font-size="${cardNameFontSize}" font-weight="700" fill="#18382d">${escapeXml(cardName)}</text><text x="450" y="218" font-family="Arial,sans-serif" font-size="15" fill="#71877a">${escapeXml(profile.business_name || categoryLabel(language, profile.business_category))}</text><rect x="450" y="270" width="680" height="2" fill="#dce8e1"/><text x="450" y="324" font-family="Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.5" fill="#789084">UNIQUE VENDOR ID</text><text x="450" y="368" font-family="Arial,sans-serif" font-size="27" font-weight="700" fill="#18382d">${escapeXml(publicId)}</text><text x="450" y="438" font-family="Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.5" fill="#789084">REGISTERED MOBILE</text><text x="450" y="478" font-family="Arial,sans-serif" font-size="22" font-weight="600" fill="#29483a">${escapeXml(maskedMobile || "Not available")}</text><rect x="450" y="514" width="680" height="166" rx="18" fill="#e8f1ec"/><circle cx="488" cy="555" r="16" fill="#1c7559"/><path d="M488 545v20m-7-13 7-7 7 7" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><text x="520" y="550" font-family="Arial,sans-serif" font-size="12" font-weight="700" letter-spacing="1.2" fill="#71877a">CURRENT VENDING ZONE</text><rect x="520" y="565" width="230" height="34" rx="17" fill="#d5e8dc"/><text x="635" y="588" text-anchor="middle" font-family="Arial,sans-serif" font-size="15" font-weight="700" fill="#17634e">${escapeXml(currentZoneId)}</text><text x="520" y="628" font-family="Arial,sans-serif" font-size="16" font-weight="700" fill="#18382d">${currentZoneNameSvg}</text><text x="450" y="720" font-family="Arial,sans-serif" font-size="12" fill="#84978d">Please present this card when requested.</text><rect x="1080" y="74" width="52" height="8" rx="4" fill="#d5a84b"/></g></svg>`;

    setError("");
    setIdCardBusy(true);
    try {
      const svgUrl = URL.createObjectURL(new Blob([svg], {type: "image/svg+xml"}));
      try {
        const image = await new Promise((resolve, reject) => {
          const candidate = new Image();
          candidate.onload = () => resolve(candidate);
          candidate.onerror = () => reject(new Error("The vendor ID image could not be created."));
          candidate.src = svgUrl;
        });
        const canvas = document.createElement("canvas");
        canvas.width = 1200;
        canvas.height = 760;
        canvas.getContext("2d").drawImage(image, 0, 0);
        const png = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
        if (!png) throw new Error("The vendor ID image could not be created.");
        const url = URL.createObjectURL(png);
        const safeName = String(profile.full_name || "Vendor").trim().replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "Vendor";
        const safeId = String(publicId).replace(/[^A-Za-z0-9_-]/g, "-");
        const link = document.createElement("a");
        link.href = url;
        link.download = `Vendor-ID-${safeName}-${safeId}.png`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } finally {
        URL.revokeObjectURL(svgUrl);
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setIdCardBusy(false);
    }
  };
  useEffect(() => {
    if (view !== "vendor-requests" || !activityRequest || !dashboard) return;
    const element = document.getElementById(`vendor-request-${activityRequest}`);
    element?.scrollIntoView({block: "center", behavior: "smooth"}); element?.focus({preventScroll: true});
  }, [view, activityRequest, dashboard]);
  useEffect(() => {setActivityRequest(focusRequestId);}, [focusRequestId]);
  useEffect(() => {if (openOwnSlot && PILOT_ZONE_IDS.includes(dashboard?.active_allocation?.zone_id)) dispatchPilot({type: "open"});}, [openOwnSlot, dashboard?.active_allocation?.zone_id]);
  const allRecommendations = [...recommendations, ...(recommendationData?.remaining_recommendations || []), ...(recommendationData?.eligible_unscorable_zones || [])];
  const detailRecommendation = allRecommendations.find(zone => zone.zone_id === detailZoneId);
  return <main className={`vendor-portal ${onboarding ? "" : "service-vendor"}`}>
    <header className="vendor-hero" hidden={(view === "vendor-recommendations" && explorerOpen) || view === "vendor-notifications" || view === "vendor-help" || view === "vendor-profile" || view === "vendor-settings" || view === "vendor-recommendation-detail" || (!onboarding && pilot.open && view === "vendor-dashboard")}>
      <div><span className="vendor-eyebrow">{t("vendor.kicker")}</span><h1>{onboarding ? t("vendor.onboardingTitle") : t("vendor.greeting", {period: greetingPeriod, name: displayName})}</h1><p>{onboarding ? t("vendor.onboardingIntro") : t("vendor.greetingHelp")}</p></div>
      {onboarding && <label className="language-control"><Languages size={17}/><span>{t("language.label")}</span><select value={language} onChange={event => changeLanguage(event.target.value)}>{LANGUAGES.map(item => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>}
    </header>
    {onboarding && <nav className="vendor-progress" aria-label={t("nav.newOnboarding")}><div className="active"><span>1</span>{t("onboarding.account")}</div><div className="active"><span>2</span>{t("onboarding.business")}</div><div className="active"><span>3</span>{t("onboarding.preferences")}</div><div><span>4</span>{t("onboarding.recommendations")}</div></nav>}
    <ToastRegion success={success} error={error} onDismissSuccess={() => setSuccess("")} onDismissError={() => setError("")}/>

    {!onboarding && view === "vendor-dashboard" && dashboardLoading && !dashboard && <DashboardSkeleton label={t("requests.loadingDashboard")}/>}
    {!onboarding && view === "vendor-dashboard" && dashboard && !pilot.open && <div className="vendor-dashboard-stack vendor-dashboard-redesign">
      <div className="vendor-dashboard-overview"><AllocationCard allocation={dashboard.active_allocation}/><section className="vendor-dashboard-card dashboard-request-status"><div className="dashboard-section-heading"><div><span className="vendor-eyebrow">{t("requests.overview")}</span><h2>{t("requests.statusTitle")}</h2></div><button className="vendor-secondary" onClick={() => onNavigate("vendor-requests")}>{t("requests.viewAll")}</button></div><RequestSummary requests={dashboard.requests}/></section></div>
      <div className="vendor-dashboard-command-row">
        {!PILOT_ZONE_IDS.includes(dashboard.active_allocation?.zone_id) && <button className="vendor-primary service-next-action" onClick={() => onNavigate(dashboard.action_state.has_pending_request ? "vendor-requests" : "vendor-recommendations")}>{t(dashboard.action_state.has_pending_request ? "requests.open" : "requests.viewRecommendations")}<ArrowRight size={17}/></button>}
        {dashboard.action_state.blocked_reason && <div className="vendor-action-notice"><Clock3 size={18}/><div><strong>{dashboard.action_state.blocked_reason}</strong><p>{t("requests.follow")}</p></div></div>}
      </div>
      {PILOT_ZONE_IDS.includes(dashboard.active_allocation?.zone_id) && <section className="vendor-dashboard-card vendor-slot-prompt"><div><span className="vendor-eyebrow">{t("display.ownSlot")}</span><strong>{pilotSummary?.my_slot_id ? t("display.assignedSlot", {slot:pilotSummary.my_slot_id}) : t("display.noSlot")}</strong><small className="field-note">{t("display.provisionalNotice")}</small></div><button className="vendor-primary" onClick={() => dispatchPilot({type: "open"})}>{t("display.viewSlot")}</button></section>}
      <ProfileSummary profile={dashboard.profile} onEdit={() => onNavigate("vendor-profile")}/>
    </div>}

    {pilot.visited && PILOT_ZONE_IDS.includes(dashboard?.active_allocation?.zone_id) && <React.Suspense fallback={<p role="status">{t("display.slotLoading")}</p>}><PilotSlotMap zoneId={dashboard.active_allocation.zone_id} ownBusinessCategory={profile?.business_category} key={sessionProfile?.vendor_id} session={pilot} dispatch={dispatchPilot} visible={pilot.open && view === "vendor-dashboard"} onBack={() => dispatchPilot({type: "close"})}/></React.Suspense>}

    {!onboarding && view === "vendor-notifications" && <VendorActivity onApplication={id => {setActivityRequest(id); onNavigate("vendor-requests");}} onSlot={() => {onNavigate("vendor-dashboard"); dispatchPilot({type: "open"});}}/>}
    {!onboarding && view === "vendor-help" && <HelpSupport/>}

    {!onboarding && view === "vendor-requests" && dashboardLoading && !dashboard && <DashboardSkeleton label={t("requests.loadingHistory")}/>}
    {!onboarding && view === "vendor-requests" && dashboard && <div className="vendor-dashboard-stack vendor-applications-page"><header className="applications-page-header"><nav aria-label="Breadcrumb"><span>Vendor Portal</span><span aria-hidden="true">/</span><strong>{t("requests.heading")}</strong></nav><div><span className="vendor-eyebrow">{t("requests.overview")}</span><h1>{t("requests.heading")}</h1><p>Track your requests, review decisions, and manage your vending allocation.</p></div></header><ApplicationSummary summary={dashboard.request_summary}/><ApplicationAllocationSummary allocation={dashboard.active_allocation} onNavigate={onNavigate}/><RequestHistory requests={dashboard.requests} actionState={dashboard.action_state} busy={busy} onCancel={setCancelTarget} onRefresh={() => refreshDashboard()} onNavigate={onNavigate}/></div>}

    {!onboarding && view === "vendor-recommendations" && dashboard?.action_state?.has_pending_request && <div className="vendor-empty"><Clock3 size={30}/><h3>{t("requests.pendingExists")}</h3><p>{t("requests.pendingHelp")}</p><button className="vendor-primary" onClick={() => onNavigate("vendor-requests")}>{t("requests.open")}</button></div>}

    {stage === "register" && <section className="vendor-panel narrow"><span className="vendor-eyebrow">{t("onboarding.verified")}</span><h2>{t("onboarding.setupTitle")}</h2><p className="panel-copy">{t("onboarding.setupHelp")}</p><form onSubmit={register}><PreferenceFields draft={draft} setDraft={setDraft} options={options} requireIdentity mode="profile"/><button className="vendor-primary" disabled={busy}>{t(busy ? "onboarding.creating" : "onboarding.create")}<ArrowRight size={17}/></button></form></section>}

    {!onboarding && ["vendor-profile", "vendor-settings"].includes(view) && profile && <section className="vendor-profile-workspace">
      <header className="vendor-profile-heading"><div className="vendor-profile-photo-area"><div className="vendor-profile-avatar">{profilePhoto ? <img src={profilePhoto} alt={`${profile.full_name || "Vendor"} profile`}/> : profile.full_name?.trim() ? profile.full_name.trim().split(/\s+/u).slice(0,2).map(part => Array.from(part)[0]).join("").toLocaleUpperCase() : <UserRound size={28}/>}</div><input ref={photoInputRef} className="vendor-photo-input" type="file" accept="image/*" onChange={uploadProfilePhoto}/><button className="vendor-secondary vendor-photo-button" type="button" disabled={photoBusy} onClick={() => photoInputRef.current?.click()}><Camera size={16}/>{t(photoBusy ? "account.photoUploading" : profilePhoto ? "account.changePhoto" : "account.uploadPhoto")}</button></div><div className="vendor-profile-heading-copy"><span className="vendor-eyebrow">{t("nav.profile")}</span><h1>{profile.full_name || t("common.notRecorded")}</h1><p><Store size={15}/>{profile.business_name || categoryLabel(language,profile.business_category)}</p></div><div className="vendor-profile-heading-actions"><button className="vendor-secondary vendor-id-card-button" type="button" disabled={idCardBusy} onClick={downloadVendorCard}><Download size={16}/>{t(idCardBusy ? "account.preparingIdCard" : "account.downloadIdCard")}</button><span className={`vendor-profile-status status-${profile.status?.toLowerCase()}`}>{statusLabel(language,profile.status)}</span></div></header>
      <div className="vendor-profile-tabs" role="tablist" aria-label={t("nav.profile")}><button id="vendor-personal-tab" role="tab" aria-selected={view === "vendor-profile"} aria-controls="vendor-personal-panel" onClick={() => onNavigate("vendor-profile")}><UserRound size={17}/>{t("account.personalBusiness")}</button><button id="vendor-settings-tab" role="tab" aria-selected={view === "vendor-settings"} aria-controls="vendor-settings-panel" onClick={() => onNavigate("vendor-settings")}><ShieldCheck size={17}/>{t("account.settings")}</button></div>
      {view === "vendor-profile" ? <div id="vendor-personal-panel" role="tabpanel" aria-labelledby="vendor-personal-tab" className="vendor-profile-body"><section className="vendor-panel vendor-profile-form-panel"><h2>{t("account.personalBusiness")}</h2><p className="vendor-profile-intro">{t("account.profileIntro")}</p><form id="vendor-profile-edit" onSubmit={saveProfile}><PreferenceFields draft={draft} setDraft={setDraft} options={options} disabled={busy} mode="profile"/><div className="vendor-profile-savebar"><button className="vendor-primary" disabled={busy}><Save size={16}/>{t(busy ? "account.savingProfile" : "account.saveProfile")}</button></div></form></section><aside className="vendor-panel vendor-profile-note"><UserRound size={22}/><h2>{t("account.profileRecords")}</h2><p>{t("account.overlayNotice")}</p><hr/><ShieldCheck size={20}/><p>{t("account.profileSecurityHint")}</p></aside></div> : <div id="vendor-settings-panel" role="tabpanel" aria-labelledby="vendor-settings-tab"><AccountSettings profile={profile} busy={busy} activeAllocation={dashboard?.active_allocation} onSaveLanguage={saveAccountLanguage}/></div>}
    </section>}

    {stage === "recommendation-detail" && profile && !recommendationData && <DashboardSkeleton label={t("recommend.detailLoading")}/>}
    {stage === "recommendation-detail" && profile && recommendationData && !detailRecommendation && <div className="vendor-empty"><MapPin size={30}/><h3>{t("recommend.detailNotFound")}</h3><p>{t("recommend.detailNotFoundHelp")}</p><button className="vendor-primary" onClick={onBackRecommendations}><ArrowLeft size={16}/>{t("recommend.backRecommendations")}</button></div>}
    {stage === "recommendation-detail" && profile && detailRecommendation && <RecommendationDetailPage zone={detailRecommendation} recommendations={recommendations} mapContext={mapContext} profile={profile} activeAllocation={activeAllocation} dashboard={dashboard} busy={busy} onBack={onBackRecommendations} onSelect={setConfirmZone} onOpenRequests={() => onNavigate("vendor-requests")}/>}

    {stage === "recommendations" && profile && explorerOpen && recommendationData && <ZoneExplorer data={recommendationData} context={mapContext} selectedId={selectedId} onFocus={setSelectedId} onDetails={id => {setSelectedId(id); onOpenRecommendation(id);}} onRequest={zone => {setSelectedId(zone.zone_id); setConfirmZone(zone);}} onBack={() => setExplorerOpen(false)} busy={busy}/>}
    {stage === "recommendations" && profile && !explorerOpen && <section className="recommendation-workspace vendor-recommendations-home">
      <div className="recommendation-toolbar"><div><button className="vendor-back" onClick={() => setStage("profile")}><ArrowLeft size={15}/> {t("nav.profile")}</button><span className="vendor-eyebrow">{t("recommend.heading")}</span><h2>{t("recommend.title")}</h2><p>{t("recommend.eligible", {count: recommendationData?.candidate_count_after_division_filter ?? recommendationData?.candidate_count_after_live_filter ?? 0})}</p></div><button className="vendor-secondary" onClick={findZones} disabled={busy}><RefreshCw size={15}/> {t("common.refresh")}</button></div>
      <details className="vendor-panel"><summary>{t("recommend.preferences")}</summary><p className="field-note">{t("account.rankingEvidence")}</p><form onSubmit={saveRankingPreferences}><PreferenceFields mode="recommendations" draft={draft} setDraft={setDraft} options={options} disabled={busy || !profileReady}/><button className="vendor-primary" disabled={busy || !profileReady}>{t("profile.save")}</button></form></details>
      <div className="personalization-strip"><div><span>{t("recommend.preferences")}</span><strong>{t("common.priority")}: {priorityLabel(language, recommendationData?.priority_profile)}</strong></div><p>{t("profile.transport")}: <b>{t(recommendationData?.preference_flags?.transport ? "common.yes" : "common.no")}</b> · {t("profile.market")}: <b>{t(recommendationData?.preference_flags?.market ? "common.yes" : "common.no")}</b> · {t("profile.parking")}: <b>{t(recommendationData?.preference_flags?.parking ? "common.yes" : "common.no")}</b></p><details><summary>{t("recommend.whyRanking")}</summary><div>{Object.entries(recommendationData?.effective_factor_weights || {}).map(([key, value]) => <span key={key}>{factorLabel(language, key, pretty(key))} <b>{(value * 100).toFixed(1)}%</b></span>)}</div></details></div>
      {recommendations.length === 0 ? <div className="vendor-empty"><MapPin size={30}/><h3>{t("recommend.noZones")}</h3><p>{recommendationData?.notice || t("recommend.noZonesHelp")}</p>{recommendationData?.eligible_unscorable_zones?.length > 0 && <button className="vendor-secondary" onClick={() => setExplorerOpen(true)}>{t("recommend.viewAllZones")}</button>}</div> : <div className="recommendation-grid">
        <div className="zone-card-list">{recommendations.map(zone => <article key={zone.zone_id} className={`zone-card ${selectedId === zone.zone_id ? "selected" : ""}`} aria-selected={selectedId === zone.zone_id} onClick={() => {setSelectedId(zone.zone_id); onOpenRecommendation(zone.zone_id);}}>
          <span className="zone-rank" style={{background: RANK_COLORS[zone.rank]}}>#{zone.rank}</span><div className="zone-card-heading"><div><h3>{zone.zone_id}</h3><span>{zoneName(zone,t("display.zoneMissing"))} - {zone.zone_division}</span></div><strong>{score(zone.score,t("common.notRecorded"))}<small>/100</small></strong></div>
          {mapUnavailableIds?.has(zone.zone_id) && <div className="map-reference-unavailable"><MapPin size={13}/> {t("recommend.mapUnavailable")}</div>}
          <div className="zone-live-grid"><span><b>{statusLabel(language, zone.live_status)}</b> {t("common.liveStatus")}</span><span><b>{displayCapacity(zone.available_capacity, t)}</b> {t("common.available")}</span><span><b>{zone.current_vendor_count ?? t("common.notRecorded")}</b> {t("common.currentVendors")}</span></div><div className="zone-card-actions"><button onClick={event => {event.stopPropagation(); setSelectedId(zone.zone_id); document.getElementById("vendor-recommendation-map")?.scrollIntoView({behavior: "smooth", block: "center"});}}><MapPin size={14}/> {t("recommend.viewMap")}</button><button onClick={event => {event.stopPropagation(); setSelectedId(zone.zone_id); onOpenRecommendation(zone.zone_id);}}>{t("recommend.viewRecommendation")}</button><button className="select-zone" onClick={event => {event.stopPropagation(); setConfirmZone(zone);}}>{t("recommend.select")}</button></div>
        </article>)}</div>
        <RecommendationMap recommendations={recommendations} context={mapContext} selectedId={selectedId} onGeometryStatus={handleGeometryStatus} onFocus={setSelectedId} onExplore={() => setExplorerOpen(true)}/>
      </div>}
    </section>}

    {confirmZone && <div className="vendor-confirm-backdrop" onClick={() => setConfirmZone(null)}><div className="vendor-confirm" onClick={event => event.stopPropagation()}><div className="confirm-icon"><Building2 size={24}/></div><span className="vendor-eyebrow">{t("recommend.confirm")}</span><h2>{t("recommend.confirmTitle", {zoneId: zoneName(confirmZone,t("display.zoneMissing"))})}</h2><p>{t("recommend.confirmHelp")}</p>{confirmZone.slot_id && <div><span>Selected provisional slot</span><strong>{confirmZone.slot_id}</strong></div>}<div><span>{t("recommend.requestType")}</span><strong>{requestTypeLabel(language, activeAllocation ? "RELOCATION" : "NEW_ALLOCATION")}</strong></div><div className="confirm-actions"><button className="vendor-secondary" onClick={() => setConfirmZone(null)}>{t("common.goBack")}</button><button className="vendor-primary" onClick={submitZone} disabled={busy}>{t(busy ? "recommend.submitting" : "recommend.submit")}</button></div></div></div>}
    {cancelTarget && <div className="vendor-confirm-backdrop" onClick={() => setCancelTarget(null)}><div className="vendor-confirm" role="dialog" aria-modal="true" aria-labelledby="cancel-request-title" onClick={event => event.stopPropagation()}><div className="confirm-icon danger"><X size={24}/></div><span className="vendor-eyebrow">{t("requests.heading")}</span><h2 id="cancel-request-title">{t("confirm.cancelRequestTitle")}</h2><p>{t("confirm.cancelRequestHelp")}</p><div><span>{t("requests.requestId")}</span><strong>{cancelTarget}</strong></div><div className="confirm-actions"><button className="vendor-secondary" onClick={() => setCancelTarget(null)}>{t("confirm.keepRequest")}</button><button className="vendor-danger" onClick={async () => {const target = cancelTarget; setCancelTarget(null); await cancelRequest(target);}} disabled={busy}>{t("confirm.cancelRequest")}</button></div></div></div>}
    {preferenceConfirm && <div className="vendor-confirm-backdrop" onClick={() => setPreferenceConfirm(false)}><div className="vendor-confirm" role="dialog" aria-modal="true" aria-labelledby="preference-confirm-title" onClick={event => event.stopPropagation()}><div className="confirm-icon"><RefreshCw size={24}/></div><span className="vendor-eyebrow">{t("profile.heading")}</span><h2 id="preference-confirm-title">{t("confirm.preferenceTitle")}</h2><p>{t("confirm.preferenceHelp")}</p><div className="confirm-actions"><button className="vendor-secondary" onClick={() => setPreferenceConfirm(false)}>{t("confirm.keepPreferences")}</button><button className="vendor-primary" onClick={() => {setPreferenceConfirm(false); persistProfile();}} disabled={busy}>{t("confirm.savePreferences")}</button></div></div></div>}
  </main>;
}
