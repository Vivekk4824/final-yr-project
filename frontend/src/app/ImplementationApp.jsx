import VendorActivity from "../features/vendor/VendorActivity.jsx";
import {useDialogFocus} from "../shared/utils/dialogFocus.js";
import React, {useCallback, useEffect, useState} from "react";
import {Bell, Building2, CircleHelp, BarChart3, ChevronRight, FileText, LayoutDashboard, LogOut, MapPin, Menu, ShieldCheck, UserRound, X} from "lucide-react";
import VendorDirectory from "../features/admin/VendorDirectory.jsx";
import AdminDashboard from "../features/admin/AdminDashboard.jsx";
import AuthLanding from "../features/auth/AuthLanding.jsx";
import RecommendationPage from "../features/recommendations/RecommendationPage.jsx";
import VendorPortal from "../features/vendor/VendorPortal.jsx";
import BrandIdentity from "../shared/ui/BrandIdentity.jsx";
import {AnalysisPage, OverviewPage, ReviewPage, ZoneRegistryPage} from "../pages/ImplementationPages.jsx";
import {getCurrentUser, logout} from "../services/api.js";
import {useI18n} from "../i18n/react.jsx";
import {profileDisplayName, publicVendorId} from "../shared/utils/profileIdentity.js";





const ADMIN_NAV = [
  {id: "vendors", title: "Vendors", icon: UserRound},
  {id: "admin", title: "Admin dashboard", icon: ShieldCheck},
  {id: "recommend", title: "Research recommendations", icon: MapPin},
  {id: "analysis", title: "GIS & model insights", icon: BarChart3},
  {id: "review", title: "Expert review", icon: FileText},
];
const VENDOR_NAV = [
  {id: "vendor-dashboard", titleKey: "nav.dashboard", icon: LayoutDashboard},
  {id: "vendor-recommendations", titleKey: "nav.recommendations", icon: MapPin},
  {id: "vendor-requests", titleKey: "nav.requests", icon: FileText},
  {id: "vendor-help", titleKey: "help.title", icon: CircleHelp},
  {id: "vendor-profile", titleKey: "nav.profile", icon: UserRound},
];
const VENDOR_PATHS = {
  "vendor-dashboard": "/vendor",
  "vendor-recommendations": "/vendor/recommendations",
  "vendor-requests": "/vendor/requests",
  "vendor-profile": "/vendor/profile",
  "vendor-settings": "/vendor/settings",
  "vendor-notifications": "/vendor/notifications",
  "vendor-help": "/vendor/help",
};

export default function ImplementationApp() {
  const {t, applyProfileLanguage} = useI18n();
  const [session, setSession] = useState(null);
  const [logoutError, setLogoutError] = useState("");
  const [checking, setChecking] = useState(true);
  const [page, setPage] = useState("vendor-dashboard");
  const [recommendationZoneId, setRecommendationZoneId] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [focusedRequestId, setFocusedRequestId] = useState(null);
  const [openOwnSlot, setOpenOwnSlot] = useState(0);
  useDialogFocus(notificationsOpen, ".vendor-notification-drawer");
  useEffect(() => {
    if (!notificationsOpen) return;
    const close = event => {if (event.key === "Escape") setNotificationsOpen(false);};
    document.addEventListener("keydown", close); return () => document.removeEventListener("keydown", close);
  }, [notificationsOpen]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [slotTarget, setSlotTarget] = useState(null);
  const [requestedDivision, setRequestedDivision] = useState("");

  const routeFromPath = next => {
    if (next?.role !== "VENDOR") return null;
    const match = window.location.pathname.match(/^\/vendor\/recommendations\/([^/]+)\/?$/);
    if (match) return {page: "vendor-recommendation-detail", zoneId: decodeURIComponent(match[1])};
    const vendorPage = Object.entries(VENDOR_PATHS).find(([, path]) => window.location.pathname === path)?.[0];
    if (vendorPage) return {page: vendorPage, zoneId: "", requestId: vendorPage === "vendor-requests" ? new URLSearchParams(window.location.search).get("request") : null};
    return null;
  };
  const applySession = (next, {preserveRoute = false} = {}) => {
    if (next?.role === "VENDOR") applyProfileLanguage(next.vendor_profile?.preferred_language);
    setSession(next);
    const admin = next?.role === "ADMIN";
    const preserved = preserveRoute ? routeFromPath(next) : null;
    if (preserved) {
      setPage(preserved.page); setRecommendationZoneId(preserved.zoneId || ""); setFocusedRequestId(preserved.requestId || null);
      return;
    }
    const nextPage = admin ? "admin" : "vendor-dashboard";
    setPage(nextPage); setRecommendationZoneId("");
    window.history.replaceState({}, "", admin ? "/admin" : "/vendor");
  };
  useEffect(() => {
    getCurrentUser().then(next => applySession(next, {preserveRoute: true})).catch(() => {
      setSession(null); window.history.replaceState({}, "", "/login");
    }).finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    const handlePopState = () => {
      if (session?.role !== "VENDOR") return;
      const route = routeFromPath(session);
      if (route) {
        setPage(route.page); setRecommendationZoneId(route.zoneId || ""); setFocusedRequestId(route.requestId || null); setNotificationsOpen(false);
      } else {
        const vendorPage = VENDOR_NAV.find(item => window.location.pathname.endsWith(`/${item.id}`))?.id || "vendor-dashboard";
        setPage(vendorPage); setRecommendationZoneId("");
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [session]);

  const updateVendorProfile = useCallback(profile => setSession(current => current?.role === "VENDOR" && current.vendor_id === profile.vendor_id ? {...current, vendor_profile: profile} : current), []);
  const signOut = async () => {
    setLogoutError("");
    try {await logout();} catch (err) {setLogoutError(err.message); return;}
    setSession(null); setPage("vendor-dashboard"); setRecommendationZoneId(""); window.history.replaceState({}, "", "/login");
  };
  const refreshSession = async () => applySession(await getCurrentUser());
  const navigate = id => {
    const allowed = (session?.role === "ADMIN" ? ADMIN_NAV : VENDOR_NAV).some(item => item.id === id) || (session?.role === "VENDOR" && id === "vendor-settings");
    const safe = allowed ? id : session?.role === "ADMIN" ? "admin" : "vendor-dashboard";
    setPage(safe); setRecommendationZoneId(""); setMobileOpen(false); setNotificationsOpen(false);
    if (safe !== "vendor-requests") setFocusedRequestId(null);
    const path = session?.role === "ADMIN" ? `/admin/${safe}` : VENDOR_PATHS[safe] || "/vendor";
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
  };
  const openRecommendation = zoneId => {
    setRecommendationZoneId(zoneId); setPage("vendor-recommendation-detail"); setMobileOpen(false);
    window.history.pushState({}, "", `/vendor/recommendations/${encodeURIComponent(zoneId)}`);
  };
  const backToRecommendations = () => {
    setRecommendationZoneId(""); setPage("vendor-recommendations");
    window.history.replaceState({}, "", VENDOR_PATHS["vendor-recommendations"]);
  };
  const openZone = division => {
    setRequestedDivision(division === "Citywide" ? "" : division); navigate("recommend");
  };

  if (checking) return <div className="auth-loading"><Building2 size={28}/><span>{t("common.loading")}</span></div>;
  if (!session) return <AuthLanding onAuthenticated={applySession}/>;

  const onboarding = session.role === "NEW_VENDOR_ONBOARDING";
  if (onboarding) return <VendorPortal onboarding onRegistered={refreshSession}/>;

  const nav = session.role === "ADMIN" ? ADMIN_NAV : VENDOR_NAV;
  const current = nav.find(item => item.id === page || (page === "vendor-settings" && item.id === "vendor-profile")) || (page === "vendor-recommendation-detail" ? VENDOR_NAV[1] : nav[0]);
  const navTitle = item => session.role === "ADMIN" ? item.title : t(item.titleKey);
  const vendorName = profileDisplayName(session.vendor_profile, {application: t("identity.applicationVendor"), registered: t("identity.registeredVendor")});
  return <div className={`implementation-shell ${onboarding ? "" : "service-app"}`}><aside className={`implementation-sidebar ${mobileOpen ? "mobile-open" : ""}`}>
    <div className="brand"><BrandIdentity compact subtitle={session.role === "ADMIN" ? "NMC Officer Workspace" : t("nav.vendorServices")}/><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label={session.role === "ADMIN" ? "Close menu" : t("nav.close")}><X size={19}/></button></div>
    <div className="sidebar-section-label">{session.role === "ADMIN" ? "YOUR WORKSPACE" : t("portal.main")}</div><nav className="implementation-nav" aria-label={session.role === "ADMIN" ? "Main navigation" : t("portal.main")}>{nav.filter(item => session.role === "ADMIN" || item.id !== "vendor-help").map(item => {const active = page === item.id || (item.id === "vendor-recommendations" && page === "vendor-recommendation-detail") || (item.id === "vendor-profile" && page === "vendor-settings"); return <button key={item.id} className={active ? "active" : ""} aria-current={active ? "page" : undefined} onClick={() => navigate(item.id)}><item.icon size={18}/><span>{navTitle(item)}</span>{session.role === "ADMIN" && active && <ChevronRight size={15} className="nav-arrow"/>}</button>;})}</nav>
    {session.role === "VENDOR" && <><div className="sidebar-section-label">{t("portal.support")}</div><nav className="implementation-nav" aria-label={t("portal.support")}><button className={page === "vendor-help" ? "active" : ""} aria-current={page === "vendor-help" ? "page" : undefined} onClick={() => navigate("vendor-help")}><CircleHelp size={18}/><span>{t("help.title")}</span></button></nav></>}
    <div className={`sidebar-bottom auth-session-card ${session.role === "VENDOR" ? "vendor-session-card" : ""}`}>
      <div className="sidebar-bottom-label">{session.role === "ADMIN" ? "SIGNED IN AS" : t("nav.signedInAs")}</div>
      {session.role === "ADMIN" ? <>
        <strong>{session.admin_id}</strong>
        <p>ADMIN</p>
      </> : <>
        <strong className="vendor-session-name">{vendorName}</strong>
        {session.vendor_id && <small className="vendor-session-id">{t("identity.vendorId", {id: publicVendorId(session.vendor_profile)})}</small>}
      </>}
      <button onClick={signOut}><LogOut size={14}/>{session.role === "ADMIN" ? "Log out" : t("nav.logout")}</button>
    </div>
  </aside>
  {mobileOpen && <button className="sidebar-backdrop" onClick={() => setMobileOpen(false)} aria-label={session.role === "ADMIN" ? "Close navigation" : t("nav.close")}/>}
  <div className="implementation-content"><header className="implementation-topbar"><button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label={session.role === "ADMIN" ? "Open navigation" : t("nav.open")}><Menu size={20}/></button>{session.role === "ADMIN" ? <><div className="topbar-breadcrumb">Officer workspace <ChevronRight size={13}/><strong>{navTitle(current)}</strong></div><div className="topbar-right"><span className="topbar-dot"/>Authenticated <span className="topbar-avatar">N</span></div></> : <div className="vendor-header-actions"><button className="vendor-notification-bell" aria-label={t("activity.title")} aria-expanded={notificationsOpen} aria-controls="vendor-notifications-dialog" aria-haspopup="dialog" onClick={() => setNotificationsOpen(value => !value)}><Bell size={20}/></button></div>}</header>
  <div className="implementation-view">
    {logoutError && <p role="alert" className="vendor-action-notice">{logoutError}</p>}
    {(session.role === "VENDOR" || onboarding) && <VendorPortal onProfileUpdated={updateVendorProfile} focusRequestId={focusedRequestId} openOwnSlot={openOwnSlot} sessionProfile={session.vendor_profile} onboarding={onboarding} view={page} detailZoneId={recommendationZoneId} onNavigate={navigate} onOpenRecommendation={openRecommendation} onBackRecommendations={backToRecommendations} onRegistered={refreshSession}/>}
    {session.role === "ADMIN" && page === "admin" && <AdminDashboard adminId={session.admin_id} slotTarget={slotTarget}/>}
    {session.role === "ADMIN" && page === "vendors" && <VendorDirectory onViewSlot={slot => {setSlotTarget({...slot}); navigate("admin");}}/>}
    {session.role === "ADMIN" && page === "overview" && <OverviewPage navigate={navigate}/>}
    {session.role === "ADMIN" && page === "zones" && <ZoneRegistryPage openZone={openZone}/>}
    {session.role === "ADMIN" && page === "recommend" && <RecommendationPage key={requestedDivision || "default"} initialDivision={requestedDivision}/>}
    {session.role === "ADMIN" && page === "analysis" && <AnalysisPage/>}
    {session.role === "ADMIN" && page === "review" && <ReviewPage/>}
  </div></div>
  {session.role === "VENDOR" && notificationsOpen && <div className="vendor-notification-backdrop" onClick={() => setNotificationsOpen(false)}><aside id="vendor-notifications-dialog" className="vendor-notification-drawer" aria-labelledby="vendor-notification-title" onClick={event => event.stopPropagation()}><button className="vendor-notification-close" aria-label={t("nav.close")} onClick={() => setNotificationsOpen(false)}><X size={18}/></button><VendorActivity compact onApplication={id => {navigate("vendor-requests"); setFocusedRequestId(id); window.history.replaceState({}, "", `/vendor/requests?request=${encodeURIComponent(id)}`);}} onSlot={() => {navigate("vendor-dashboard"); setOpenOwnSlot(value => value + 1);}}/></aside></div>}
  </div>;
}

import "../styles/foundation.css";
