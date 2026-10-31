import { useI18n, keyLabel, hasKeyLabel, cropLabel, type Key, type Lang } from "../i18n";
import { dayLabel } from "../format";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}/;
// Values that are a word from a fixed list, shown in the reader's language.
const WORDS: Record<string, Key> = {
  patchy: "pattern.patchy", uniform: "pattern.uniform", accepted: "qa.accepted", suspect: "qa.suspect", rejected: "qa.rejected",
  farmer: "date_source.farmer", weather_proposed: "date_source.weather_proposed", news: "date_source.news",
  strong: "scale.strong", moderate: "scale.moderate", weak: "scale.weak", insufficient: "scale.insufficient",
  not_damage_likely_harvest: "scale.not_damage_likely_harvest",
  rebutted: "outcome.rebutted", conceded: "outcome.conceded", unresolved: "outcome.unresolved",
};
const AS_WRITTEN = new Set(["district", "state"]);
const SENSORS: Record<string, string> = { s2: "Sentinel-2", s1: "Sentinel-1" };

export interface Fact { key: string; label: string; value: React.ReactNode; missing?: boolean }
export interface RawFact { key: string; text: string }

/** The one rule for machine values: a reader sees a label in their language with a value they can
 * read, and anything else (ids, codes, nested data) waits under the collapsed "technical" control. */
export function splitFacts(
  entries: [string, unknown][], lang: Lang, t: (k: Key) => string, showMissing = false,
): { shown: Fact[]; raw: RawFact[] } {
  const shown: Fact[] = [];
  const raw: RawFact[] = [];
  for (const [key, v] of entries) {
    const asRaw = () => raw.push({ key, text: typeof v === "string" ? v : JSON.stringify(v) ?? "" });
    const last = key.split(".").pop() ?? key;
    const named = hasKeyLabel(key);
    const put = (value: React.ReactNode, missing = false) => shown.push({ key, label: keyLabel(key, lang), value, missing });
    if (v === null || v === undefined) {
      // A comparison that was not run on this sensor is no missing measurement.
      if (showMissing && named && !/^(radar|ring|far)_/.test(key)) put(t("missing.short"), true);
      else if (showMissing) raw.push({ key, text: "null" });
      continue;
    }
    if (!named || /_scene_id$|^scene_id$|_reason$/.test(last)) { asRaw(); continue; }
    if (typeof v === "boolean") put(t(v ? "fact.yes" : "fact.no"));
    else if (typeof v === "number") put(v);
    else if (Array.isArray(v)) {
      if (v.length && typeof v[0] === "object") raw.push({ key, text: JSON.stringify(v) });
      put(v.length);
    } else if (typeof v === "string") {
      if (ISO_DAY.test(v)) put(dayLabel(v.slice(0, 10), lang));
      else if (WORDS[v]) put(t(WORDS[v]));
      else if (SENSORS[v]) put(SENSORS[v]);
      else if (last === "crop") put(cropLabel(v, lang));
      else if (AS_WRITTEN.has(last)) put(v);
      else if (lang === "en" && !/^[a-z0-9]+(_[a-z0-9]+)+$/.test(v)) put(v);
      else asRaw();
    } else asRaw();
  }
  return { shown, raw };
}

export function TechnicalFacts({ raw }: { raw: RawFact[] }) {
  const { t } = useI18n();
  if (raw.length === 0) return null;
  return (
    <details className="fine facts-raw">
      <summary>{t("fact.technical")}</summary>
      <dl className="facts-raw-list" lang="en">
        {raw.map((r) => (
          <div key={r.key}><dt className="mono">{r.key}</dt><dd className="mono break">{r.text}</dd></div>
        ))}
      </dl>
    </details>
  );
}
