"""Mechanism and leakage checks; never assert improved national validation scores."""
import copy
import unittest
import numpy as np
import pandas as pd
from tests.test_shared_dynamic_stock import fixture
from gfa_science_v2 import b0_shock_response as m
from v7 import shared_dynamic_stock as b0
from v7 import observed_driver_extension as observed


class ShockResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel, cls.obs, cls.q = fixture()
        for f in observed.FACTORS:
            cls.panel[observed.PREFIX+f] = cls.panel[f]
            cls.panel[observed.PREFIX+f+"__qualified"] = cls.panel[f].notna()

    def test_hinge_zero_orthogonality_and_bounded_tails(self):
        x = np.linspace(-1, 1, 15)
        inputs = {c:{a:(np.roll(x, i), np.ones(15, bool), np.repeat("test", 15)) for a in m.AXES}
                  for i, c in enumerate(["A", "B", "C", "D"])}
        p = m.calibrate(inputs, list(inputs))["activity"]
        self.assertTrue(p["enabled"])
        xx = np.concatenate([inputs[c]["activity"][0][:5] for c in inputs])
        h, _, _ = m.basis(xx, np.ones(len(xx), bool), p)
        self.assertLess(abs(np.mean(xx*h)), 1e-12)
        np.testing.assert_allclose(np.mean(h*h), 1.)
        z, _, outside = m.basis([0., -10., -100., 10., 100.], [True]*5, p)
        self.assertEqual(z[0], 0.); self.assertEqual(z[1], z[2]); self.assertEqual(z[3], z[4])
        self.assertTrue(outside[1:].all())

    def test_zero_hinges_nest_both_controls(self):
        for policy in ["legacy", "observed"]:
            model, *_ = m.fit(self.panel, self.obs, self.q, policy=policy, nonlinear=True)
            engine = b0 if policy == "legacy" else observed
            control, *_ = engine.fit_model(self.panel, self.obs, self.q)
            model["coefficients"] = control["coefficients"]+[0., 0.]
            actual = m.predict(self.panel, model)[0]
            expected = engine.predict_model(self.panel, control)[0]
            for col in ["total_gfa_m2", "residential_gfa_m2", "total_annual_net_change_m2"]:
                np.testing.assert_allclose(actual[col], expected[col], rtol=2e-14, atol=1e-12, equal_nan=True)

    def test_held_country_poison_cannot_change_fit(self):
        a, *_ = m.fit(self.panel, self.obs, self.q, policy="observed", nonlinear=True, excluded=["DDD"])
        panel, obs = self.panel.copy(), self.obs.copy()
        obs.loc[obs.country_id.eq("DDD"), "native_log_ratio_to_2020"] = 999.
        for col in list(self.q)+[observed.PREFIX+f for f in observed.FACTORS]:
            panel.loc[panel.country_id.eq("DDD"), col] = 500.
        b, *_ = m.fit(panel, obs, self.q, policy="observed", nonlinear=True, excluded=["DDD"])
        self.assertEqual(a, b)

    def test_missing_signal_and_causal_post2020_response(self):
        model, *_ = m.fit(self.panel, self.obs, self.q, policy="observed", nonlinear=True)
        panel = self.panel.copy()
        before = m.predict(panel, model)[0]
        for f in observed.FACTORS:
            panel.loc[panel.country_id.eq("EEE") & panel.year.eq(2023), observed.PREFIX+f] = -1.
            panel.loc[panel.country_id.eq("EEE") & panel.year.eq(2023), observed.PREFIX+f+"__qualified"] = True
        after = m.predict(panel, model)[0]
        cols = ["total_gfa_m2", "residential_gfa_m2", "non_residential_gfa_m2"]
        np.testing.assert_allclose(before.loc[before.year.le(2022), cols], after.loc[after.year.le(2022), cols])
        # Verify a changed operator, independently of possibly tiny fitted slopes.
        _, _, c0, _, _, _ = m.operator(self.panel, model)
        _, _, c1, _, _, _ = m.operator(panel, model)
        a = c0.loc[c0.country_id.eq("EEE") & c0.interval_end_year.eq(2023), b0.COEFFICIENTS[4:6]].to_numpy()
        b = c1.loc[c1.country_id.eq("EEE") & c1.interval_end_year.eq(2023), b0.COEFFICIENTS[4:6]].to_numpy()
        self.assertGreater(float(np.max(abs(a-b))), 1e-6)
        missing = panel.copy()
        for f in observed.FACTORS:
            missing.loc[missing.year.gt(2020), observed.PREFIX+f] = np.nan
        _, _, ext = m.predict(missing, model)
        self.assertFalse(ext.extension_role.eq("qualified_latest_vintage_reported_or_estimated_driver").any())
        self.assertFalse(ext.raw_missing_filled.any())

    def test_gradient_and_accounting(self):
        model, *_ = m.fit(self.panel, self.obs, self.q, policy="observed", nonlinear=True)
        states, _, _, _, _, inputs = m.operator(self.panel, model)
        states, _ = m.augment(states, inputs, model["nonlinear_basis"])
        blocks, _ = b0.training_blocks(self.obs, states)
        theta = np.arange(9)*.1
        _, grad, _ = m.objective(theta, states, blocks, True)
        numeric = [(m.objective(theta+np.eye(9)[i]*1e-6, states, blocks)-m.objective(theta-np.eye(9)[i]*1e-6, states, blocks))/2e-6 for i in range(9)]
        np.testing.assert_allclose(grad, numeric, atol=2e-6, rtol=2e-6)
        before = self.panel.copy(deep=True); pred = m.predict(self.panel, model)[0]
        pd.testing.assert_frame_equal(before, self.panel)
        np.testing.assert_allclose(pred.residential_gfa_m2+pred.non_residential_gfa_m2, pred.total_gfa_m2)
        np.testing.assert_array_equal(pred.loc[pred.year.eq(2020), "total_gfa_m2"], 100.)
        np.testing.assert_allclose(pred.groupby("country_id").total_gfa_m2.diff(), pred.total_annual_net_change_m2, equal_nan=True)


if __name__ == "__main__": unittest.main()
