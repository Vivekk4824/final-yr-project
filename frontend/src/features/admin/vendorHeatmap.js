const EARTH_RADIUS_METRES = 6371008.8;

const radians = degrees => degrees * Math.PI / 180;

export function distanceMetres(first, second) {
  const latitudeDelta = radians(second.latitude - first.latitude);
  const longitudeDelta = radians(second.longitude - first.longitude);
  const firstLatitude = radians(first.latitude);
  const secondLatitude = radians(second.latitude);
  const haversine = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(firstLatitude) * Math.cos(secondLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return 2 * EARTH_RADIUS_METRES * Math.asin(Math.sqrt(haversine));
}

export function vendorsWithinRadius(points, center, radiusMetres) {
  if (!center || !Number.isFinite(radiusMetres)) return [];
  return points.filter(point => distanceMetres(center, point) <= radiusMetres);
}

export function competitionWithinRadius(points, center, category, radiusMetres) {
  if (!center || !category || !Number.isFinite(radiusMetres)) return [];
  return vendorsWithinRadius(points, center, radiusMetres)
    .filter(point => point.business_category === category);
}

export function groupVendorMarkers(points) {
  const groups = new Map();
  points.forEach(point => {
    const key = `${point.latitude.toFixed(7)}:${point.longitude.toFixed(7)}`;
    const group = groups.get(key) || {
      key,
      latitude: point.latitude,
      longitude: point.longitude,
      vendors: [],
      categories: {},
    };
    group.vendors.push(point);
    group.categories[point.business_category] = (group.categories[point.business_category] || 0) + 1;
    groups.set(key, group);
  });
  return [...groups.values()];
}
