// Client-side geometry for live feedback while drawing. The API's area_ha is authoritative once saved.
const R = 6378137;
const rad = (d: number) => (d * Math.PI) / 180;

export function ringAreaM2(ring: number[][]): number {
  // Spherical excess, as in Chamberlain & Duquette.
  const n = ring.length;
  if (n < 4) return 0;
  let total = 0;
  for (let i = 0; i < n - 1; i++) {
    const [lon1, lat1] = ring[i];
    const [lon2, lat2] = ring[i + 1];
    total += rad(lon2 - lon1) * (2 + Math.sin(rad(lat1)) + Math.sin(rad(lat2)));
  }
  return Math.abs((total * R * R) / 2);
}

export function closeRing(coords: number[][]): number[][] {
  if (coords.length === 0) return coords;
  const a = coords[0];
  const b = coords[coords.length - 1];
  if (a[0] === b[0] && a[1] === b[1]) return coords;
  return [...coords, a];
}

function segmentsCross(a: number[], b: number[], c: number[], d: number[]): boolean {
  const o = (p: number[], q: number[], r: number[]) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const d1 = o(a, b, c);
  const d2 = o(a, b, d);
  const d3 = o(c, d, a);
  const d4 = o(c, d, b);
  return d1 * d2 < 0 && d3 * d4 < 0;
}

export function selfIntersects(ring: number[][]): boolean {
  const n = ring.length - 1;
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      if (segmentsCross(ring[i], ring[i + 1], ring[j], ring[j + 1])) return true;
    }
  }
  return false;
}

export const HA_PER_ACRE = 0.40468564224;
// "Pucca" bigha: 3,025 sq yd = 5/8 acre. Bigha differs by district, and the UI says so beside the number.
export const HA_PER_BIGHA = 0.2529285264;

export function bboxOfRing(ring: number[][]): [number, number, number, number] {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const [x, y] of ring) {
    if (x < w) w = x;
    if (x > e) e = x;
    if (y < s) s = y;
    if (y > n) n = y;
  }
  return [w, s, e, n];
}

export function polygonOutlineOnChip(ring: number[][], bounds: [number, number, number, number]): string {
  // Chips are north-up at small extents, so linear lon/lat scaling lands within a pixel of the image.
  const [w, s, e, n] = bounds;
  return ring
    .map(([x, y]) => `${(((x - w) / (e - w)) * 100).toFixed(3)},${(((n - y) / (n - s)) * 100).toFixed(3)}`)
    .join(" ");
}
