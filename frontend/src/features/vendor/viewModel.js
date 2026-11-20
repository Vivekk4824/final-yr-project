export const PROFILES = ["BALANCED", "COMMERCIAL", "ACCESSIBILITY", "FACILITIES"];
export const LANGUAGES = [{value: "en", label: "English"}, {value: "mr", label: "मराठी"}, {value: "hi", label: "हिंदी"}];
export const RANK_COLORS = {1: "#174b77", 2: "#28658f", 3: "#3b78a3"};
export const pretty = value => (value || "").replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
export const score = (value, missing = "Not available") => value == null || !Number.isFinite(Number(value)) ? missing : Number(value).toFixed(1);
export const displayCapacity = (value, t) => value == null ? t("common.notSpecified") : String(value);

export function suitableZoneSections(data, {search = "", division = "", availability = ""} = {}) {
  const needle = search.trim().toLocaleLowerCase();
  const matches = zone => (!division || zone.zone_division === division)
    && (!availability || (availability === "KNOWN_CAPACITY" ? zone.available_capacity != null && zone.available_capacity > 0 : availability === "UNKNOWN_CAPACITY" ? zone.available_capacity == null : zone.live_status === availability))
    && (!needle || [zone.zone_id, zone.official_description, zone.description, zone.zone_division].some(value => String(value || "").toLocaleLowerCase().includes(needle)));
  const shortlist = new Map((data?.recommendations || []).map((zone, index) => [zone.zone_id, index + 1]));
  const byId = new Map([...(data?.remaining_recommendations || []), ...(data?.recommendations || [])].map(zone => [zone.zone_id, zone]));
  const usesServerRanking = Boolean(data?.location_ranking);
  const scored = [...byId.values()].filter(zone => zone.score != null && Number.isFinite(Number(zone.score)) && zone.eligible !== false)
    .sort((a, b) => {
      if (usesServerRanking) {
        const aHighlight = shortlist.get(a.zone_id) ?? Infinity;
        const bHighlight = shortlist.get(b.zone_id) ?? Infinity;
        return (aHighlight - bHighlight) || (a.rank - b.rank);
      }
      return Number(b.score) - Number(a.score) || (a.zone_id < b.zone_id ? -1 : a.zone_id > b.zone_id ? 1 : 0);
    });
  const ranked = scored.map((zone, index) => ({
    ...zone, rank: index + 1, is_top_three: usesServerRanking ? shortlist.has(zone.zone_id) : index < 3,
  }));
  const unscored = (data?.eligible_unscorable_zones || []).filter(zone => zone.eligible !== false)
    .map(zone => ({...zone, score:null, rank:null, is_top_three:false})).sort((a,b) => a.zone_id.localeCompare(b.zone_id));
  return {scored:ranked.filter(matches), unscored:unscored.filter(matches), totalScored:ranked.length, totalUnscored:unscored.length};
}

export function mergeRecommendationContext(data, context) {
  const byId = new Map([...(data.recommendations || []), ...(data.remaining_recommendations || []), ...(data.eligible_unscorable_zones || [])].map(zone => [zone.zone_id, zone]));
  const zones = new Map((context.zones || []).map(zone => [zone.zone_id, zone]));
  for (const [id, recommendation] of byId) zones.set(id, {...zones.get(id), ...recommendation});
  return {...context, zones: [...zones.values()]};
}

export function latestRecommendationRequest() {
  let sequence = 0;
  return {begin:() => ++sequence, isCurrent:id => id === sequence, invalidate:() => ++sequence};
}

export function indexAiFactorExplanations(result) {
  return new Map((result?.factors || []).map(item => [item.factor, item.explanation]));
}

