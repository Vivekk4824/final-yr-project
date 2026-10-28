import {useCallback, useEffect, useReducer, useRef, useState} from "react";

import {cancelAllocationRequest, createAllocationRequest, getActiveAllocation, getOptions, getRecommendations, getVendorDashboard, getVendorProfile, getVendorEligibleZones, registerVendor, updateVendorProfile, getPilotLayout} from "../../services/api.js";

import {profileDisplayName} from "../../shared/utils/profileIdentity.js";
import {useDialogFocus} from "../../shared/utils/dialogFocus.js";
import {useI18n} from "../../i18n/react.jsx";
import {mergeRecommendationContext, latestRecommendationRequest} from "./viewModel.js";

import {initialPilotState, pilotReducer, PILOT_ZONE_IDS} from "../pilot-slots/pilotState.js";

function draftFromProfile(profile) {
  return {
    full_name: profile?.full_name || "",
    business_name: profile?.business_name || "",
    business_category: profile?.business_category || "food",
    preferred_division: profile?.preferred_division || "",
    preferred_locality: profile?.preferred_locality || "",
    priority_profile: profile?.priority_profile || "BALANCED",
    market_preference: Boolean(profile?.market_preference),
    transport_preference: Boolean(profile?.transport_preference),
    parking_preference: Boolean(profile?.parking_preference),
    preferred_language: profile?.preferred_language || "en",
  };
}

export default function useVendorWorkspace({sessionProfile = null, onboarding = false, view = "vendor-dashboard", onNavigate = () => {}, onRegistered}) {

  const {language, t, selectLanguage} = useI18n();
  const [options, setOptions] = useState({categories: [], divisions: []});
  const [profile, setProfile] = useState(null);
  const [profileReady, setProfileReady] = useState(false);
  const recommendationRequest = useRef(latestRecommendationRequest());
  const actionRequest = useRef(latestRecommendationRequest());
  const [draft, setDraft] = useState(draftFromProfile());
  const [activeAllocation, setActiveAllocation] = useState(null);
  const [pilot, dispatchPilot] = useReducer(pilotReducer, initialPilotState);
  const [pilotSummary, setPilotSummary] = useState(null);
  const [recommendationData, setRecommendationData] = useState(null);
  const [mapContext, setMapContext] = useState({zones: [], current_zone_id: null, pending_zone_id: null});
  const [selectedId, setSelectedId] = useState("");
  const [confirmZone, setConfirmZone] = useState(null);
  const [cancelTarget, setCancelTarget] = useState(null);
  const [preferenceConfirm, setPreferenceConfirm] = useState(false);
  useDialogFocus(Boolean(confirmZone || cancelTarget || preferenceConfirm), ".vendor-confirm");
  const [dashboard, setDashboard] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [mapUnavailableIds, setMapUnavailableIds] = useState(null);
  const languagePatchRef = useRef("");
  const stage = onboarding ? "register" : view === "vendor-profile" ? "profile" : view === "vendor-recommendation-detail" ? "recommendation-detail" : view === "vendor-recommendations" && !dashboard?.action_state?.has_pending_request ? "recommendations" : "dashboard";
  const setStage = next => onNavigate(next === "profile" ? "vendor-profile" : next === "recommendations" ? "vendor-recommendations" : "vendor-dashboard");
  const handleGeometryStatus = useCallback(ids => setMapUnavailableIds(ids ? new Set(ids) : null), []);

  useEffect(() => { getOptions().then(setOptions).catch(err => setError(err.message)); }, []);
  useEffect(() => {
    if (!sessionProfile) return;
    setProfile(sessionProfile); setDraft(draftFromProfile(sessionProfile));
  }, [sessionProfile?.vendor_id]);
  useEffect(() => {
    if (!sessionProfile?.vendor_id) return;
    setProfileReady(false);
    recommendationRequest.current.invalidate();
    let active = true;
    getVendorProfile(sessionProfile.vendor_id).then(vendor => {if (active) {setProfile(vendor); setDraft(draftFromProfile(vendor)); setProfileReady(true);}}).catch(err => {if (active) {setError(err.message);}});
    return () => {active = false;};
  }, [sessionProfile?.vendor_id]);
  const run = async action => {
    const actionId = actionRequest.current.begin();
    setBusy(true); setError(""); setSuccess("");
    try { return await action(); } catch (err) {
      if (actionRequest.current.isCurrent(actionId)) setError(err.message);
      return null;
    } finally {if (actionRequest.current.isCurrent(actionId)) setBusy(false);}
  };
  const refreshDashboard = useCallback(async (quiet = false) => {
    if (!sessionProfile?.vendor_id) return null;
    if (!quiet) setDashboardLoading(true);
    try {
      const data = await getVendorDashboard();
      setDashboard(data); setActiveAllocation(data.active_allocation);
      if (PILOT_ZONE_IDS.includes(data.active_allocation?.zone_id)) {
        try {setPilotSummary(await getPilotLayout(data.active_allocation.zone_id));} catch {setPilotSummary(null);}
      } else setPilotSummary(null);
      return data;
    } catch (err) {
      setError(err.message); return null;
    } finally {
      if (!quiet) setDashboardLoading(false);
    }
  }, [sessionProfile?.vendor_id]);
  useEffect(() => {
    if (!onboarding && sessionProfile?.vendor_id) refreshDashboard();
  }, [onboarding, sessionProfile?.vendor_id, refreshDashboard]);
  const hydrateVendor = async vendor => {
    setProfile(vendor); setDraft(draftFromProfile(vendor)); selectLanguage(vendor.preferred_language, {deliberate: false});
    setProfileReady(true);
    const active = await getActiveAllocation(vendor.vendor_id);
    setActiveAllocation(active.allocation);
  };
  const register = event => { event.preventDefault(); run(async () => {
    const vendor = await registerVendor({...draft, preferred_division: draft.preferred_division || null, preferred_locality: draft.preferred_locality || null});
    await hydrateVendor(vendor); await onRegistered?.(); setSuccess(t("onboarding.created"));
  }); };
  const persistProfile = () => run(async () => {
    recommendationRequest.current.invalidate();
    const vendor = await updateVendorProfile(profile.vendor_id, {full_name: draft.full_name, business_name: draft.business_name, business_category: draft.business_category, preferred_division: draft.preferred_division || null, preferred_locality: draft.preferred_locality || null});
    setProfile(vendor); setDraft(draftFromProfile(vendor)); selectLanguage(vendor.preferred_language); setRecommendationData(null); await refreshDashboard(true); setSuccess(t("profile.saved"));
  });
  const saveAccountLanguage = next => run(async () => {
    const vendor = await updateVendorProfile(profile.vendor_id, {preferred_language: next});
    setProfile(vendor); setDraft(current => ({...current, preferred_language: vendor.preferred_language}));
    selectLanguage(vendor.preferred_language); await refreshDashboard(true); setSuccess(t("profile.saved"));
    return vendor;
  });
  const saveRankingPreferences = event => {event.preventDefault(); run(async () => {
    recommendationRequest.current.invalidate();
    const vendor = await updateVendorProfile(profile.vendor_id, {priority_profile: draft.priority_profile,
      market_preference: draft.market_preference, transport_preference: draft.transport_preference, parking_preference: draft.parking_preference});
    setProfile(vendor); setDraft(draftFromProfile(vendor)); await refreshDashboard(true);
    await loadRecommendations(vendor, {navigate:false}); setSuccess(t("profile.saved"));
  });};
  const saveProfile = event => {
    event.preventDefault();
    if (recommendationData) setPreferenceConfirm(true);
    else persistProfile();
  };
  const loadRecommendations = async (vendor, {navigate = true} = {}) => {
    const requestId = recommendationRequest.current.begin();
    try {
      const active = await getActiveAllocation(vendor.vendor_id);
      if (!recommendationRequest.current.isCurrent(requestId)) return;
      setActiveAllocation(active.allocation);
      const [data, context] = await Promise.all([
        getRecommendations(vendor.vendor_id, active.allocation?.zone_id || "", {
          business: vendor.business_category,
          division: vendor.preferred_division || "",
        }),
        getVendorEligibleZones(),
      ]);
      if (!recommendationRequest.current.isCurrent(requestId)) return;
      setMapUnavailableIds(null);
      setMapContext(mergeRecommendationContext(data, context)); setRecommendationData(data);
      const ids = new Set([...data.recommendations, ...(data.remaining_recommendations || []), ...(data.eligible_unscorable_zones || [])].map(zone => zone.zone_id));
      setSelectedId(current => ids.has(current) ? current : data.recommendations[0]?.zone_id || "");
      if (navigate) onNavigate("vendor-recommendations");
    } catch (error) {
      if (recommendationRequest.current.isCurrent(requestId)) throw error;
    }
  };
  const findZones = ({navigate = true} = {}) => run(() => loadRecommendations(profile, {navigate}));
  useEffect(() => {
    const recommendationView = view === "vendor-recommendations" || view === "vendor-recommendation-detail";
    if (recommendationView && profileReady && profile && !recommendationData && (view === "vendor-recommendation-detail" || !dashboard?.action_state?.has_pending_request)) findZones({navigate: false});
  }, [view, profileReady, profile?.vendor_id, recommendationData, dashboard?.action_state?.has_pending_request]);
  useEffect(() => () => {recommendationRequest.current.invalidate(); actionRequest.current.invalidate();}, []);
  const submitZone = () => run(async () => {
    const requestType = activeAllocation ? "RELOCATION" : "NEW_ALLOCATION";
    const created = await createAllocationRequest({
      vendor_id: profile.vendor_id, zone_id: confirmZone.zone_id, request_type: requestType,
      slot_id: confirmZone.slot_id || null,
      business_category: profile.business_category, preferred_division: profile.preferred_division,
      notes: "Submitted through vendor portal",
    });
    setConfirmZone(null); await refreshDashboard(true); onNavigate("vendor-requests");
    setSuccess(t("requests.submittedNotice"));
  });
  const cancelRequest = requestId => run(async () => {
    await cancelAllocationRequest(requestId);
    await refreshDashboard(true); setSuccess(t("requests.cancelledNotice"));
  });
  useEffect(() => {
    if (!confirmZone && !cancelTarget && !preferenceConfirm) return undefined;
    const close = event => {
      if (event.key !== "Escape") return;
      setConfirmZone(null); setCancelTarget(null); setPreferenceConfirm(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [confirmZone, cancelTarget, preferenceConfirm]);
  const changeLanguage = next => {
    selectLanguage(next);
    setDraft(current => ({...current, preferred_language: next}));
    if (!onboarding && profile?.vendor_id && profile.preferred_language !== next && languagePatchRef.current !== next) {
      languagePatchRef.current = next;
      updateVendorProfile(profile.vendor_id, {preferred_language: next})
        .then(vendor => {
          if (languagePatchRef.current !== next) return;
          setProfile(vendor);
          setDraft(current => ({...current, preferred_language: vendor.preferred_language}));
          setDashboard(current => current ? {...current, profile: {...current.profile, preferred_language: vendor.preferred_language}} : current);
        })
        .catch(err => setError(err.message))
        .finally(() => { if (languagePatchRef.current === next) languagePatchRef.current = ""; });
    }
  };
  const recommendations = recommendationData?.recommendations || [];
  const identityProfile = dashboard?.profile || profile;
  const displayName = profileDisplayName(identityProfile, {application: t("identity.applicationVendor"), registered: t("identity.registeredVendor")});
  const hour = new Date().getHours();
  const greetingPeriod = t(hour < 12 ? "vendor.morning" : hour < 17 ? "vendor.afternoon" : "vendor.evening");

  return {language, t, options, profile, profileReady, draft, setDraft, activeAllocation, pilot, dispatchPilot, pilotSummary, recommendationData, mapContext, selectedId, setSelectedId, confirmZone, setConfirmZone, cancelTarget, setCancelTarget, preferenceConfirm, setPreferenceConfirm, dashboard, dashboardLoading, busy, error, setError, success, setSuccess, mapUnavailableIds, stage, setStage, handleGeometryStatus, refreshDashboard, register, persistProfile, saveProfile, saveRankingPreferences, saveAccountLanguage, findZones, submitZone, cancelRequest, changeLanguage, recommendations, displayName, greetingPeriod};
}
