# Feasibility spikes (31 Oct 2026)

Throwaway scripts used to check the FasalSaakshi evidence assumptions against live Planetary Computer data. **They aren't used at runtime.** Findings are written up in [`docs/plan/03-evidence-engine.md` §0](../docs/plan/03-evidence-engine.md#0-spike-findings-31-oct-2026-scripts-in-spikes).

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install pystac-client planetary-computer odc-stac rioxarray numpy
```

```bash
.venv/bin/python -I spikes/s2_ndvi_by_date.py
```

| Script | What it checks |
|---|---|
| `s2_ndvi_by_date.py` | Per-date NDVI distribution near Sirsa, Oct 2025 vs Oct 2026 (offset-corrected) |
| `s2_raw_band_check.py` | Raw band values for 18 vs 28 Oct 2026, which exposed the corrupted 28 Oct scene |
| `s1_s2_post_event_check.py` | Post-event optical availability and Sentinel-1 RTC backscatter stats |
| `s2_fatehabad_check.py` | Same checks over Fatehabad |
