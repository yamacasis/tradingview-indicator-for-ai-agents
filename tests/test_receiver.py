"""Tests for examples/webhook_receiver.py (standard library only).

Run:  python3 -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import webhook_receiver as wr  # noqa: E402

EXAMPLES = ROOT / "examples"


def load(name):
    return json.loads((EXAMPLES / name).read_text())


class ValidateTests(unittest.TestCase):
    def test_accepts_all_sample_packets(self):
        for name in ("sample_packet.json", "sample_strategy_packet.json", "sample_order.json"):
            with self.subTest(name=name):
                self.assertIsNone(wr.validate_packet(load(name)))

    def test_rejects_unknown_schema(self):
        p = load("sample_packet.json")
        p["schema"] = "something-else/v9"
        self.assertIn("expected schema", wr.validate_packet(p))

    def test_rejects_non_object(self):
        self.assertIsNotNone(wr.validate_packet([1, 2, 3]))
        self.assertIsNotNone(wr.validate_packet("text"))

    def test_rejects_missing_symbol(self):
        p = load("sample_strategy_packet.json")
        del p["symbol"]
        self.assertEqual(wr.validate_packet(p), "missing field symbol")

    def test_rejects_bad_order_action(self):
        o = load("sample_order.json")
        o["action"] = "BUY_EVERYTHING"
        self.assertIn("order action", wr.validate_packet(o))

    def test_candle_packet_needs_event(self):
        p = load("sample_strategy_packet.json")
        del p["event"]
        self.assertEqual(wr.validate_packet(p), "missing field event")

    def test_safe_name(self):
        self.assertEqual(wr.safe_name("BINANCE:BTCUSDT.P_60"), "BINANCE_BTCUSDT.P_60")
        self.assertEqual(wr.safe_name("../../etc/passwd"), ".._.._etc_passwd")
        self.assertEqual(wr.safe_name(""), "unknown")

    def test_token(self):
        self.assertTrue(wr.token_ok("", "anything"))
        self.assertTrue(wr.token_ok("s3cret", "s3cret"))
        self.assertFalse(wr.token_ok("s3cret", "wrong"))
        self.assertFalse(wr.token_ok("s3cret", ""))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "packets"

    def tearDown(self):
        self.tmp.cleanup()

    def test_candle_packets_go_to_latest_and_history(self):
        for name in ("sample_packet.json", "sample_strategy_packet.json"):
            self.assertEqual(wr.store_packet(self.out, load(name)), "candle")
        latest = json.loads((self.out / "latest.json").read_text())
        self.assertEqual(latest["schema"], "ai-agent-lens-strategy/v1")
        self.assertIn("_received_at", latest)
        history = (self.out / "history.jsonl").read_text().splitlines()
        self.assertEqual(len(history), 2)
        per_chart = list((self.out / "latest").iterdir())
        self.assertEqual([p.name for p in per_chart], ["BINANCE_HYPEUSDT.P_60.json"])
        self.assertFalse((self.out / "orders.jsonl").exists())

    def test_orders_go_to_orders_jsonl_only(self):
        self.assertEqual(wr.store_packet(self.out, load("sample_order.json")), "order")
        lines = (self.out / "orders.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(lines[0])["action"], "OPEN_LONG")
        self.assertFalse((self.out / "latest.json").exists())

    def test_handle_body_errors(self):
        self.assertEqual(wr.handle_body(b"not json", self.out)[0], 400)
        self.assertEqual(wr.handle_body(b"\xff\xfe", self.out)[0], 400)
        self.assertEqual(wr.handle_body(b'{"schema":"x"}', self.out)[0], 400)


class HttpTests(unittest.TestCase):
    TOKEN = "test-token"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "packets"
        cls.server = wr.make_server("127.0.0.1", 0, cls.out, cls.TOKEN)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, path, body=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_health(self):
        self.assertEqual(self.request("/health")[0], 200)

    def test_unknown_path(self):
        self.assertEqual(self.request("/nope")[0], 404)
        self.assertEqual(self.request("/nope", {"a": 1})[0], 404)

    def test_bad_token(self):
        code, body = self.request("/webhook?token=wrong", load("sample_order.json"))
        self.assertEqual(code, 401)
        self.assertFalse(body["ok"])

    def test_post_strategy_packet_and_order(self):
        code, body = self.request(f"/webhook?token={self.TOKEN}", load("sample_strategy_packet.json"))
        self.assertEqual((code, body["ok"]), (200, True))
        code, _ = self.request(f"/webhook?token={self.TOKEN}", load("sample_order.json"))
        self.assertEqual(code, 200)
        self.assertTrue((self.out / "latest.json").exists())
        self.assertTrue((self.out / "orders.jsonl").exists())

    def test_invalid_json_rejected(self):
        code, body = self.request(f"/webhook?token={self.TOKEN}", b"{broken")
        self.assertEqual(code, 400)
        self.assertEqual(body["message"], "body is not valid JSON")

    def test_oversized_body_rejected(self):
        big = b"{" + b" " * (wr.MAX_BODY + 1) + b"}"
        code, _ = self.request(f"/webhook?token={self.TOKEN}", big)
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
