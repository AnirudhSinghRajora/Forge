// Map shortcuts for documented events (docs/validation/events.md). Each one only moves the map:
// it creates no case, no polygon and no evidence, and the reader confirms everything.
export interface Place {
  id: string;
  lat: number;
  lon: number;
  zoom: number;
  eventDate: string; // preselects the date field at Confirm, where the reader checks it
  /** Set when this spot was chosen from a scan, so the choice is disclosed wherever it is used. */
  selected?: { hi: string; te: string; en: string };
  label: { hi: string; te: string; en: string };
}

export const PLACES: Place[] = [
  {
    id: "bhiwani-hail-2024",
    lat: 28.700911,
    lon: 76.215719,
    zoom: 15,
    eventDate: "2024-03-02",
    label: { hi: "ओले, भिवानी (मार्च 2024)", te: "వడగళ్లు, భివానీ (మార్చి 2024)", en: "Hail, Bhiwani (March 2024)" },
    selected: {
      hi: "यह खेत चुना हुआ है: उस पट्टी के स्कैन किए 200 खेतों में सबसे ज़्यादा गिरावट वाला। यह आम खेत नहीं है।",
      te: "ఈ పొలం ఎంపిక చేసినది: ఆ పట్టీలో స్కాన్ చేసిన 200 పొలాలలో అత్యధిక తగ్గుదల ఉన్నది. ఇది సాధారణ పొలం కాదు.",
      en: "This plot was selected: the strongest of 200 scanned in that band. It is not a typical field.",
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

/** The disclosure for a result whose plot sits on a selected spot (within about 300 m). */
export function selectionNear(lon: number, lat: number): Place["selected"] | null {
  for (const p of PLACES) {
    if (p.selected && Math.abs(p.lat - lat) < 0.003 && Math.abs(p.lon - lon) < 0.003) return p.selected;
  }
  return null;
}
