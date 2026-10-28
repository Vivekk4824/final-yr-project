import {zoneName} from "../../shared/utils/displayLabels.js";
import React, {useState} from "react";
import {categoryLabel, statusLabel} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";
import {publicSlotCategory} from "./slotPresentation.js";

export default function SlotInspector({selected, slots, selectedId, onSelect, admin, assigned, allocations, ownBusinessCategory, onViewVendor, children, zoneId = "NN_F_013", operationalEnabled = true}) {
  const [expanded,setExpanded] = useState(false);
  const {language,t} = useI18n();
  const allocation = admin && selected?.assigned_vendor_id ? allocations.find(a => a.vendor_id === selected.assigned_vendor_id && a.zone_id === zoneId && a.status === "ACTIVE") : null;
  const category = admin ? allocation?.business_category || selected?.public_business_category : publicSlotCategory(selected,assigned?.slot_id,ownBusinessCategory);
  return <aside className={`pilot-details slot-inspector ${expanded ? "is-expanded" : ""}`} aria-label="Selected slot inspector">
    <button className="slot-sheet-toggle" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{t(expanded ? "display.less" : "display.more")}<span aria-hidden="true">{expanded ? "⌄" : "⌃"}</span></button>
    <div className="slot-inspector-basic" aria-live="polite"><span className="slot-context-label">{selected?.slot_id === assigned?.slot_id ? `${t("display.selectedSlot")} · ${t("display.ownSlot")}` : t("display.selectedSlot")}</span>
      <div className="slot-inspector-title"><h3>{selected?.slot_id || t("display.chooseSlot")}</h3>{selected && <span className={`pilot-status slot-status-${selected.status.toLowerCase()}`}>{statusLabel(language,selected.status)}</span>}</div>
      <strong className="slot-zone-name">{zoneName(zoneId,t("display.zoneMissing"))}</strong><small>{zoneId}</small>
      {!admin && assigned && selected?.slot_id !== assigned.slot_id && <small className="slot-my-assignment">{t("display.ownSlot")}: {assigned.slot_id}</small>}
      {selected && <p className="slot-basic-meta">{selected.width_m ?? 2} × {selected.depth_m ?? 2} m · {category ? categoryLabel(language,category) : t("display.categoryMissing")}</p>}
    </div>
    <div className="slot-inspector-extra"><label>{t("display.selectedSlot")}<select aria-label="Select pilot slot" value={selectedId || ""} onChange={e => {const slot = slots.find(s => s.slot_id === e.target.value); if(slot) onSelect(slot);}}><option value="">{t("display.chooseSlot")}</option>{slots.map(s => <option key={s.slot_id} value={s.slot_id}>{s.slot_id} · {statusLabel(language,s.status)}</option>)}</select></label>
      {!admin && assigned && <p className="slot-own-note">{t("display.ownSlot")}: <strong>{assigned.slot_id}</strong>. {t("display.slotNotice")}</p>}
      {!selected ? <p>Click a numbered polygon or select a slot above.</p> : <>{admin && <dl><div><dt>{t("display.assignedVendor")}</dt><dd>{allocation?.vendor_name || (selected.assigned_vendor_id ? t("identity.registeredVendor") : t("common.none"))}</dd></div>{allocation && <div><dt>{t("display.allocation")}</dt><dd>{allocation.allocation_id}</dd></div>}</dl>}
        {admin && allocation && onViewVendor && <button onClick={() => onViewVendor(allocation)}>{t("display.vendorDetails")}</button>}
        {children}
      </>}
    </div>
  </aside>;
}
