import React from "react";
import {factorLabel, formatNumber} from "../../i18n/index.js";
import {useI18n} from "../../i18n/react.jsx";

export function RankingContext({zone, locationApplied}) {
  const {language, t} = useI18n();
  const formatDistance = value => formatNumber(language, value, {maximumFractionDigits: 1});
  const reason = zone.ranking_reason;
  let description;
  if (reason?.kind === "mapped_poi") {
    description = t(`recommend.poi.${reason.feature}`, {count: formatNumber(language, reason.count)});
  } else if (reason?.kind === "nearby") {
    description = t("recommend.reasonNearby");
  } else if (reason?.kind === "mcda_factor") {
    description = t("recommend.reasonFactor", {factor: factorLabel(language, reason.factor)});
  }
  let distance = locationApplied ? t("recommend.distanceUnavailable") : null;
  if (zone.distance_km != null) {
    distance = zone.distance_km < 0.1
      ? t("recommend.distanceUnder", {distance: formatDistance(0.1)})
      : t("recommend.approxDistance", {distance: formatDistance(zone.distance_km)});
  }
  return (distance || description) && <p className="field-note vendor-ranking-reason">
    {distance}{distance && description && " · "}{description}
  </p>;
}
