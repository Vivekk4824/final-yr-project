import React, {useEffect, useState} from "react";
import {RefreshCw, WifiOff} from "lucide-react";
import BrandIdentity from "../shared/ui/BrandIdentity.jsx";
import {useI18n} from "../i18n/react.jsx";
import {apiRequest} from "../services/api.js";
import "./pwa.css";

export default function ConnectionBoundary({children}) {
  const {t} = useI18n();
  const [connected, setConnected] = useState(() => navigator.onLine !== false);
  const [checking, setChecking] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const retry = async () => {
    if (checking) return;
    setChecking(true);
    try {await apiRequest("/api/health"); setEpoch(value => value + 1); setConnected(true);}
    catch {setConnected(false);}
    finally {setChecking(false);}
  };
  useEffect(() => {
    const offline = () => setConnected(false);
    const restored = () => {setEpoch(value => value + 1); setConnected(navigator.onLine !== false);};
    const pageshow = event => {if (event.persisted) restored();};
    window.addEventListener("offline", offline);
    window.addEventListener("vendormap:connection-lost", offline);
    window.addEventListener("online", restored);
    window.addEventListener("pageshow", pageshow);
    return () => {window.removeEventListener("offline", offline); window.removeEventListener("online", restored); window.removeEventListener("vendormap:connection-lost", offline); window.removeEventListener("pageshow", pageshow);};
  }, []);
  if (connected) return <React.Fragment key={epoch}>{children}</React.Fragment>;
  return <main className="pwa-offline"><div className="pwa-offline-content"><BrandIdentity/><WifiOff className="pwa-offline-symbol" size={30} aria-hidden="true"/><h1>{t("pwa.offlineTitle")}</h1><p>{t("pwa.offlineText")}</p><button onClick={retry} disabled={checking}><RefreshCw size={17} aria-hidden="true"/>{t(checking ? "common.loading" : "pwa.retry")}</button></div></main>;
}
