// Map shortcuts for documented events. Each one only moves the map: it creates no case, no
// polygon and no evidence. The team replaces coordinates here with exact locations.
export interface Place {
  id: string;
  lat: number;
  lon: number;
  zoom: number;
  label: { hi: string; te: string; en: string };
}

export const PLACES: Place[] = [
  {
    id: "arnab-godavari",
    lat: 16.6,
    lon: 81.8,
    zoom: 12,
    label: { hi: "चक्रवात अर्णब, गोदावरी", te: "ఆర్నబ్ తుఫాను, గోదావరి", en: "Cyclone Arnab, Godavari" },
  },
  {
    id: "sirsa-hail",
    lat: 29.53,
    lon: 75.03,
    zoom: 12,
    label: { hi: "ओले, सिरसा", te: "వడగళ్లు, సిర్సా", en: "Hailstorm, Sirsa" },
  },
];
