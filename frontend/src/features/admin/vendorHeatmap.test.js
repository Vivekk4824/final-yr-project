import test from "node:test";
import assert from "node:assert/strict";
import {competitionWithinRadius, distanceMetres, groupVendorMarkers, vendorsWithinRadius} from "./vendorHeatmap.js";

const origin = {latitude: 19.9975, longitude: 73.7898};

test("competition counts only the selected category inside the selected radius", () => {
  const points = [
    {...origin, vendor_id: "A", business_category: "food"},
    {latitude: 19.9980, longitude: 73.7898, vendor_id: "B", business_category: "food"},
    {...origin, vendor_id: "C", business_category: "clothing"},
    {latitude: 20.0100, longitude: 73.7898, vendor_id: "D", business_category: "food"},
  ];
  assert.equal(competitionWithinRadius(points, origin, "food", 100).length, 2);
  assert.equal(competitionWithinRadius(points, origin, "clothing", 100).length, 1);
  assert.deepEqual(competitionWithinRadius(points, origin, "", 100), []);
});

test("nearby vendor count includes all categories within the selected radius", () => {
  const points = [
    {...origin, vendor_id: "A", business_category: "food"},
    {latitude: 19.9980, longitude: 73.7898, vendor_id: "B", business_category: "clothing"},
    {latitude: 20.0100, longitude: 73.7898, vendor_id: "C", business_category: "food"},
  ];
  assert.deepEqual(vendorsWithinRadius(points, origin, 100).map(point => point.vendor_id), ["A", "B"]);
  assert.deepEqual(vendorsWithinRadius(points, null, 100), []);
});

test("haversine distance remains metric and stable around Nashik", () => {
  const north = {latitude: origin.latitude + 0.001, longitude: origin.longitude};
  assert.ok(distanceMetres(origin, north) > 110);
  assert.ok(distanceMetres(origin, north) < 112);
});

test("marker grouping retains real duplicate records without moving coordinates", () => {
  const points = [
    {...origin, vendor_id: "A", business_category: "food"},
    {...origin, vendor_id: "B", business_category: "clothing"},
  ];
  const [group] = groupVendorMarkers(points);
  assert.equal(group.latitude, origin.latitude);
  assert.equal(group.longitude, origin.longitude);
  assert.equal(group.vendors.length, 2);
  assert.deepEqual(group.categories, {food: 1, clothing: 1});
});
