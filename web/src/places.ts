// Map shortcuts for documented events (docs/validation/events.md). Each one only moves the map:
// it creates no case, no polygon and no evidence, and the reader confirms everything.
export interface Place {
  id: string;
  lat: number;
  lon: number;
  zoom: number;
  eventDate: string; // preselects the date field at Confirm, where the reader checks it
  label: { hi: string; te: string; en: string };
}

export const PLACES: Place[] = [
  {
    id: "bhiwani-hail-2024",
    lat: 28.76654,
    lon: 76.18455,
    zoom: 13,
    eventDate: "2024-03-02",
    label: { hi: "ओले, भिवानी (मार्च 2024)", te: "వడగళ్లు, భివానీ (మార్చి 2024)", en: "Hail, Bhiwani (March 2024)" },
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
