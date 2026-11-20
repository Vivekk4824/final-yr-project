import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {preview} from "vite";
import {delay, launchBrowser} from "../tools/browser.mjs";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const root = path.resolve(frontend, "..");
const python = process.env.VENDORMAP_TEST_PYTHON || path.join(root, ".venv", "Scripts", "python.exe");
const backend = spawn(python, [path.join(frontend, "tests", "vendormap-server.py")], {
  cwd: root, windowsHide: true, stdio: ["ignore", "ignore", "pipe"],
  env: {...process.env, LOCATION_RANKING_EXPERIMENT: "true", BUSINESS_AWARE_MCDA_EXPERIMENT: "true"},
});
let backendErrors = "";
backend.stderr.on("data", chunk => {backendErrors += chunk;});
let server, browser;
try {
  for (let attempt = 0; ; attempt++) {
    const ready = await fetch("http://127.0.0.1:8093/api/health", {signal: AbortSignal.timeout(1000)})
      .then(response => response.ok).catch(() => false);
    if (ready) break;
    if (attempt === 80) throw new Error(backendErrors || "API failed to start");
    await delay(250);
  }
  server = await preview({
    root: frontend, configLoader: "runner",
    preview: {host: "127.0.0.1", port: 5193, strictPort: true,
      proxy: {"/api": {target: "http://127.0.0.1:8093", changeOrigin: true}}},
  });
  browser = await launchBrowser();
  console.log("Headless browser connected.");
  const {command, evaluate, waitFor} = browser;
  const api = (url, body, method = body ? "POST" : "GET") => evaluate(`(async () => {
    const response = await fetch(${JSON.stringify(url)}, {method: ${JSON.stringify(method)},
      headers: {"Content-Type": "application/json"}, body: ${body ? JSON.stringify(JSON.stringify(body)) : "undefined"}});
    if (!response.ok) throw Error(await response.text());
    return response.json();
  })()`);
  const click = label => evaluate(`[...document.querySelectorAll("button")].find(button => button.textContent.trim() === ${JSON.stringify(label)}).click()`);
  const mobile = width => command("Emulation.setDeviceMetricsOverride", {
    width, height: 850, deviceScaleFactor: 1, mobile: true,
  });
  await mobile(390);
  await command("Emulation.setTouchEmulationEnabled", {enabled: true});
  await command("Page.navigate", {url: "http://127.0.0.1:5193/"});
  await waitFor("!!document.querySelector('.auth-card')");
  const otp = await api("/api/auth/vendor/request-otp", {mobile: "9999964420"});
  await api("/api/auth/vendor/verify-otp", {challenge_id: otp.challenge_id, otp: "123456"});
  const vendor = await api("/api/vendors", {
    full_name: "Location browser check", business_category: "food", preferred_division: "Nashik East",
    preferred_locality: "Legacy browser fixture",
  });
  await command("Page.reload");
  await waitFor("!!document.querySelector('.vm-find')");
  await click("Find a vending place");
  await waitFor("document.querySelectorAll('.zone-card').length === 3");
  const openPreferences = () => evaluate("document.querySelector('.vendor-recommendations-home details.vendor-panel').open = true");
  await openPreferences();
  assert.deepEqual(await evaluate(`(() => {
    const form = document.querySelector(".vendor-recommendations-home details.vendor-panel form");
    return [form.elements.business_category.options.length, form.elements.preferred_division.options.length,
      form.querySelectorAll("input[type=radio]").length, form.querySelectorAll("input[type=checkbox]").length,
      form.querySelectorAll("input[type=text], input:not([type])").length];
  })()`), [6, 7, 4, 3, 0]);
  await click("Open location map");
  await waitFor("!!document.querySelector('.vendor-location-map')");
  for (const width of [320, 390]) {
    await mobile(width);
    const fit = await evaluate(`(() => {
      const rect = document.querySelector(".vendor-location-map").getBoundingClientRect();
      return rect.width > 180 && rect.height >= 220 && rect.right <= innerWidth
        && document.documentElement.scrollWidth <= innerWidth;
    })()`);
    assert.ok(fit, `Location picker fits ${width}px viewport`);
  }
  const point = await evaluate(`(() => {
    const map = document.querySelector(".vendor-location-map");
    map.scrollIntoView({block: "center"});
    const rect = map.getBoundingClientRect();
    return {x: Math.round(rect.left + .63 * rect.width), y: Math.round(rect.top + .52 * rect.height)};
  })()`);
  await command("Input.dispatchTouchEvent", {type: "touchStart", touchPoints: [point]});
  await command("Input.dispatchTouchEvent", {type: "touchEnd", touchPoints: []});
  await waitFor("!!document.querySelector('.vendor-location-map .leaflet-marker-icon')");
  await evaluate(`(() => {
    const form = document.querySelector(".vendor-recommendations-home details.vendor-panel form");
    const select = (field, value) => {
      field.value = value;
      field.dispatchEvent(new Event("change", {bubbles: true}));
    };
    select(form.elements.business_category, "clothing");
    select(form.elements.preferred_division, "");
    select(form.querySelector(".vendor-working-location select"), "1");
    form.querySelector("input[value=COMMERCIAL]").click();
    form.querySelector("input[type=checkbox]").click();
  })()`);
  await click("Save preferences");
  await waitFor("document.body.innerText.includes('Preferences saved.') && !document.querySelector('.recommendation-toolbar button.vendor-secondary').disabled");
  const profile = await api(`/api/vendors/${vendor.vendor_id}`);
  assert.equal(profile.preferred_radius_km, 1);
  assert.equal(profile.business_category, "clothing");
  assert.equal(profile.preferred_division, null);
  assert.equal(profile.priority_profile, "COMMERCIAL");
  assert.equal(profile.market_preference, true);
  assert.equal(profile.preferred_locality, "Legacy browser fixture");
  assert.equal(typeof profile.preferred_latitude, "number");
  assert.equal(typeof profile.preferred_longitude, "number");
  assert.notEqual(profile.preferred_longitude, 73.7898);
  const savedRanking = await api("/api/recommendations", {vendor_id: vendor.vendor_id});
  assert.deepEqual(await evaluate("[...document.querySelectorAll('.zone-card h3')].map(node => node.textContent)"),
    savedRanking.recommendations.map(row => row.zone_id));
  await command("Page.reload");
  await waitFor("!!document.querySelector('.vendor-recommendations-home')");
  await openPreferences();
  await waitFor("document.querySelector('.vendor-working-location select').value === '1' && !document.querySelector('.vendor-location-actions button').disabled");
  await click("Open location map");
  await waitFor("!!document.querySelector('.vendor-location-map .leaflet-marker-icon')");

  await api(`/api/vendors/${vendor.vendor_id}`, {
    preferred_latitude: 19.98, preferred_longitude: 73.60, preferred_division: "Nashik East",
  }, "PATCH");
  await click("Refresh");
  await waitFor("document.body.innerText.includes('0 of 3 recommendations within 1 km.')");
  await click("Expand Search");
  await waitFor("document.querySelectorAll('.zone-card').length === 3");
  assert.match(await evaluate("document.querySelector('.zone-card').innerText"), /Original MCDA suitability[\s\S]*straight-line distance/);
  assert.equal((await api(`/api/vendors/${vendor.vendor_id}`)).preferred_radius_km, 1);
  await click("Use preferred distance");
  await waitFor("document.body.innerText.includes('0 of 3 recommendations within 1 km.')");
  await click("Explore all suitable places");
  await waitFor("document.querySelectorAll('.explorer-zone-card').length > 3");
  assert.match(await evaluate("document.querySelector('.explorer-list').innerText"), /No score|Unscored|Not scored|Score unavailable/i);
  for (const [language, anywhere] of [["mr", "कुठेही"], ["hi", "कहीं भी"]]) {
    await api(`/api/vendors/${vendor.vendor_id}`, {preferred_language: language}, "PATCH");
    await command("Page.reload");
    await waitFor(`document.documentElement.lang === "${language}" && !!document.querySelector('.vendor-recommendations-home')`);
    await openPreferences();
    assert.equal(await evaluate("document.querySelector('.vendor-working-location select').options[0].textContent"), anywhere);
    await waitFor("!!document.querySelector('.vendor-radius-summary') && !document.querySelector('.recommendation-toolbar button.vendor-secondary').disabled");
  }
  assert.deepEqual(browser.errors, []);
  console.log("Six inputs, immediate refresh, mobile pin, saved radius, Expand Search, unscored explorer, and three languages passed.");
} finally {
  try {
    await browser?.close();
    server?.httpServer.closeAllConnections();
    await server?.close();
  } finally {
    backend.kill();
  }
}
