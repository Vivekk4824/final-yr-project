import React from "react";
import {createRoot} from "react-dom/client";
import ImplementationApp from "./app/ImplementationApp.jsx";
import {I18nProvider} from "./i18n/react.jsx";
import ConnectionBoundary from "./pwa/ConnectionBoundary.jsx";
import PwaControls from "./pwa/PwaControls.jsx";
import {startPwa} from "./pwa/runtime.js";
startPwa();
createRoot(document.getElementById("root")).render(<React.StrictMode><I18nProvider><PwaControls/><ConnectionBoundary><React.Suspense fallback={<div className="auth-loading" role="status">Loading VendorMap…</div>}><ImplementationApp/></React.Suspense></ConnectionBoundary></I18nProvider></React.StrictMode>);
