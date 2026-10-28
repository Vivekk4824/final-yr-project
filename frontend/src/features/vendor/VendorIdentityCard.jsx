import React, {useMemo} from "react";
import mark from "../../assets/vendormap-mark.svg?raw";
import {categoryLabel} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";
import {buildIdentityCard} from "./identityCard.js";

export function useIdentityCard(profile, photo, zoneId) {
  const {language, t} = useI18n();
  return useMemo(() => profile ? buildIdentityCard({profile, photo, zoneId, mark, category: categoryLabel(language, profile.business_category), labels: {vendor: t("identity.registeredVendor"), identifier: t(profile.vendor_type === "NEW" ? "card.applicationReference" : "card.vendorReference"), zone: t("card.currentZone"), noZone: t("card.noZone"), notice: t("card.notice")}}) : "", [profile, photo, zoneId, language, t]);
}

export default function VendorIdentityCard({svg}) {
  const {t} = useI18n();
  return <details className="vm-identity-preview"><summary>{t("card.title")}</summary><img className="vm-identity-card" src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`} alt={t("card.title")} width="640" height="620"/></details>;
}
