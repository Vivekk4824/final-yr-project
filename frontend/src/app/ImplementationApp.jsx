import VendorActivity from "../features/vendor/VendorActivity.jsx";
import {useDialogFocus} from "../shared/utils/dialogFocus.js";
import React, {useCallback, useEffect, useRef, useState} from "react";
import {ArrowLeft, Bell, Building2, CircleHelp, FileText, Flame, LayoutDashboard, LogOut, MapPin, UserRound, X} from "lucide-react";
const VendorDirectory = React.lazy(() => import("../features/admin/VendorWorkspace.jsx"));
const AdminDashboard = React.lazy(() => import("../features/admin/AdminDashboard.jsx"));
const AuthLanding = React.lazy(() => import("../features/auth/AuthLanding.jsx"));
const VendorPortal = React.lazy(() => import("../features/vendor/VendorPortal.jsx"));
import BrandIdentity from "../shared/ui/BrandIdentity.jsx";
import {getCurrentUser, logout} from "../services/api.js";
import {useI18n} from "../i18n/react.jsx";





const ADMIN_NAV = [
  {id: "admin", title: "Overview", icon: LayoutDashboard},
  {id: "vendors", title: "Vendors", icon: UserRound},
  {id: "zones", title: "Zones & maps", icon: MapPin},
  {id: "heatmap", title: "Vendor Heatmap", icon: Flame},
  {id: "requests", title: "Applications", icon: FileText},
  {id: "map", title: "Vending slots", icon: Building2},
];
const VENDOR_NAV = [
  {id: "vendor-dashboard", titleKey: "nav.dashboard", icon: LayoutDashboard},
  {id: "vendor-recommendations", titleKey: "nav.recommendations", icon: MapPin},
  {id: "vendor-location-insights", titleKey: "nav.locationInsights", icon: Flame},
  {id: "vendor-requests", titleKey: "nav.requests", icon: FileText},
  {id: "vendor-help", titleKey: "help.title", icon: CircleHelp},
  {id: "vendor-profile", titleKey: "nav.profile", icon: UserRound},
];
const VENDOR_PATHS = {
  "vendor-dashboard": "/vendor",
  "vendor-recommendations": "/vendor/recommendations",
  "vendor-location-insights": "/vendor/location-insights",
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
  const [logoutConfirm, setLogoutConfirm] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [checking, setChecking] = useState(true);
  const [sessionError, setSessionError] = useState("");
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [page, setPage] = useState("vendor-dashboard");
  const [recommendationZoneId, setRecommendationZoneId] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [focusedRequestId, setFocusedRequestId] = useState(null);
  const [openOwnSlot, setOpenOwnSlot] = useState(0);
  const [contextualBackVisible, setContextualBackVisible] = useState(false);
  const appRouteHistory = useRef([]);
  useEffect(() => {window.scrollTo({top: 0, behavior: "auto"});}, [page, recommendationZoneId]);
  useDialogFocus(notificationsOpen, ".vendor-notification-drawer");
  useDialogFocus(logoutConfirm, ".vendor-confirm");
  useEffect(() => {
    if (!notificationsOpen) return;
    const close = event => {if (event.key === "Escape") setNotificationsOpen(false);};
    document.addEventListener("keydown", close); return () => document.removeEventListener("keydown", close);
  }, [notificationsOpen]);
  useEffect(() => {
    if (!logoutConfirm) return;
    const close = event => {if (event.key === "Escape" && !loggingOut) setLogoutConfirm(false);};
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [logoutConfirm, loggingOut]);
  const [slotTarget, setSlotTarget] = useState(null);

  const currentPath = () => `${window.location.pathname}${window.location.search}`;
  const replaceCurrentRoute = (path, resetHistory = false) => {
    window.history.replaceState({}, "", path);
    if (resetHistory) appRouteHistory.current = [path];
    else if (appRouteHistory.current.length) appRouteHistory.current[appRouteHistory.current.length - 1] = path;
    else appRouteHistory.current = [path];
  };

  const routeFromPath = next => {
    const pathname = window.location.pathname.replace(/\/+$/, "") || "/";
    if (next?.role === "ADMIN") {
      const match = pathname.match(/^\/admin(?:\/([^/]+))?$/);
      if (!match) return null;
      const id = match[1] || "admin";
      return ADMIN_NAV.some(item => item.id === id) ? {page: id} : null;
    }
    if (next?.role !== "VENDOR") return null;
    const match = pathname.match(/^\/vendor\/recommendations\/([^/]+)$/);
    if (match) return {page: "vendor-recommendation-detail", zoneId: decodeURIComponent(match[1])};
    const vendorPage = Object.entries(VENDOR_PATHS).find(([, path]) => pathname === path)?.[0];
    if (vendorPage) return {page: vendorPage, zoneId: "", requestId: vendorPage === "vendor-requests" ? new URLSearchParams(window.location.search).get("request") : null};
    return null;
  };
  const applySession = (next, {preserveRoute = false} = {}) => {
    if (next?.role === "VENDOR") applyProfileLanguage(next.vendor_profile?.preferred_language);
    setContextualBackVisible(false);
    setSession(next);
    const admin = next?.role === "ADMIN";
    const preserved = preserveRoute ? routeFromPath(next) : null;
    if (preserved) {
      appRouteHistory.current = [currentPath()];
      setPage(preserved.page); setRecommendationZoneId(preserved.zoneId || ""); setFocusedRequestId(preserved.requestId || null);
      return;
    }
    const nextPage = admin ? "admin" : "vendor-dashboard";
    const homePath = admin ? "/admin" : "/vendor";
    setPage(nextPage); setRecommendationZoneId("");
    replaceCurrentRoute(homePath, true);
  };
  useEffect(() => {
    let active = true;
    setChecking(true); setSessionError("");
    getCurrentUser().then(next => {if (active) applySession(next, {preserveRoute: true});}).catch(error => {
      if (!active) return;
      if (error.code === "NETWORK_UNAVAILABLE") return;
      if (error.status === 401) {setSession(null); replaceCurrentRoute("/login", true);}
      else setSessionError(error.message);
    }).finally(() => {if (active) setChecking(false);});
    return () => {active = false;};
  }, [sessionAttempt]);
  useEffect(() => {
    const expired = () => {
      setSession(null); setSessionError(""); setNotificationsOpen(false);
      replaceCurrentRoute("/login", true);
    };
    window.addEventListener("vendormap:session-expired", expired);
    return () => window.removeEventListener("vendormap:session-expired", expired);
  }, []);
  useEffect(() => {
    const handlePopState = () => {
      if (!session) return;
      const route = routeFromPath(session);
      if (route) {
        const path = currentPath();
        const previousIndex = appRouteHistory.current.lastIndexOf(path);
        appRouteHistory.current = previousIndex >= 0
          ? appRouteHistory.current.slice(0, previousIndex + 1)
          : [path];
        setPage(route.page); setRecommendationZoneId(route.zoneId || ""); setFocusedRequestId(route.requestId || null); setNotificationsOpen(false);
      } else {
        const homePage = session.role === "ADMIN" ? "admin" : "vendor-dashboard";
        const homePath = session.role === "ADMIN" ? "/admin" : "/vendor";
        setPage(homePage); setRecommendationZoneId(""); setFocusedRequestId(null); setNotificationsOpen(false);
        replaceCurrentRoute(homePath, true);
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [session]);

  const updateVendorProfile = useCallback(profile => setSession(current => current?.role === "VENDOR" && current.vendor_id === profile.vendor_id ? {...current, vendor_profile: profile} : current), []);
  const signOut = async () => {
    setLogoutError(""); setLoggingOut(true);
    try {await logout();} catch (err) {setLogoutError(err.message); setLoggingOut(false); return;}
    setLogoutConfirm(false); setLoggingOut(false);
    setSession(null); setPage("vendor-dashboard"); setRecommendationZoneId(""); replaceCurrentRoute("/login", true);
  };
  const refreshSession = async () => applySession(await getCurrentUser());
  const navigate = id => {
    const allowed = (session?.role === "ADMIN" ? ADMIN_NAV : VENDOR_NAV).some(item => item.id === id) || (session?.role === "VENDOR" && id === "vendor-settings");
    const safe = allowed ? id : session?.role === "ADMIN" ? "admin" : "vendor-dashboard";
    setPage(safe); setRecommendationZoneId(""); setNotificationsOpen(false);
    if (safe !== "vendor-requests") setFocusedRequestId(null);
    const path = session?.role === "ADMIN" ? `/admin/${safe}` : VENDOR_PATHS[safe] || "/vendor";
    if (currentPath() !== path) {
      if (!appRouteHistory.current.length) appRouteHistory.current = [currentPath()];
      appRouteHistory.current.push(path);
      window.history.pushState({}, "", path);
    } else if (!appRouteHistory.current.length) appRouteHistory.current = [path];
  };
  const openRecommendation = zoneId => {
    const path = `/vendor/recommendations/${encodeURIComponent(zoneId)}`;
    setRecommendationZoneId(zoneId); setPage("vendor-recommendation-detail");
    if (!appRouteHistory.current.length) appRouteHistory.current = [currentPath()];
    appRouteHistory.current.push(path);
    window.history.pushState({}, "", path);
  };
  const backToRecommendations = () => {
    const recommendationsPath = VENDOR_PATHS["vendor-recommendations"];
    if (appRouteHistory.current.length > 1 && appRouteHistory.current.at(-2) === recommendationsPath) {
      appRouteHistory.current.pop();
      window.history.back();
      return;
    }
    setRecommendationZoneId(""); setPage("vendor-recommendations");
    replaceCurrentRoute(recommendationsPath);
  };
  const goBack = () => {
    setNotificationsOpen(false);
    if (appRouteHistory.current.length > 1) {
      appRouteHistory.current.pop();
      window.history.back();
      return;
    }
    const homePage = session?.role === "ADMIN" ? "admin" : "vendor-dashboard";
    const homePath = session?.role === "ADMIN" ? "/admin" : "/vendor";
    setPage(homePage); setRecommendationZoneId(""); setFocusedRequestId(null);
    replaceCurrentRoute(homePath);
  };
  const logoutDialog = logoutConfirm && <div className="vendor-confirm-backdrop" onClick={() => !loggingOut && setLogoutConfirm(false)}><div className="vendor-confirm" role="dialog" aria-modal="true" aria-labelledby="logout-confirm-title" onClick={event => event.stopPropagation()}><div className="confirm-icon danger"><LogOut size={24}/></div><span className="vendor-eyebrow">{t("nav.logout")}</span><h2 id="logout-confirm-title">{t("confirm.logoutTitle")}</h2><p>{t("confirm.logoutHelp")}</p>{logoutError && <p role="alert" className="vendor-action-notice">{logoutError}</p>}<div className="confirm-actions"><button className="vendor-secondary" type="button" onClick={() => setLogoutConfirm(false)} disabled={loggingOut}>{t("confirm.staySignedIn")}</button><button className="vendor-danger" type="button" onClick={signOut} disabled={loggingOut}>{t(loggingOut ? "confirm.loggingOut" : "confirm.logout")}</button></div></div></div>;
  if (checking) return <div className="auth-loading"><Building2 size={28}/><span>{t("common.loading")}</span></div>;
  if (sessionError) return <main className="auth-loading"><p role="alert">{sessionError}</p><button onClick={() => setSessionAttempt(value => value + 1)}>{t("pwa.retry")}</button></main>;
  if (!session) return <AuthLanding onAuthenticated={applySession}/>;

  const onboarding = session.role === "NEW_VENDOR_ONBOARDING";
  if (onboarding) return <div className="onboarding-shell vendormap">{logoutError && <p role="alert" className="vendor-action-notice">{logoutError}</p>}<VendorPortal onboarding onBack={signOut} onLogout={() => {setLogoutError(""); setLogoutConfirm(true);}} onRegistered={refreshSession}/>{logoutDialog}</div>;

  const nav = session.role === "ADMIN" ? ADMIN_NAV : VENDOR_NAV;
  const navTitle = item => session.role === "ADMIN" ? item.title : t(item.titleKey);
  const showGenericBack = !contextualBackVisible
    && (appRouteHistory.current.length > 1 || page !== (session.role === "ADMIN" ? "admin" : "vendor-dashboard"));
  return <div className={`implementation-shell service-app vendormap ${session.role === "ADMIN" ? "officer-app" : "vendor-app"}`}>
    <a className="skip-link" href="#main-content">{t("vm.skip")}</a>
    <header className="vm-header">
      <BrandIdentity compact subtitle={session.role === "ADMIN" ? "NMC · Officer workspace" : "Nashik"}/>
      <nav className="vm-nav" aria-label={t("portal.main")}>{nav.filter(item => item.id !== "vendor-help").map(item => {
        const active = page === item.id || (item.id === "vendor-recommendations" && page === "vendor-recommendation-detail") || (item.id === "vendor-profile" && page === "vendor-settings");
        return <button key={item.id} aria-current={active ? "page" : undefined} className={active ? "active" : ""} onClick={() => navigate(item.id)}><item.icon size={18}/><span>{navTitle(item)}</span></button>;
      })}</nav>
      <div className="vm-utilities">
        {session.role === "VENDOR" && <><button aria-label={t("help.title")} title={t("help.title")} onClick={() => navigate("vendor-help")}><CircleHelp size={20}/></button><button aria-label={t("activity.title")} aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen(value => !value)}><Bell size={20}/></button></>}
        <button aria-label={t("nav.logout")} title={t("nav.logout")} onClick={() => {setLogoutError(""); setLogoutConfirm(true);}}><LogOut size={19}/></button>
      </div>
    </header>
    <div className="implementation-content">{showGenericBack && <div className="vm-page-toolbar"><button className="vm-page-back" type="button" onClick={goBack}><ArrowLeft size={17}/><span>{t("nav.back")}</span></button></div>}<div className="implementation-view" id="main-content" tabIndex={-1}>
    {logoutError && <p role="alert" className="vendor-action-notice">{logoutError}</p>}
    {(session.role === "VENDOR" || onboarding) && <VendorPortal key={session.vendor_id} onProfileUpdated={updateVendorProfile} onContextualBackChange={setContextualBackVisible} focusRequestId={focusedRequestId} openOwnSlot={openOwnSlot} sessionProfile={session.vendor_profile} onboarding={onboarding} view={page} detailZoneId={recommendationZoneId} onNavigate={navigate} onOpenRecommendation={openRecommendation} onBackRecommendations={backToRecommendations} onRegistered={refreshSession}/>}
    {session.role === "ADMIN" && page !== "vendors" && <AdminDashboard adminId={session.admin_id} slotTarget={slotTarget} section={page === "admin" ? "overview" : page} onContextualBackChange={setContextualBackVisible} onSectionChange={id => navigate(id === "overview" ? "admin" : id)}/>}
    {session.role === "ADMIN" && page === "vendors" && <VendorDirectory onViewSlot={slot => {setSlotTarget({...slot}); navigate("map");}}/>}
  </div></div>
  {session.role === "VENDOR" && notificationsOpen && <div className="vendor-notification-backdrop" onClick={() => setNotificationsOpen(false)}><aside id="vendor-notifications-dialog" className="vendor-notification-drawer" role="dialog" aria-modal="true" aria-labelledby="vendor-notification-title" onClick={event => event.stopPropagation()}><button className="vendor-notification-close" aria-label={t("nav.close")} onClick={() => setNotificationsOpen(false)}><X size={18}/></button><VendorActivity compact onApplication={id => {navigate("vendor-requests"); setFocusedRequestId(id); replaceCurrentRoute(`/vendor/requests?request=${encodeURIComponent(id)}`);}} onSlot={() => {navigate("vendor-dashboard"); setOpenOwnSlot(value => value + 1);}}/></aside></div>}
  {logoutDialog}
  </div>;
}

import "../styles/foundation.css";
import "../styles/vendormap.css";
