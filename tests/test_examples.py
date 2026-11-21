"""Checks that the example files match the documented schemas.

Run:  python3 -m unittest discover -s tests -v
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

REGIMES = {"TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY"}
STRATEGY_EVENTS = {"BAR_CLOSE", "LONG_ENTRY", "SHORT_ENTRY", "ENTRY_FILLED", "PARTIAL_EXIT", "EXIT"}
TRADE_STATUS = {"NONE", "PENDING", "ACTIVE", "TARGET_1_HIT", "TARGET_2_HIT", "STOPPED",
                "STOPPED_AFTER_T1", "BREAKEVEN_AFTER_T1", "TIME_EXIT", "REVERSED"}
EXIT_REASONS = {"T1", "T2", "SL", "BE", "TIME", "REVERSE"}


def load(name):
    return json.loads((EXAMPLES / name).read_text())


class StrategyPacketExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load("sample_strategy_packet.json")

    def test_enums(self):
        self.assertEqual(self.p["schema"], "ai-agent-lens-strategy/v1")
        self.assertIn(self.p["event"], STRATEGY_EVENTS)
        self.assertIn(self.p["regime"], REGIMES)
        self.assertIn(self.p["trade"]["status"], TRADE_STATUS)
        self.assertIn(self.p["trade"]["side"], {"LONG", "SHORT", "FLAT"})
        self.assertIn(self.p["signals"]["combine"], {"Any", "All", "At least N"})

    def test_votes_add_up(self):
        s = self.p["signals"]
        enabled = [m for m in s["modules"] if m["enabled"]]
        self.assertEqual(s["enabled"], len(enabled))
        self.assertEqual(s["long_votes"], sum(m["long"] for m in enabled))
        self.assertEqual(s["short_votes"], sum(m["short"] for m in enabled))
        self.assertLessEqual(s["votes_needed"], max(s["enabled"], 1))

    def test_filters_add_up(self):
        f = self.p["filters"]
        enabled = [i for i in f["items"] if i["enabled"]]
        self.assertEqual(f["long_ok"], all(i["allow_long"] for i in enabled))
        self.assertEqual(f["short_ok"], all(i["allow_short"] for i in enabled))

    def test_long_levels_in_order(self):
        t = self.p["trade"]
        if self.p["last_setup"]["side"] == "LONG":
            self.assertLess(t["stop"], t["entry"])
            self.assertLess(t["entry"], t["target_1"])
            self.assertLess(t["target_1"], t["target_2"])

    def test_fills(self):
        for fill in self.p["fills"]:
            self.assertIn(fill["type"], {"ENTRY", "PARTIAL_EXIT", "EXIT"})
            if fill["type"] != "ENTRY":
                self.assertIn(fill["reason"], EXIT_REASONS)

    def test_state_code_matches(self):
        parts = self.p["state_code"].split("|")
        self.assertEqual(parts[0], "LENS-S")
        self.assertEqual(parts[3], self.p["regime"])
        self.assertEqual(parts[4], f"L{self.p['scores']['long']}")
        self.assertEqual(parts[6], f"V{self.p['signals']['long_votes']}/{self.p['signals']['short_votes']}")
        self.assertEqual(parts[7], f"{self.p['trade']['side']}:{self.p['trade']['status']}")

    def test_contains_indicator_fields(self):
        base = load("sample_packet.json")
        for key in base:
            self.assertIn(key, self.p, f"strategy packet lost indicator field {key}")


class OrderExample(unittest.TestCase):
    def test_order(self):
        o = load("sample_order.json")
        self.assertEqual(o["schema"], "ai-agent-lens-order/v1")
        self.assertIn(o["action"], {"OPEN_LONG", "OPEN_SHORT", "CLOSE_LONG", "CLOSE_SHORT"})
        self.assertGreater(o["qty"], 0)
        if o["action"] == "OPEN_LONG":
            self.assertLess(o["stop"], o["price_ref"])
            self.assertGreater(o["target_2"], o["target_1"])


if __name__ == "__main__":
    unittest.main()
