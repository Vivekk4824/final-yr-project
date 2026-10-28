let state = {installEvent: null, installed: false, waiting: null, updateReady: false};
const listeners = new Set();
let registration;
let started = false;
let requestedReload = false;
const publish = values => {state = {...state, ...values}; listeners.forEach(listener => listener());};
export const subscribePwa = listener => {listeners.add(listener); return () => listeners.delete(listener);};
export const pwaSnapshot = () => state;

export function isStandalone() {
  return typeof window !== "undefined" && (window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true);
}
export function isIos() {
  return /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
}

export function startPwa() {
  if (started || typeof window === "undefined") return;
  started = true;
  publish({installed: isStandalone()});
  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    publish({installEvent: event, installed: isStandalone()});
  });
  window.addEventListener("appinstalled", () => publish({installed: true, installEvent: null}));
  window.matchMedia?.("(display-mode: standalone)").addEventListener?.("change", () => publish({installed: isStandalone()}));
  if (!import.meta.env.PROD || !window.isSecureContext || !("serviceWorker" in navigator)) return;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (requestedReload) {window.location.reload(); return;}
    // Other open windows remain usable until their user chooses Reload.
    if (state.waiting) publish({waiting: null, updateReady: true});
  });
  const register = async () => {
    try {
      registration = await navigator.serviceWorker.register("/sw.js", {scope: "/", updateViaCache: "none"});
      const ready = () => {
        const script = document.querySelector('script[type="module"][src]');
        if (script) registration.active?.postMessage({type: "CLIENT_READY", entry: new URL(script.src).pathname});
      };
      navigator.serviceWorker.ready.then(ready).catch(() => {});
      const inspect = () => {if (registration.waiting && navigator.serviceWorker.controller) publish({waiting: registration.waiting});};
      inspect();
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", inspect);
      });
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && navigator.onLine) {ready(); registration.update().catch(() => {});}
      });
      registration.update().catch(() => {});
    } catch {
      // Registration failure must not interfere with the ordinary online application.
    }
  };
  if (document.readyState === "complete") register();
  else window.addEventListener("load", register, {once: true});
}

export async function requestInstall() {
  const event = state.installEvent;
  if (!event) return "unavailable";
  publish({installEvent: null});
  try {
    await event.prompt();
    const choice = await event.userChoice;
    return choice.outcome;
  } catch {return "unavailable";}
}

export function reloadForUpdate() {
  const waiting = registration?.waiting || state.waiting;
  if (waiting?.state === "installed") {
    requestedReload = true;
    waiting.postMessage({type: "ACTIVATE_UPDATE"});
  } else window.location.reload();
}
