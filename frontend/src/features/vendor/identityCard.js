import {publicVendorId} from "../../shared/utils/profileIdentity.js";

const escapeXml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&apos;"}[c]));
export function cardLines(value, length = 26, limit = 2) {
  const lines = [];
  let line = "";
  for (const word of String(value ?? "").trim().split(/\s+/u)) {
    if (!word) continue;
    const units = Array.from(word);
    if (line && Array.from(`${line} ${word}`).length > length) {lines.push(line); line = "";}
    while (units.length > length) {lines.push(units.splice(0, length).join(""));}
    line = line ? `${line} ${units.join("")}` : units.join("");
  }
  if (line) lines.push(line);
  const truncated = lines.length > limit;
  return lines.slice(0, limit).map((text, i) => truncated && i === limit - 1 ? `${Array.from(text).slice(0, length - 1).join("")}…` : text);
}

export function buildIdentityCard({profile, photo, category, zoneId, mark, labels}) {
  const name = profile.full_name || labels.vendor;
  const initials = name.trim().split(/\s+/u).slice(0, 2).map(part => Array.from(part)[0]).join("").toLocaleUpperCase();
  const textLines = (value, x, y, size, width, fill, weight = 500) => `<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${cardLines(value, width).map((line, i) => `<tspan x="${x}" dy="${i ? size * 1.3 : 0}">${escapeXml(line)}</tspan>`).join("")}</text>`;
  const portrait = photo && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(photo)
    ? `<image href="${escapeXml(photo)}" x="40" y="150" width="88" height="88" preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait)"/>`
    : `<rect x="40" y="150" width="88" height="88" rx="22" fill="#DFEDB4"/><text x="84" y="208" text-anchor="middle" font-size="32" font-weight="700" fill="#244E3D">${escapeXml(initials)}</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="620" viewBox="0 0 640 620"><defs><clipPath id="portrait"><rect x="40" y="150" width="88" height="88" rx="22"/></clipPath></defs><g font-family="'Segoe UI','Nirmala UI',Arial,sans-serif"><rect x="1" y="1" width="638" height="618" rx="30" fill="#FFFEFA" stroke="#DDDFD3" stroke-width="2"/><path d="M30 1h580a29 29 0 0 1 29 29v74H1V30A29 29 0 0 1 30 1Z" fill="#F0F2E9"/>${mark.replace('<svg ', '<svg x="36" y="26" width="52" height="52" ')}<text x="103" y="62" fill="#244E3D" font-size="32" font-weight="750">VendorMap<tspan fill="#BD653C">.</tspan></text><rect x="532" y="44" width="22" height="7" rx="3.5" fill="#D47C54"/><rect x="560" y="44" width="22" height="7" rx="3.5" fill="#466B83"/>${portrait}${textLines(name, 152, 180, 32, 24, '#203B30', 650)}${textLines(profile.business_name || category, 40, 292, 25, 40, '#646C62')}<path d="M40 329h560" stroke="#DDDFD3"/>${textLines(labels.identifier, 40, 374, 21, 48, '#646C62')}${textLines(publicVendorId(profile), 40, 421, 30, 32, '#244E3D', 700)}${textLines(labels.zone, 40, 477, 21, 48, '#646C62')}${textLines(zoneId || labels.noZone, 40, 519, 27, 37, '#203B30', 600)}<path d="M40 555h560" stroke="#DDDFD3"/>${textLines(labels.notice, 40, 588, 18, 58, '#646C62')}</g></svg>`;
}
