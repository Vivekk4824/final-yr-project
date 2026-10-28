import {zoneName} from "../../shared/utils/displayLabels.js";
import React, {useState} from "react";

import {ArrowRight, CheckCircle2, ChevronDown, Clock3, FileText, MapPin, RefreshCw, XCircle} from "lucide-react";

import {useI18n} from "../../i18n/react.jsx";

import {categoryLabel, formatDate as localizedDate, priorityLabel, requestTypeLabel, statusLabel} from "../../i18n/index.js";

import {displayCapacity} from "./viewModel.js";

export function StatusPill({status}) {
  const {language} = useI18n();
  return <span className={`request-status status-${String(status).toLowerCase()}`}>{statusLabel(language, status)}</span>;
}

export function ProfileSummary({profile, onEdit}) {
  const {language, t} = useI18n();
  const [expanded, setExpanded] = useState(false);
  const contentId = "vendor-preferences-summary";
  return <section className="vendor-account-card vendor-preferences-card">
    <button className="vendor-preferences-toggle" type="button" aria-expanded={expanded} aria-controls={contentId} onClick={() => setExpanded(value => !value)}><span><b>{t("profile.heading")}</b></span><ChevronDown size={18}/></button>
    {expanded && <div id={contentId} className="vendor-preferences-content"><div className="vendor-account-grid"><div><span>{t("profile.businessCategory")}</span><strong>{categoryLabel(language, profile.business_category)}</strong></div><div><span>{t("profile.preferredDivision")}</span><strong>{profile.preferred_division || t("common.anyDivision")}</strong></div><div><span>{t("profile.preferredLocality")}</span><strong>{profile.preferred_locality || t("common.notSpecified")}</strong></div><div><span>{t("profile.preferredLanguage")}</span><strong>{t(`language.${profile.preferred_language || profile.language || "en"}`)}</strong></div><div><span>{t("profile.priorityProfile")}</span><strong>{priorityLabel(language, profile.priority_profile)}</strong></div><div><span>{t("profile.accountStatus")}</span><strong>{statusLabel(language, profile.status)}</strong></div></div><button className="vendor-secondary" onClick={onEdit}>{t("profile.edit")}</button></div>}
  </section>;
}

export function AllocationCard({allocation}) {
  const {language, t} = useI18n();
  return <section className="vendor-dashboard-card allocation-card"><div className="dashboard-section-heading"><div><span className="vendor-eyebrow">{t("allocation.heading")}</span><h2>{t("allocation.title")}</h2></div>{allocation && <StatusPill status="ACTIVE"/>}</div>
    {!allocation ? <div className="dashboard-empty"><MapPin size={27}/><strong>{t("allocation.noActive")}</strong><p>{t("allocation.noActiveHelp")}</p></div> : <><div className="allocation-zone"><MapPin size={22}/><div><strong>{zoneName(allocation,t("display.zoneMissing"))}</strong><p>{allocation.zone_id}</p><small>{t(allocation.allocation_source === "LEGACY_IMPORT" ? "allocation.importedExisting" : "allocation.adminApproved")}</small></div></div><details className="service-disclosure"><summary>{t("allocation.view")}</summary><div className="allocation-facts"><div><span>{t("allocation.date")}</span><strong>{localizedDate(language, allocation.allocated_at)}</strong></div><div><span>{t("allocation.type")}</span><strong>{requestTypeLabel(language, allocation.allocation_type || "NEW_ALLOCATION")}</strong></div><div><span>{t("common.liveStatus")}</span><strong>{statusLabel(language, allocation.live_zone_status)}</strong></div><div><span>{t("common.officialCapacity")}</span><strong>{displayCapacity(allocation.official_capacity, t)}</strong></div><div><span>{t("common.currentVendors")}</span><strong>{allocation.current_vendor_count ?? t("common.unknown")}</strong></div><div><span>{t("common.available")}</span><strong>{displayCapacity(allocation.available_capacity, t)}</strong></div></div><p className="field-note">{t("common.currentVendorsHelp")}</p></details></>}
  </section>;
}

export function RequestSummary({requests = []}) {
  const {language, t} = useI18n();
  const currentRequest = requests[0];
  return <section className="request-summary-grid current-only" style={{gridTemplateColumns: "minmax(0, 1fr)"}} aria-label={t("requests.statusTitle")}><div className={`request-summary-card ${currentRequest ? `status-border-${currentRequest.status.toLowerCase()}` : "status-border-empty"}`}><span>{t("requests.statusTitle")}</span><strong>{currentRequest ? statusLabel(language, currentRequest.status) : t("requests.empty")}</strong></div></section>;
}

export function ApplicationSummary({summary = {}}) {
  const {t} = useI18n();
  const cards = [["total", summary.total_requests ?? 0, FileText, "neutral"], ["pending", summary.pending_count ?? 0, Clock3, "pending"], ["approved", summary.approved_count ?? 0, CheckCircle2, "approved"], ["rejected", summary.rejected_count ?? 0, XCircle, "rejected"]];
  return <section className="application-summary-grid" aria-label={t("requests.overview")}>{cards.map(([key, count, Icon, tone]) => <article className={`application-summary-tile ${tone}`} key={key}><Icon size={17} aria-hidden="true"/><div><span>{t(`requests.summary.${key}`)}</span><strong>{count}</strong></div></article>)}</section>;
}

export function ApplicationAllocationSummary({allocation, onNavigate}) {
  const {t} = useI18n();
  if (!allocation) return null;
  return <aside className="application-allocation-context"><MapPin size={19} aria-hidden="true"/><div><span>{t("allocation.active")}</span><strong>{zoneName(allocation,t("display.zoneMissing"))}</strong><small>{allocation.zone_id} · <StatusPill status={allocation.status || "ACTIVE"}/></small></div><button className="vendor-secondary" onClick={() => onNavigate("vendor-dashboard")}><span>{t("allocation.view")}</span><ArrowRight size={15}/></button></aside>;
}

export function RequestHistory({requests, actionState, busy, onCancel, onRefresh, onNavigate}) {
  const {language, t} = useI18n();
  return <section className="vendor-dashboard-card request-history-card"><div className="dashboard-section-heading"><div><span className="vendor-eyebrow">{t("requests.heading")}</span><h2>{t("requests.history")}</h2><p>{t("requests.newest")}</p></div><button className="vendor-secondary" onClick={onRefresh} disabled={busy}><RefreshCw size={15}/> {t("common.refresh")}</button></div>
    {requests.length === 0 ? <div className="dashboard-empty"><FileText size={27}/><strong>{t("requests.empty")}</strong><p>{t("requests.emptyHelp")}</p><button className="vendor-primary" onClick={() => onNavigate("vendor-recommendations")}>{t("requests.viewRecommendations")}</button></div> : <div className="request-history-list">{requests.map(item => <article className={`request-history-item application-status-${item.status.toLowerCase()}`} id={`vendor-request-${item.request_id}`} tabIndex={-1} key={item.request_id}>
      <div className="request-history-main"><div><span className="request-type-label">{requestTypeLabel(language, item.request_type)}</span><h3>{zoneName(item,t("display.zoneMissing"))}</h3><p>{item.requested_zone_id} <span aria-hidden="true">·</span> {item.request_id}</p></div><StatusPill status={item.status}/></div>
      <div className="request-dates"><div><span>{t("common.submitted")}</span><strong>{localizedDate(language, item.created_at)}</strong></div>{item.reviewed_at && <div><span>{t("common.reviewed")}</span><strong>{localizedDate(language, item.reviewed_at)}</strong></div>}</div>
      <div className="request-timeline" aria-label={`${t("requests.history")}: ${item.request_id}`}><div className="timeline-step complete"><span/><div><strong>{t("common.submitted")}</strong></div></div><div className="timeline-line"/><div className={`timeline-step ${item.status === "PENDING" ? "current" : "complete"}`}><span/><div><strong>{t("requests.pendingReview")}</strong></div></div><div className="timeline-line"/><div className={`timeline-step ${item.status === "PENDING" ? "future" : `current ${item.status.toLowerCase()}`}`}><span/><div><strong>{item.status === "PENDING" ? t("requests.pending") : statusLabel(language, item.status)}</strong></div></div></div>
      <details className="request-details"><summary>{t("common.details")}</summary><dl className="request-meta"><div><dt>{t("requests.requestId")}</dt><dd>{item.request_id}</dd></div>{item.previous_zone_id && <div><dt>{t("requests.previousZone")}</dt><dd>{zoneName(item.previous_zone_id,t("display.zoneMissing"))}</dd></div>}{item.reviewed_at && <div><dt>{t("common.reviewed")}</dt><dd>{localizedDate(language, item.reviewed_at)}</dd></div>}</dl></details>
      {item.status === "REJECTED" && <p className="request-reason"><strong>{t("common.reason")}:</strong> {item.rejection_reason || t("requests.noReason")}</p>}
      <div className="request-row-actions">{item.status === "PENDING" && <button className="vendor-danger" onClick={() => onCancel(item.request_id)} disabled={busy}>{t("requests.cancel")}</button>}{item.status === "APPROVED" && <button className="vendor-secondary" onClick={() => onNavigate("vendor-dashboard")}>{t("allocation.view")}</button>}{item.status === "REJECTED" && actionState.can_submit_request && <button className="vendor-secondary" onClick={() => onNavigate("vendor-recommendations")}>{t("requests.returnRecommendations")}</button>}</div>
    </article>)}</div>}
  </section>;
}

export function DashboardSkeleton({label}) {
  return <div className="vendor-skeleton" role="status" aria-label={label}><span/><div/><div/><section><i/><i/><i/></section></div>;
}
