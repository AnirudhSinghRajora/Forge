"""Math only, on tiny synthetic arrays. No network. Fixtures like these are allowed only in tests."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from app.evidence.schema import SceneQA
from app.tools.geo import flatten_numbers, plot_info, utm_epsg
from app.tools.geo import indices as ix
from app.tools.geo.base import PlotError, r4
from app.tools.geo.grid import parse_plot
from app.tools.geo.placebo import PlacementResult, build_placebo_fields, p_value, sample_placements
from app.tools.geo.qa import RawQA, apply_q5, evaluate_optical, evaluate_sar
from app.tools.geo.sar import water_threshold
from app.tools.geo.scale import block_average
from app.tools.geo.twin import field_twin
from app.tools.geo.village import clustering_problem, share_below_half, simulate_surveys


def square(lon=75.03, lat=29.53, side_m=120.0):
    dlat = side_m / 2 / 111_320
    dlon = dlat / np.cos(np.radians(lat))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


class TestOffset:
    @pytest.mark.parametrize("baseline,expected", [("05.13", 1000), ("05.11", 1000), ("04.00", 1000), ("03.01", 0), ("02.14", 0)])
    def test_offset_follows_baseline(self, baseline, expected):
        assert ix.boa_offset(baseline) == expected

    @pytest.mark.parametrize("bad", [None, "", "abc"])
    def test_unknown_baseline_is_an_error_not_a_guess(self, bad):
        with pytest.raises(ValueError):
            ix.boa_offset(bad)

    def test_reflectance_applies_offset_and_masks_nodata(self):
        out = ix.to_reflectance(np.array([0, 1000, 3000], dtype=np.uint16), 1000)
        assert np.isnan(out[0])
        assert out[1] == 0
        assert out[2] == pytest.approx(0.2)

    def test_skipping_the_offset_would_distort_ndvi(self):
        b08, b04 = np.array([4000], dtype=np.uint16), np.array([2000], dtype=np.uint16)
        right = ix.ndvi(ix.to_reflectance(b08, 1000), ix.to_reflectance(b04, 1000))[0]
        wrong = ix.ndvi(ix.to_reflectance(b08, 0), ix.to_reflectance(b04, 0))[0]
        assert right == pytest.approx(0.5)
        assert wrong == pytest.approx(1 / 3)

    def test_negative_reflectance_gives_no_ndvi(self):
        assert np.isnan(ix.ndvi(np.array([-0.08]), np.array([0.02]))[0])


class TestPValue:
    def test_formula(self):
        assert p_value(-0.5, np.array([-0.6, -0.5, -0.1, 0.0])) == (2, 3 / 5)

    def test_extreme_plot_floors_at_one_over_n_plus_one(self):
        k, p = p_value(-1.0, np.linspace(-0.2, 0.2, 199))
        assert k == 0
        assert p == pytest.approx(1 / 200)

    def test_null_is_uniform(self):
        rng = np.random.default_rng(1)
        ps = [p_value(rng.normal(), rng.normal(size=200))[1] for _ in range(3000)]
        assert np.mean(np.array(ps) <= 0.05) == pytest.approx(0.05, abs=0.015)

    def test_under_thirty_placements_has_no_p_value(self):
        res = PlacementResult(np.array([-0.1, 0.0]), np.zeros((2, 2), int), 2, 5, 5)
        fields = build_placebo_fields(res, -0.9, "median_delta_ndvi", 1)
        assert fields["p_value"] == 1.0
        assert "2 comparable" in fields["insufficient_reason"]

    def test_zero_placements_invents_nothing(self):
        res = PlacementResult(np.empty(0), np.empty((0, 2), int), 0, 0, 0)
        fields = build_placebo_fields(res, -0.9, "median_delta_ndvi", 1)
        assert fields["placebo_median"] is None
        assert fields["histogram_counts"] == []


class TestPlacements:
    def setup_method(self):
        self.shape = (120, 120)
        self.mask = np.zeros(self.shape, bool)
        self.mask[55:65, 55:65] = True
        self.ring = np.ones(self.shape, bool)
        self.ring[35:85, 35:85] = False
        self.pre = np.full(self.shape, 0.6, np.float32)
        rng = np.random.default_rng(0)
        self.delta = rng.normal(0, 0.05, self.shape).astype(np.float32)
        self.valid = np.ones(self.shape, bool)

    def run(self, seed=3, **kw):
        args = dict(pre_tolerance=0.15, target=50)
        args.update(kw)
        return sample_placements(self.mask, self.ring, self.valid, self.pre, self.delta, 0.6, seed, **args)

    def test_deterministic_for_a_seed(self):
        a, b = self.run(), self.run()
        assert np.array_equal(a.values, b.values)
        assert np.array_equal(a.offsets, b.offsets)

    def test_seed_changes_placements(self):
        assert not np.array_equal(self.run(seed=3).offsets, self.run(seed=4).offsets)

    def test_placements_stay_in_the_ring(self):
        res = self.run()
        assert res.values.size == 50
        for y, x in res.offsets:
            assert self.ring[y: y + 10, x: x + 10].all()

    def test_first_pass_does_not_overlap(self):
        res = self.run(target=20, allow_overlap=False)
        o = res.offsets
        for i in range(len(o)):
            for j in range(i + 1, len(o)):
                assert abs(o[i, 0] - o[j, 0]) >= 10 or abs(o[i, 1] - o[j, 1]) >= 10

    def test_incomparable_pre_ndvi_is_excluded(self):
        self.pre[:] = 0.2
        assert self.run().values.size == 0

    def test_spread_matching_rejects_a_mixed_placement_for_a_uniform_plot(self):
        # Half bare, half crop: this block's median can still match, but its spread cannot.
        rows, cols = np.indices(self.shape)
        self.pre = np.where((rows + cols) % 2 == 0, 0.6, 0.1).astype(np.float32)
        self.pre[60:, :] = 0.6
        res = self.run(target=30, plot_pre_iqr=0.0, spread_tolerance=0.05)
        assert res.values.size > 0
        assert all(y >= 55 for y, _ in res.offsets)  # a few mixed rows can leave the IQR at 0

    def test_invalid_pixels_block_placements(self):
        self.valid[:] = False
        assert self.run().values.size == 0

    def test_statistic_matches_a_direct_median(self):
        res = self.run(target=5)
        y, x = res.offsets[0]
        assert res.values[0] == pytest.approx(float(np.median(self.delta[y: y + 10, x: x + 10])))

    def test_keeps_a_non_rectangular_shape(self):
        self.mask[:] = False
        self.mask[55:65, 55:60] = True
        self.mask[60:65, 60:65] = True
        n = int(self.mask.sum())
        res = self.run(target=5)
        rows, cols = np.nonzero(self.mask)
        rr, cc = rows - rows.min(), cols - cols.min()
        y, x = res.offsets[0]
        assert res.values[0] == pytest.approx(float(np.median(self.delta[rr + y, cc + x])))
        assert rr.size == n


class TestPattern:
    @pytest.mark.parametrize(
        "drop,iqr,expected",
        [(0.5, 0.2, "patchy"), (0.2, 0.12, "patchy"), (0.8, 0.12, "patchy"), (0.9, 0.05, "uniform"),
         (0.9, 0.2, "none"), (0.5, 0.05, "none"), (0.1, 0.3, "none")],
    )
    def test_rules(self, drop, iqr, expected):
        assert ix.within_plot_pattern(drop, iqr) == expected

    def test_delta_summary(self):
        median, drop, iqr = ix.delta_summary(np.array([-0.3, -0.2, -0.1, 0.0, 0.1]))
        assert median == pytest.approx(-0.1)
        assert drop == pytest.approx(0.4)
        assert iqr == pytest.approx(0.2)

    def test_bare_fraction_needs_low_ndvi_and_positive_bsi(self):
        ndvi = np.array([0.1, 0.1, 0.6, np.nan], np.float32)
        bsi = np.array([0.2, -0.2, 0.2, 0.2], np.float32)
        assert ix.bare_fraction(ndvi, bsi) == pytest.approx(1 / 3)

    def test_clear_mask_buffers_cloud_and_only_admits_water_when_asked(self):
        scl = np.full((9, 9), 4, np.uint8)
        scl[4, 4] = 9
        scl[0, 0] = 6
        m = ix.clear_mask(scl)
        assert not m[4, 4] and not m[4, 6] and m[4, 7]
        assert not m[0, 0]
        assert ix.clear_mask(scl, allow_water=True)[0, 0]


def _healthy(n=100):
    return {
        "B02": np.full((n, n), 1500, np.uint16),
        "B03": np.full((n, n), 1800, np.uint16),
        "B04": np.full((n, n), 1600, np.uint16),
        "B08": np.full((n, n), 4000, np.uint16),
        "B11": np.full((n, n), 2500, np.uint16),
        "SCL": np.full((n, n), 4, np.uint8),
    }


class TestQA:
    def setup_method(self):
        self.mask = np.zeros((100, 100), bool)
        self.mask[40:60, 40:60] = True

    def test_healthy_scene_is_accepted(self):
        raw = evaluate_optical(_healthy(), 1000, self.mask)
        assert raw.status == "accepted" and raw.reasons == []

    def test_28_oct_signature_clean_scl_garbage_radiometry_is_rejected(self):
        # What the real 28 Oct 2026 pass looks like: SCL normal, bands below the offset.
        bands = _healthy()
        bands["B04"][:] = 130
        bands["B08"][:] = 130
        raw = evaluate_optical(bands, 1000, self.mask)
        assert raw.status == "rejected"
        assert any(r.startswith("Q3") and "B08" in r for r in raw.reasons)

    def test_empty_band_is_rejected(self):
        bands = _healthy()
        bands["B02"][:] = 0
        raw = evaluate_optical(bands, 1000, self.mask)
        assert raw.status == "rejected" and any("blue band (B02) is empty" in r for r in raw.reasons)

    def test_ndvi_zero_on_vegetation_fails_q4(self):
        bands = _healthy()
        bands["B04"][:] = 2500
        bands["B08"][:] = 2500
        raw = evaluate_optical(bands, 1000, self.mask)
        assert raw.status == "rejected" and any(r.startswith("Q4") for r in raw.reasons)

    def test_cloudy_plot_fails_q2(self):
        bands = _healthy()
        bands["SCL"][self.mask] = 9
        raw = evaluate_optical(bands, 1000, self.mask)
        assert raw.status == "rejected" and any(r.startswith("Q2") for r in raw.reasons)

    def test_swath_edge_zeros_are_not_corruption(self):
        bands = _healthy()
        for b in bands.values():
            b[:, :30] = 0
        assert evaluate_optical(bands, 1000, self.mask).status == "accepted"

    def test_flooded_plot_is_observed_but_flagged_suspect(self):
        bands = _healthy()
        bands["SCL"][self.mask] = 6
        raw = evaluate_optical(bands, 1000, self.mask)
        assert raw.status == "suspect" and raw.plot_valid_frac == 1.0

    def test_missing_band_rejects(self):
        bands = _healthy()
        bands["B08"] = None
        raw = evaluate_optical(bands, 1000, self.mask)
        assert raw.status == "rejected" and any(r.startswith("Q1") for r in raw.reasons)

    def test_missing_baseline_rejects(self):
        assert evaluate_optical(_healthy(), None, self.mask).status == "rejected"

    def _prev(self, ndvi=0.6, when=date(2026, 10, 18)):
        return SceneQA(id="p", collection="sentinel-2-l2a", date=when, status="accepted", context_ndvi_median=ndvi)

    def test_q5_large_shift_is_suspect(self):
        raw = RawQA("accepted", [], 1.0, 0.1)
        assert apply_q5(raw, date(2026, 10, 23), self._prev()).status == "suspect"

    def test_q5_ignores_scenes_over_ten_days_apart(self):
        raw = RawQA("accepted", [], 1.0, 0.1)
        assert apply_q5(raw, date(2026, 11, 20), self._prev()).status == "accepted"

    def test_sar_qa(self):
        vv = np.full((100, 100), 0.1, np.float32)
        assert evaluate_sar(vv, vv, self.mask).status == "accepted"
        assert evaluate_sar(None, vv, self.mask).status == "rejected"
        gone = vv.copy()
        gone[self.mask] = np.nan
        assert evaluate_sar(gone, vv, self.mask).status == "rejected"


class TestSarMath:
    def test_otsu_on_bimodal_water(self):
        rng = np.random.default_rng(0)
        vv = np.concatenate([rng.normal(-22, 1.0, 4000), rng.normal(-9, 1.5, 12000)])
        t, how = water_threshold(vv, vv)
        assert -20 < t < -12
        assert how.startswith("Otsu")

    def test_land_only_falls_back_to_fixed_threshold(self):
        vv = np.random.default_rng(0).normal(-9, 1.5, 16000)
        t, how = water_threshold(vv, vv)
        assert t == -18.0
        assert how.startswith("fixed")


class TestTwin:
    def test_picks_matching_pixels_and_measures_the_gap(self):
        rows, cols = 40, 40
        dates = [date(2026, 10, d) for d in (1, 6, 11, 16)]
        stack = np.zeros((4, rows, cols), np.float32)
        traj = np.array([0.5, 0.6, 0.7, 0.7], np.float32)
        stack[:] = traj[:, None, None]
        stack[:, 20:, :] = (traj - 0.3)[:, None, None]  # a different crop that must not be matched
        plot = np.zeros((rows, cols), bool)
        plot[:4, :4] = True
        stack[3][plot] = 0.2  # the plot alone collapses after the event
        controls = ~plot
        twin = field_twin(stack, dates, 3, 3, plot, controls, n_controls=100)
        assert twin.n_control_pixels == 100
        assert twin.pre_fit_rmse == pytest.approx(0.0, abs=1e-4)
        assert twin.gap_at_post == pytest.approx(-0.5, abs=1e-3)
        assert twin.series[3].expected == pytest.approx(0.7, abs=1e-3)

    def test_too_few_controls_invents_nothing(self):
        stack = np.full((2, 10, 10), 0.5, np.float32)
        plot = np.zeros((10, 10), bool)
        plot[:2, :2] = True
        twin = field_twin(stack, [date(2026, 10, 1), date(2026, 10, 6)], 1, 1, plot, np.zeros((10, 10), bool))
        assert twin.gap_at_post is None
        assert twin.series[1].expected is None


class TestLottery:
    def test_deterministic_and_without_replacement(self):
        vals = np.arange(50, dtype=float)
        a, da = simulate_surveys(vals, 5, n_simulations=100)
        b, db = simulate_surveys(vals, 5, n_simulations=100)
        assert np.array_equal(a, b) and np.array_equal(da, db)
        assert all(len(set(row.tolist())) == 10 for row in da)
        assert a[0] == pytest.approx(vals[da[0]].mean())

    def test_uniform_field_has_no_spread(self):
        a, _ = simulate_surveys(np.full(40, -0.2), 1, n_simulations=50)
        assert np.allclose(a, -0.2)

    def test_share_below_half(self):
        avgs = np.array([-0.4, -0.3, -0.1, 0.0])
        assert share_below_half(avgs, -0.4, "s2") == pytest.approx(0.5)

    def test_share_is_not_reported_for_a_noise_level_plot(self):
        assert share_below_half(np.array([-0.4, 0.0]), -0.01, "s2") is None
        assert share_below_half(np.array([-4.0, 0.0]), -0.5, "s1") is None

    def test_clustering(self):
        assert clustering_problem(np.array([[0, 0], [1, 1], [2, 2]]), 10) is not None
        spread = np.array([[r, c] for r in range(0, 500, 100) for c in range(0, 500, 100)])
        assert clustering_problem(spread, 10) is None


class TestBlockAverage:
    def test_centre_block_and_nan_handling(self):
        v = np.zeros((30, 30), np.float32)
        v[15, 15] = 9.0
        out, value, lowest = block_average(v, 10, (15, 15))
        assert out.shape == v.shape
        assert value == pytest.approx(0.09)
        assert lowest == pytest.approx(0.0)

    def test_centre_sits_mid_block(self):
        v = np.arange(100, dtype=np.float32).reshape(10, 10)
        out, _, _ = block_average(v, 5, (5, 5))
        assert out[3, 3] == out[7, 7] and out[2, 2] != out[3, 3]

    def test_block_with_too_few_valid_pixels_is_nan(self):
        v = np.full((20, 20), np.nan, np.float32)
        v[10, 10] = -0.3
        _, value, _ = block_average(v, 10, (10, 10))
        assert value is None

    def test_level_one_is_the_map_itself(self):
        v = np.array([[1.0, np.nan], [3.0, 4.0]], np.float32)
        out, value, lowest = block_average(v, 1, (1, 0))
        assert value == 3.0 and lowest == 1.0 and np.isnan(out[0, 1])

    def test_mean_is_preserved_by_blocking_a_real_drop(self):
        v = np.zeros((90, 90), np.float32)
        v[40:50, 40:50] = -0.5
        values = [block_average(v, b, (45, 45))[1] for b in (1, 10, 50, 90)]
        assert values[0] == pytest.approx(-0.5)
        assert values[1] == pytest.approx(-0.5)
        assert values[2] == pytest.approx(-0.02)
        assert values[3] < 0 and abs(values[3]) < abs(values[2])


class TestPolygonRules:
    def test_utm_zone_is_computed(self):
        assert utm_epsg(75.03, 29.53) == 32643
        assert utm_epsg(82.21, 16.73) == 32644

    def test_small_plot_warns_and_large_plot_is_rejected(self):
        assert plot_info(square(side_m=30)).warnings
        assert plot_info(square(side_m=100)).warnings == []
        with pytest.raises(PlotError, match="limit"):
            parse_plot(square(side_m=1000))

    @pytest.mark.parametrize(
        "bad",
        [{"type": "Point", "coordinates": [75, 29]},
         {"type": "Polygon", "coordinates": [[[75, 29], [75.1, 29.1], [75.1, 29], [75, 29.1], [75, 29]]]},
         {"type": "Polygon", "coordinates": [[[200, 29], [200.001, 29], [200.001, 29.001], [200, 29]]]}],
    )
    def test_bad_polygons_are_clear_errors(self, bad):
        with pytest.raises(PlotError):
            parse_plot(bad)

    def test_mask_area_matches_the_polygon(self):
        plot = parse_plot(square(side_m=200))
        grid = plot.grid()
        assert plot.full_mask(grid).sum() == pytest.approx(plot.area_ha * 100, rel=0.1)
        assert plot.stats_mask(grid).sum() < plot.full_mask(grid).sum()
        assert plot.distance_m(grid).max() > 1500


class TestFlatten:
    def test_rounding_and_negative_zero(self):
        assert r4(-0.00001) == 0.0 and str(r4(-0.00001)) == "0.0"
        assert r4(float("nan")) is None
        assert r4(0.123456) == 0.1235

    def test_empty_is_empty(self):
        assert flatten_numbers() == {}
