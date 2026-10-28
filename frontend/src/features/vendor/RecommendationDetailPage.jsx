import {zoneName,zoneDescription} from "../../shared/utils/displayLabels.js";
import React, {useEffect, useMemo, useState} from "react";
import {AlertCircle, ArrowLeft, Building2, Check, CheckCircle2, ChevronDown, Clock3, MapPin, Sparkles} from "lucide-react";
import {categoryLabel, factorLabel, factorSummary, statusLabel} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";
import {displayCapacity, indexAiFactorExplanations, score} from "./viewModel.js";
import RecommendationDetailMap from "./RecommendationDetailMap.jsx";
import {getRecommendationAiExplanation} from "../../services/api.js";
import "./RecommendationDetailPage.css";
import {PILOT_ZONE_IDS} from "../pilot-slots/pilotState.js";
const PilotSlotMap = React.lazy(() => import("../pilot-slots/PilotSlotMap.jsx"));

const evidenceKeys = {
  "Same-business records": "sameBusiness", "Historical associations": "historicalAssociations", "Evidence source": "source",
  "Commercial POIs · 250 m": "commercialPois", "Markets · 500 m": "markets", "Food POIs · 250 m": "foodPois",
  "Major-road distance": "majorRoad", "Bus-access distance": "busAccess", "Pedestrian-road density": "pedestrianDensity",
  "Healthcare · 500 m": "healthcare", "Education · 500 m": "education", "Public toilets · 500 m": "toilets",
  "Parking · 500 m": "parking", "Zone division": "division", "Fallback": "fallback", "Association records": "associationRecords",
  "Evidence method": "method",
  "Current same-category vendors": "currentSameCategoryVendors",
  "Historical same-category records": "historicalSameCategoryRecords",
  "Historical vendor-zone associations": "historicalTextAssociationRecords",
  "Historical text-associated records": "historicalTextAssociationRecords",
  "Accepted historical associations": "acceptedHistoricalAssociations",
};

function evidenceValue(t, value) {
  if (value === "Yes") return t("common.yes");
  if (value === "No") return t("common.no");
  if (value === "unknown") return t("common.unknown");
  if (value === "Text-associated vendor records") return t("evidence.textAssociatedRecords");
  return value ?? t("common.unknown");
}

function normalizedScore(value) {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return Math.max(0, Math.min(100, Number(value) * 100));
}

function strengthKey(value) {
  if (value >= 90) return "excellent";
  if (value >= 75) return "strong";
  if (value >= 60) return "good";
  if (value >= 40) return "moderate";
  return "limited";
}

const shortFactorLabel = (t, factor) => t(`factorShort.${factor.key}`);

function FactorCard({factor, language, t, expanded, onToggle, aiExplanation, aiSource}) {
  const value = normalizedScore(factor.score);
  const level = value == null ? "unknown" : strengthKey(value);
  const evidenceId = `factor-evidence-${factor.key}`;
  return <article className={`recommendation-factor-card strength-${level}`}>
    <div className="factor-card-heading"><h3>{shortFactorLabel(t, factor)}</h3><div className="factor-card-score"><strong>{value == null ? t("common.notRecorded") : Math.round(value)}</strong><span>/100</span></div></div>
    <span className="factor-strength-label">{value == null ? t("common.unknown") : t(`recommend.strength.${level}`)}</span>
    <div className="recommendation-factor-bar" role="progressbar" aria-label={shortFactorLabel(t, factor)} aria-valuemin="0" aria-valuemax="100" aria-valuenow={value == null ? undefined : Math.round(value)}><span style={{width: `${value || 0}%`}}/></div>
    <p>{factorSummary(language, factor.key, factor.summary)}</p>
    {aiExplanation && <div className={`factor-ai-explanation ${aiSource === "gemini" ? "generated" : "fallback"}`}><span><Sparkles size={13}/>{t(aiSource === "gemini" ? "recommend.aiGeneratedLabel" : "recommend.aiFallbackLabel")}</span><p>{aiExplanation}</p></div>}
    <button className="factor-evidence-toggle" type="button" aria-expanded={expanded} aria-controls={evidenceId} onClick={onToggle}>{t(expanded ? "recommend.hideEvidence" : "recommend.viewEvidence")}<ChevronDown size={15}/></button>
    {expanded && <div className="recommendation-evidence" id={evidenceId}><h4>{t("recommend.evidence")}</h4>{factor.evidence?.length ? <dl>{factor.evidence.map((item, index) => <div key={`${item.label}-${index}`}><dt>{t(`evidence.${evidenceKeys[item.label] || "record"}`)}</dt><dd>{evidenceValue(t, item.value)}</dd></div>)}</dl> : <p className="factor-no-evidence">{t("recommend.noEvidence")}</p>}</div>}
  </article>;
}

export default function RecommendationDetailPage({zone, recommendations, mapContext, profile, activeAllocation, dashboard, busy, onBack, onSelect, onOpenRequests}) {
  const {language, t} = useI18n();
  const [expandedFactor, setExpandedFactor] = useState("");
  const [aiResult, setAiResult] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [slotMapOpen,setSlotMapOpen] = useState(false);
  useEffect(() => { setAiResult(null); setAiError(""); setAiLoading(false); setSlotMapOpen(false); }, [zone?.zone_id]);
  const factors = zone?.factors || [];
  const rankedFactors = useMemo(() => factors.filter(item => normalizedScore(item.score) != null).sort((left, right) => normalizedScore(right.score) - normalizedScore(left.score)), [factors]);
  const strengths = rankedFactors.slice(0, 3);
  const weakest = rankedFactors.at(-1);
  const finalValue = Number.isFinite(Number(zone.score)) ? Number(zone.score) : null;
  const finalStrength = finalValue == null ? null : strengthKey(finalValue);
  const summary = strengths.length ? t("recommend.quickSummary", {
    first: shortFactorLabel(t, strengths[0]),
    second: strengths[1] ? shortFactorLabel(t, strengths[1]) : shortFactorLabel(t, strengths[0]),
    third: strengths[2] ? shortFactorLabel(t, strengths[2]) : shortFactorLabel(t, strengths.at(-1)),
    weakest: weakest ? shortFactorLabel(t, weakest) : t("common.unknown"),
  }) : t("recommend.detailSummaryUnavailable");
  const pending = dashboard?.action_state?.has_pending_request;
  const actionLoading = !dashboard;
  const aiByFactor = useMemo(() => indexAiFactorExplanations(aiResult), [aiResult]);
  async function loadAiExplanation() {
    setAiLoading(true); setAiError("");
    try { setAiResult(await getRecommendationAiExplanation(zone.zone_id)); }
    catch (error) { setAiError(error.message || t("recommend.aiUnavailable")); }
    finally { setAiLoading(false); }
  }

  return <section className="recommendation-detail-page">
    <button className="vendor-back recommendation-detail-back" onClick={onBack}><ArrowLeft size={16}/> {t("recommend.backRecommendations")}</button>
    <header className="recommendation-detail-header">
      <div><span className="recommendation-detail-rank">{zone.rank ? t("recommend.recommendedZone", {rank: zone.rank}) : t("recommend.viewRecommendation")}</span><h1>{zone.zone_id}</h1><p>{zoneDescription(zone,t("fallback.zoneDescription"))}</p><small>{zoneName(zone,t("display.zoneMissing"))}</small><div className="recommendation-detail-location"><MapPin size={14}/><span>{zone.zone_division || t("common.notSpecified")}</span></div></div>
      <div className="recommendation-detail-score"><span>{t("recommend.suitability")}</span><strong>{score(zone.score,t("common.notRecorded"))}</strong><small>/100</small><em>{t("recommend.recommendedForBusiness")}: {categoryLabel(language, profile?.business_category)}</em></div>
    </header>

    <div className="recommendation-summary-cards recommendation-operational-summary">
      <div><span>{t("common.liveStatus")}</span><strong>{statusLabel(language, zone.live_status)}</strong></div>
      <div><span>{t("recommend.availableSpaces")}</span><strong>{displayCapacity(zone.available_capacity, t)}</strong></div>
      <div><span>{t("common.currentVendors")}</span><strong>{zone.current_total_vendors ?? zone.current_vendor_count ?? t("common.notSpecified")}</strong></div>
    </div>

    <section className="recommendation-quick-summary">
      <div className="quick-summary-copy"><span className="vendor-eyebrow">{t("recommend.whyThisZone")}</span><h2>{finalStrength ? t("recommend.overallQuality", {quality: t(`recommend.strength.${finalStrength}`)}) : t("recommend.whyRankTitle", {rank: zone.rank})}</h2><p>{summary}</p></div>
      <div className="quick-summary-reasons"><div><h3>{t("recommend.mainStrengths")}</h3>{strengths.map(factor => <span key={factor.key}><Check size={15}/><b>{shortFactorLabel(t, factor)}</b><small>{t(`recommend.strength.${strengthKey(normalizedScore(factor.score))}`)}</small></span>)}</div>{weakest && <div className="quick-summary-consideration"><h3>{t("recommend.mainConsideration")}</h3><span><AlertCircle size={16}/><b>{t("recommend.considerationText", {factor: shortFactorLabel(t, weakest)})}</b></span></div>}</div>
    </section>

    <section className="recommendation-factors-section">
      <div className="recommendation-section-heading recommendation-ai-heading"><div><span className="vendor-eyebrow">{t("recommend.factorOverview")}</span><h2>{t("recommend.sixFactors")}</h2><p>{t("recommend.factorOverviewHelp")}</p></div><button className="vendor-secondary recommendation-ai-button" type="button" onClick={loadAiExplanation} disabled={aiLoading}><Sparkles size={15}/>{t(aiLoading ? "recommend.aiLoading" : aiResult ? "recommend.aiRefresh" : "recommend.aiExplain")}</button></div>
      {(aiResult?.message || aiError) && <p className={`recommendation-ai-notice ${aiError ? "error" : ""}`} role="status">{aiError || aiResult.message}</p>}
      <div className="recommendation-factor-grid">{factors.map(factor => <FactorCard key={factor.key} factor={factor} language={language} t={t} expanded={expandedFactor === factor.key} onToggle={() => setExpandedFactor(current => current === factor.key ? "" : factor.key)} aiExplanation={aiByFactor.get(factor.key)} aiSource={aiResult?.source}/>)}</div>
    </section>

    <section className="recommendation-zone-context">
      <div className="recommendation-zone-map"><h2>{t("recommend.zoneContext")}</h2><RecommendationDetailMap zone={zone} recommendations={recommendations} context={mapContext}/></div>
      <div className="recommendation-zone-facts"><h2>{t("recommend.operationalContext")}</h2><dl><div><dt>{t("common.division")}</dt><dd>{zone.zone_division || t("common.notSpecified")}</dd></div><div><dt>{t("common.liveStatus")}</dt><dd>{statusLabel(language, zone.live_status)}</dd></div><div><dt>{t("common.officialCapacity")}</dt><dd>{displayCapacity(zone.official_capacity, t)}</dd></div><div><dt>{t("common.currentVendors")}</dt><dd>{zone.current_total_vendors ?? zone.current_vendor_count ?? t("common.notSpecified")}</dd></div><div><dt>{t("evidence.currentSameCategoryVendors")}</dt><dd>{zone.current_same_category_vendors ?? 0}</dd></div><div><dt>{t("evidence.historicalSameCategoryRecords")}</dt><dd>{zone.historical_same_category_records ?? t("common.notSpecified")}</dd></div><div><dt>{t("evidence.historicalTextAssociationRecords")}</dt><dd>{zone.historical_text_association_records ?? zone.historical_vendor_zone_associations ?? t("common.notSpecified")}</dd></div><div><dt>{t("evidence.acceptedHistoricalAssociations")}</dt><dd>{zone.accepted_historical_association_count ?? t("common.notSpecified")}</dd></div><div><dt>{t("common.available")}</dt><dd>{displayCapacity(zone.available_capacity, t)}</dd></div></dl><p className="field-note">{t("common.currentVendorsHelp")}</p><p className="field-note">{t("evidence.historicalNotOccupancy")}</p>{zone.environment_cluster != null && <div className="recommendation-environment"><h3>{t("recommend.environmentalProfile")}</h3><p>{t("recommend.environmentalProfileText", {cluster: zone.environment_cluster})}</p></div>}<p className="recommendation-map-disclaimer">{t("recommend.analyticalBoundaryNotice")}</p></div>
    </section>

    {PILOT_ZONE_IDS.includes(zone.zone_id) && <section className="recommendation-slot-entry"><div><span className="vendor-eyebrow">Interactive slot layout</span><h2>Choose an available vending slot</h2><p>Slot positions are provisional planning geometry unless independently verified. Selecting a slot creates a request; it does not create an allocation.</p></div><button className="vendor-secondary" onClick={() => setSlotMapOpen(value=>!value)}>{slotMapOpen ? "Hide slot layout" : "View available slots"}</button></section>}
    {slotMapOpen && <React.Suspense fallback={<p role="status">Loading slot layout…</p>}><PilotSlotMap zoneId={zone.zone_id} visible onBack={() => setSlotMapOpen(false)} ownBusinessCategory={profile?.business_category} onRequestSlot={slot => onSelect({...zone,slot_id:slot.slot_id})}/></React.Suspense>}

    <details className="recommendation-calculation">
      <summary><span><strong>{t("recommend.calculationTitle")}</strong><small>{t("recommend.calculationSummary")}</small></span><ChevronDown size={18}/></summary>
      <div className="recommendation-calculation-body"><p>{t("recommend.calculationHelp")}</p><div className="recommendation-calculation-table"><table><thead><tr><th>{t("recommend.factorColumn")}</th><th>{t("common.score")}</th><th>{t("common.weight")}</th><th>{t("common.contribution")}</th></tr></thead><tbody>{factors.map(factor => <tr key={factor.key}><th>{factorLabel(language, factor.key, factor.label)}</th><td>{normalizedScore(factor.score) == null ? t("common.notRecorded") : Math.round(normalizedScore(factor.score))}</td><td>{factor.weight == null ? t("common.notRecorded") : `${Number(factor.weight).toFixed(1)}%`}</td><td>{factor.contribution == null ? t("common.notRecorded") : `+${score(factor.contribution,t("common.notRecorded"))}`}</td></tr>)}</tbody></table></div></div>
    </details>

    <section className={`recommendation-detail-action ${pending ? "blocked" : ""}`}>
      <div className="recommendation-action-icon">{pending || actionLoading ? <Clock3 size={22}/> : <CheckCircle2 size={22}/>}</div>
      <div><h2>{actionLoading ? t("common.loading") : pending ? t("requests.pendingExists") : t("recommend.actionTitle")}</h2><p>{pending ? t("recommend.pendingActionBlocked") : t("recommend.actionHelp")}</p></div>
      <div className="recommendation-detail-action-buttons"><button className="vendor-secondary" onClick={onBack}><ArrowLeft size={15}/>{t("recommend.backRecommendations")}</button>{actionLoading ? <button className="vendor-primary" disabled>{t("common.loading")}</button> : pending ? <button className="vendor-secondary" onClick={onOpenRequests}>{t("requests.open")}</button> : <button className="vendor-primary" onClick={() => onSelect(zone)} disabled={busy}><Building2 size={16}/>{t(activeAllocation ? "recommend.selectRelocation" : "recommend.selectThis")}</button>}</div>
    </section>
  </section>;
}
