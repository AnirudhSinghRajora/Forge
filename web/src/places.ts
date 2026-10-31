// Map shortcuts for documented events (docs/validation/events.md). Each one only moves the map:
// it creates no case, no polygon and no evidence, and the reader confirms everything.
export interface Place {
  id: string;
  lat: number;
  lon: number;
  zoom: number;
  eventDate: string; // preselects the date field at Confirm, where the reader checks it
  /** Said when the shortcut is pressed, before any case exists. A result's note comes from the server. */
  selected?: { hi: string; te: string; en: string };
  label: { hi: string; te: string; en: string };
}

export const PLACES: Place[] = [
  {
    id: "bhiwani-typical",
    lat: 28.715212,
    lon: 76.231138,
    zoom: 15,
    eventDate: "2024-03-03",
    label: { hi: "ओले, भिवानी 2024: आम खेत (नियम से चुना)", te: "వడగళ్లు, భివానీ 2024: సాధారణ పొలం (నియమంతో ఎంపిక)", en: "Hail, Bhiwani 2024: typical plot (chosen by rule)" },
    selected: {
      hi: "यह खेत नियम से चुना गया है, नतीजा देखकर नहीं: उस पट्टी के 40 यादृच्छिक खेतों में बीच वाला (मध्यिका)।",
      te: "ఈ పొలాన్ని ఫలితం చూసి కాదు, నియమం ప్రకారం ఎంచుకున్నాం: ఆ పట్టీలోని 40 యాదృచ్ఛిక పొలాలలో మధ్యస్థమైనది.",
      en: "This plot was chosen by rule, not for its result: the median of 40 random plots from the band.",
    },
  },
  {
    id: "bhiwani-strongest",
    lat: 28.700911,
    lon: 76.215719,
    zoom: 15,
    eventDate: "2024-03-03",
    label: { hi: "ओले, भिवानी 2024: 200 में सबसे ज़्यादा गिरा खेत", te: "వడగళ్లు, భివానీ 2024: 200లో అత్యధికంగా తగ్గిన పొలం", en: "Hail, Bhiwani 2024: strongest of 200 scanned" },
    selected: {
      hi: "यह खेत एक स्कैन से चुना गया है: इस इलाके में स्कैन किए गए 200 यादृच्छिक खेतों में सबसे ज़्यादा गिरावट वाला। यह आम खेत नहीं है।",
      te: "ఈ పొలాన్ని స్కాన్ నుంచి ఎంచుకున్నాం: ఈ ప్రాంతంలో స్కాన్ చేసిన 200 యాదృచ్ఛిక పొలాలలో అత్యధిక తగ్గుదల ఉన్నది. ఇది సాధారణ పొలం కాదు.",
      en: "This plot was picked from a scan: the strongest of 200 random plots scanned in this area. It is not a typical field.",
    },
  },
  {
    id: "arnab-godavari",
    lat: 16.45,
    lon: 81.9,
    zoom: 12,
    eventDate: "2026-10-28",
    label: { hi: "चक्रवात अर्णब, गोदावरी", te: "ఆర్నబ్ తుఫాను, గోదావరి", en: "Cyclone Arnab, Godavari" },
  },
  {
    id: "ratia-fatehabad-hail",
    lat: 29.68469,
    lon: 75.56926,
    zoom: 12,
    eventDate: "2026-10-24",
    label: { hi: "ओले, रतिया, फ़तेहाबाद", te: "వడగళ్లు, రతియా, ఫతేహాబాద్", en: "Hail, Ratia, Fatehabad" },
  },
];
