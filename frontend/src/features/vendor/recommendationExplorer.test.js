import test from "node:test";
import assert from "node:assert/strict";
import {suitableZoneSections, mergeRecommendationContext, latestRecommendationRequest} from "./viewModel.js";
import {buildVendorExplorerMapModel} from "../../shared/utils/mapGrouping.js";
import {translate} from "../../i18n/index.js";

const a = {zone_id:"NN_F_013",score:80,zone_division:"Nashik Road",official_description:"Lekha Nagar",live_status:"OPEN",available_capacity:7};
const b = {zone_id:"PAN_F_019",score:80,zone_division:"Panchavati",official_description:"Dattanagar Garden",live_status:"OPEN",available_capacity:10};
const c = {zone_id:"SAT_F_014",score:90,zone_division:"Satpur",official_description:"Gangapur Gaon",live_status:"OPEN",available_capacity:null};
const unscored = {zone_id:"UNSCORED",score:null,rank:0,zone_division:"Satpur",live_status:"OPEN",available_capacity:3};
const data = {recommendations:[a,b],remaining_recommendations:[c,a],eligible_unscorable_zones:[unscored]};

test("personalized score order, stable tie-breaks and Top 3 survive filtering", () => {
  const all = suitableZoneSections(data);
  assert.deepEqual(all.scored.map(zone => zone.zone_id),[c.zone_id,a.zone_id,b.zone_id]);
  assert.deepEqual(all.scored.map(zone => zone.rank),[1,2,3]);
  const filtered = suitableZoneSections(data,{search:"Dattanagar"});
  assert.equal(filtered.scored[0].rank,3);
  assert.equal(filtered.scored[0].is_top_three,true);
  assert.equal(filtered.totalScored,3);
});

test("unscoreable eligibility stays accessible without numerical score or rank", () => {
  const sections = suitableZoneSections(data);
  assert.equal(sections.unscored.length,1);
  assert.equal(sections.unscored[0].score,null);
  assert.equal(sections.unscored[0].rank,null);
  assert.equal(suitableZoneSections({...data,eligible_unscorable_zones:[{...unscored,eligible:false}]}).unscored.length,0);
});

test("a short nearby shortlist keeps its highlights while the explorer includes all eligible zones", () => {
  const sections = suitableZoneSections({
    recommendations: [{...b, rank: 1}],
    remaining_recommendations: [{...c, rank: 1}, {...a, rank: 2}],
    eligible_unscorable_zones: [unscored],
    location_ranking: {applied: true, radius_km: 1},
  });
  assert.deepEqual(sections.scored.map(zone => zone.zone_id), [b.zone_id, c.zone_id, a.zone_id]);
  assert.deepEqual(sections.scored.map(zone => zone.is_top_three), [true, false, false]);
  assert.equal(sections.unscored.length, 1);
});

test("division, zone ID and operational capacity filters retain honest missing values", () => {
  assert.equal(suitableZoneSections(data,{division:"Satpur"}).scored[0].zone_id,c.zone_id);
  assert.equal(suitableZoneSections(data,{search:"nn_f_013"}).scored[0].zone_id,a.zone_id);
  assert.deepEqual(suitableZoneSections(data,{availability:"UNKNOWN_CAPACITY"}).scored.map(zone => zone.zone_id),[c.zone_id]);
  assert.equal(suitableZoneSections(data,{availability:"KNOWN_CAPACITY"}).unscored.length,1);
  assert.equal(suitableZoneSections(data,{availability:"FULL"}).scored.length,0);
});

test("map/list share zone identities; absent locations never become markers", () => {
  const geometry={type:"FeatureCollection",features:[a,b].map(zone => ({type:"Feature",properties:{zone_id:zone.zone_id},geometry:{type:"Point",coordinates:[73.77,19.97]}}))};
  const sections=suitableZoneSections(data);
  const model=buildVendorExplorerMapModel(sections.scored.filter(zone=>zone.is_top_three),[...sections.scored,...sections.unscored],geometry);
  assert.equal(model.groups.length,1);
  assert.equal(model.groups[0].shared,true);
  assert.deepEqual(new Set(model.unavailableZoneIds),new Set([c.zone_id,unscored.zone_id]));
  const selectedId=b.zone_id;
  const marker=model.groups.find(group=>group.zones.some(zone=>zone.zone_id===selectedId));
  assert.deepEqual(marker.position,[19.97,73.77]);
  assert.equal(sections.scored.find(zone=>zone.zone_id===selectedId).rank,3);
});

test("fresh scoring overlays keep operational locations and availability", () => {
  const context={zones:[{...a,score:12,resolved_location:{coordinates:[73.77,19.97]}},{...unscored,rank:12}],current_zone_id:null};
  const merged=mergeRecommendationContext(data,context);
  assert.equal(merged.zones[0].score,80);
  assert.equal(merged.zones[0].available_capacity,7);
  assert.deepEqual(merged.zones[0].resolved_location.coordinates,[73.77,19.97]);
  assert.equal(merged.zones[1].score,null);
});

test("an older recommendation response cannot replace a newer preference result", () => {
  const requests=latestRecommendationRequest();
  const old=requests.begin(),fresh=requests.begin();
  assert.equal(requests.isCurrent(old),false);
  assert.equal(requests.isCurrent(fresh),true);
  requests.invalidate();
  assert.equal(requests.isCurrent(fresh),false);
});

test("explorer actions and missing-score labels exist in all supported languages", () => {
  for(const language of ["en","mr","hi"]) for(const key of ["explorer.title","explorer.request","explorer.unscored","explorer.search","explorer.map"]) {
    assert.notEqual(translate(language,key),key);
  }
});
