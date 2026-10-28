import React, {useState} from "react";
import VendorDirectory from "./VendorDirectory.jsx";
import RelocationPlanning from "./RelocationPlanning.jsx";

export default function VendorWorkspace({onViewSlot}) {
  const [view, setView] = useState("directory");
  return <div className="vm-vendor-workspace"><nav className="vm-view-switch" aria-label="Vendor workspace"><button aria-current={view === "directory" ? "page" : undefined} aria-pressed={view === "directory"} onClick={() => setView("directory")}>Directory</button><button aria-current={view === "planning" ? "page" : undefined} aria-pressed={view === "planning"} onClick={() => setView("planning")}>Relocation planning</button></nav>{view === "directory" ? <VendorDirectory onViewSlot={onViewSlot}/> : <RelocationPlanning onViewSlot={onViewSlot}/>}</div>;
}
