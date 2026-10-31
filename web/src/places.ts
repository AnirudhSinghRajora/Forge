// Map shortcuts for documented events (docs/validation/events.md). Each one only moves the map: it sets
// no date, creates no case and no evidence. What was reported shows as text, with where it was reported,
// and the reader enters their own details.
type Text = { hi: string; te: string; en: string };

export interface Place {
  id: string;
  lat: number;
  lon: number;
  zoom: number;
  label: Text;
  /** What was reported here and when. Text only: it fills in nothing. */
  reported: Text;
  source: { url: string; name: string };
  /** Said when the shortcut is pressed, before any case exists. A result's note comes from the server. */
  selected?: Text;
}

const TRIBUNE_BHIWANI = "https://www.tribuneindia.com/news/haryana/hisar-bhiwani-farmers-suffer-massive-losses-says-report-597645";
const BHIWANI_REPORTED: Text = {
  hi: "ओले की ख़बर: 2-3 मार्च 2024",
  te: "వడగళ్ల నివేదిక: 2-3 మార్చి 2024",
  en: "Hail reported: 2-3 March 2024",
};

export const PLACES: Place[] = [
  {
    id: "bhiwani-typical",
    lat: 28.715212,
    lon: 76.231138,
    zoom: 15,
    label: { hi: "भिवानी: आम खेत (नियम से चुना)", te: "భివానీ: సాధారణ పొలం (నియమంతో ఎంపిక)", en: "Bhiwani: typical plot (chosen by rule)" },
    reported: BHIWANI_REPORTED,
    source: { url: TRIBUNE_BHIWANI, name: "The Tribune" },
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
    label: { hi: "भिवानी: 200 में सबसे ज़्यादा गिरा खेत", te: "భివానీ: 200లో అత్యధికంగా తగ్గిన పొలం", en: "Bhiwani: strongest of 200 scanned" },
    reported: BHIWANI_REPORTED,
    source: { url: TRIBUNE_BHIWANI, name: "The Tribune" },
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
    label: { hi: "गोदावरी: चक्रवात अर्णब का तट", te: "గోదావరి: ఆర్నబ్ తుఫాను తీరం", en: "Godavari: where Cyclone Arnab came ashore" },
    reported: { hi: "चक्रवात की ख़बर: 28 अक्टूबर 2026", te: "తుఫాను నివేదిక: 28 అక్టోబర్ 2026", en: "Cyclone reported: 28 October 2026" },
    source: { url: "https://mausam.imd.gov.in/Forecast/marquee_data/25.%20National%20Bulletin%20No%2025-28Oct2026_0830IST.pdf", name: "IMD" },
  },
  {
    id: "ratia-fatehabad-hail",
    lat: 29.68469,
    lon: 75.56926,
    zoom: 12,
    label: { hi: "रतिया, फ़तेहाबाद", te: "రతియా, ఫతేహాబాద్", en: "Ratia, Fatehabad" },
    reported: { hi: "ओले की ख़बर: 24 अक्टूबर 2026 की शाम", te: "వడగళ్ల నివేదిక: 24 అక్టోబర్ 2026 సాయంత్రం", en: "Hail reported: evening of 24 October 2026" },
    source: { url: "https://www.tribuneindia.com/news/haryana/hailstorm-rain-raise-fears-of-paddy-crop-damage-in-sirsa-fatehabad-districts/", name: "The Tribune" },
  },
];
