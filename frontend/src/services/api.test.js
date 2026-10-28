import test from "node:test";
import assert from "node:assert/strict";
import {apiRequest, deletePilotSlot, getAllocations, getCapacityPressure, getRecommendationAiExplanation, getRecommendations, getPilotRoute, getVendorRelocationRecommendations, savePilotGeometry} from "./api.js";
import {indexAiFactorExplanations} from "../features/vendor/viewModel.js";

test("shared client includes the session cookie and preserves the endpoint", async t => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8000/api/catalog");
    assert.equal(options.credentials, "include");
    return new Response(JSON.stringify({zones: []}));
  });
  assert.deepEqual(await apiRequest("/api/catalog"), {zones: []});
});

test("slot deletion accepts the API's empty 204 response", async t => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8000/api/pilot/slots/S001?zone_id=NN_F_013&expected_updated_at=2026-10-16T00%3A00%3A00Z");
    assert.equal(options.method, "DELETE");
    return new Response(null, {status: 204});
  });
  assert.equal(await deletePilotSlot("S001", "2026-10-16T00:00:00Z", "NN_F_013"), null);
});

test("allocation list requests only the selected status and page", async t => {
  t.mock.method(globalThis, "fetch", async url => {
    assert.equal(url, "http://127.0.0.1:8000/api/allocations?status=ACTIVE&limit=50&offset=100");
    return new Response(JSON.stringify({allocations: [], count: 0, total_count: 120}));
  });
  assert.equal((await getAllocations("ACTIVE", undefined, {limit: 50, offset: 100})).total_count, 120);
});

test("recommendation request preserves vendor ownership context and preferences", async t => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.ok(url.endsWith("/api/recommendations"));
    assert.equal(options.method, "POST");
    assert.equal(options.credentials, "include");
    assert.deepEqual(JSON.parse(options.body), {
      vendor_id: "V1", exclude_zone: "Z1", business: "food", division: "New Nashik", top_n: 3,
    });
    return new Response(JSON.stringify({recommendations: []}));
  });
  await getRecommendations("V1", "Z1", {business: "food", division: "New Nashik"});
});

test("AI explanation request sends only the selected zone and session cookie", async t => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.ok(url.endsWith("/api/recommendations/NE_F_010/ai-explanation"));
    assert.equal(options.credentials, "include");
    assert.equal(options.body, undefined);
    return new Response(JSON.stringify({source: "gemini", factors: []}));
  });
  await getRecommendationAiExplanation("NE_F_010");
});

test("all six AI explanations remain keyed to their existing factor cards", () => {
  const keys = ["business", "commercial", "access", "facilities", "preference", "historical"];
  const indexed = indexAiFactorExplanations({factors: keys.map(factor => ({factor, explanation: `${factor} prose`}))});
  assert.equal(indexed.size, 6);
  keys.forEach(factor => assert.equal(indexed.get(factor), `${factor} prose`));
});

test("routing preserves WGS84 longitude/latitude and reviewed geometry payloads", async t => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    const body = JSON.parse(options.body);
    if (url.endsWith("/route")) assert.deepEqual(body, {longitude: 73.77, latitude: 19.97});
    else assert.deepEqual(body, {layout: {slots: []}, review_confirmed: true});
    return new Response(JSON.stringify({available: false}));
  });
  await getPilotRoute({longitude: 73.77, latitude: 19.97});
  await savePilotGeometry({slots: []});
});

test("admin planning APIs are read-only GET requests", async t => {
  const seen = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    seen.push([url, options.method]);
    return new Response(JSON.stringify({recommendations: [], zones: []}));
  });
  await getVendorRelocationRecommendations("V2024_00033");
  await getCapacityPressure();
  assert.ok(seen[0][0].endsWith("/api/admin/vendors/V2024_00033/relocation-recommendations?include_all=false"));
  assert.equal(seen[0][1] || "GET", "GET");
  assert.ok(seen[1][0].endsWith("/api/admin/capacity-pressure"));
  assert.equal(seen[1][1] || "GET", "GET");
});

test("shared client reports an unavailable service", async t => {
  t.mock.method(globalThis, "fetch", async () => {throw new TypeError("offline");});
  await assert.rejects(apiRequest("/api/catalog"), /Unable to reach/);
});

test("shared client retains server error detail", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({detail: "Not authorized"}), {status: 403}));
  await assert.rejects(apiRequest("/api/catalog"), /Not authorized/);
});

test("shared client reports malformed responses", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response("not JSON", {status: 502}));
  await assert.rejects(apiRequest("/api/catalog"), /unreadable response \(502\)/);
});
