import React, {useState, useSyncExternalStore} from "react";
import {Download, RefreshCw, Share, X} from "lucide-react";
import {useI18n} from "../i18n/react.jsx";
import {isIos, isStandalone, pwaSnapshot, reloadForUpdate, requestInstall, subscribePwa} from "./runtime.js";
import "./pwa.css";

const dismissalKey = "vendormap:pwa-install-dismissed";
export default function PwaControls() {
  const {t} = useI18n();
  const pwa = useSyncExternalStore(subscribePwa, pwaSnapshot, pwaSnapshot);
  const [dismissed, setDismissed] = useState(() => {try {return sessionStorage.getItem(dismissalKey) === "1";} catch {return false;}});
  const [guide, setGuide] = useState(false);
  const [busy, setBusy] = useState(false);
  const [updateDismissed, setUpdateDismissed] = useState(false);
  const update = Boolean(pwa.waiting || pwa.updateReady);
  const ios = !pwa.installed && isIos() && !isStandalone();
  if (!window.isSecureContext || (update ? updateDismissed : dismissed || pwa.installed || (!pwa.installEvent && !ios))) return null;
  const dismiss = () => {if (update) {setUpdateDismissed(true); return;} setDismissed(true); try {sessionStorage.setItem(dismissalKey, "1");} catch { /* Optional preference only. */ }};
  const install = async () => {
    if (ios) {setGuide(value => !value); return;}
    setBusy(true);
    const result = await requestInstall();
    setBusy(false);
    if (result !== "accepted") dismiss();
  };
  return <aside className="pwa-strip" aria-label={t(update ? "pwa.updateTitle" : "pwa.installTitle")}>
    <div className="pwa-strip-main">{update ? <RefreshCw size={18} aria-hidden="true"/> : <Download size={18} aria-hidden="true"/>}<span>{t(update ? "pwa.updateText" : "pwa.installText")}</span>
      <button className="pwa-action" disabled={busy} onClick={update ? reloadForUpdate : install} aria-expanded={ios && !update ? guide : undefined}>{t(update ? "pwa.reload" : ios ? "pwa.how" : "pwa.install")}</button>
      <button className="pwa-dismiss" onClick={dismiss} aria-label={t("common.close")}><X size={17}/></button></div>
    {guide && !update && <p className="pwa-ios-guide"><Share size={17} aria-hidden="true"/>{t("pwa.iosGuide")}</p>}
  </aside>;
}
