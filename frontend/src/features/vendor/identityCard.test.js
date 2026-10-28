import test from "node:test";
import assert from "node:assert/strict";
import {buildIdentityCard, cardLines} from "./identityCard.js";

const labels = {vendor:"Vendor", identifier:"Application vendor ID", zone:"Current zone", noZone:"No active allocation", notice:"Profile summary. Not a vending permit."};
test("identity summary uses public application reference and escapes vendor content", () => {
  const svg = buildIdentityCard({profile:{vendor_type:"NEW", vendor_id:"private-account-uuid", application_vendor_id:"APP2026_0042", full_name:'A & B <Shop>'}, mark:"<svg viewBox='0 0 64 64'/>", category:"Food", labels});
  assert.ok(svg.includes("APP2026_0042"));
  assert.ok(!svg.includes("private-account-uuid"));
  assert.ok(svg.includes("A &amp; B &lt;Shop&gt;"));
  assert.ok(svg.includes(labels.notice));
});
test("historical reference stays distinct and non-image URLs cannot enter the card", () => {
  const svg = buildIdentityCard({profile:{vendor_type:"EXISTING_IMPORTED", vendor_id:"V2024_00042", full_name:"Test Vendor"}, photo:'javascript:alert(1)', zoneId:"NN_F_013", mark:"<svg/>", category:"Food", labels});
  assert.ok(svg.includes("V2024_00042"));
  assert.ok(svg.includes("NN_F_013"));
  assert.ok(!svg.includes("javascript:"));
});
test("long names wrap within the card without truncating Unicode code points", () => {
  assert.deepEqual(cardLines("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 8, 2), ["ABCDEFGH", "IJKLMNO…"]);
  const lines = cardLines("विक्रेता नाव आणि व्यवसाय", 12, 2);
  assert.ok(lines.every(line => Array.from(line).length <= 12));
});
