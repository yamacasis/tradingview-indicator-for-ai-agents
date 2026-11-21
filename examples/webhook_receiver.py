#!/usr/bin/env python3
"""
Minimal webhook receiver for AI Agent Lens packets.

TradingView sends JSON to this server. The server validates it and saves it to disk,
where any AI agent (Claude Code, a script, an n8n flow) can read it.

Accepted schemas:
    ai-agent-lens/v1            indicator packet, one per closed candle
    ai-agent-lens-strategy/v1   strategy packet, per candle or per trade event
    ai-agent-lens-order/v1      compact order message from strategy order fills

Files written:
    packets/latest.json                       newest candle packet from any chart
    packets/latest/<SYMBOL>_<TF>.json         newest candle packet per chart
    packets/history.jsonl                     every candle packet, one per line
    packets/orders.jsonl                      every order message, one per line

Standard library only. No installs.

Usage:
    python3 examples/webhook_receiver.py --port 8080 --token CHANGE_ME

Then expose it with HTTPS (TradingView only sends webhooks to ports 80/443), e.g.:
    cloudflared tunnel --url http://localhost:8080
and use  https://<your-tunnel>/webhook?token=CHANGE_ME  as the alert's webhook URL.
"""

import argparse
import hmac
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

INDICATOR_SCHEMA = "ai-agent-lens/v1"
STRATEGY_SCHEMA = "ai-agent-lens-strategy/v1"
ORDER_SCHEMA = "ai-agent-lens-order/v1"
CANDLE_SCHEMAS = {INDICATOR_SCHEMA, STRATEGY_SCHEMA}
SCHEMAS = CANDLE_SCHEMAS | {ORDER_SCHEMA}
# Kept for backwards compatibility with code that imported it
SCHEMA = INDICATOR_SCHEMA

MAX_BODY = 64 * 1024
ORDER_ACTIONS = {"OPEN_LONG", "OPEN_SHORT", "CLOSE_LONG", "CLOSE_SHORT"}

_write_lock = threading.Lock()


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:80] or "unknown"


def validate_packet(packet) -> Optional[str]:
    """Return None if the packet is acceptable, otherwise a short error message."""
    if not isinstance(packet, dict):
        return "body must be a JSON object"
    schema = packet.get("schema")
    if schema not in SCHEMAS:
        return "expected schema one of " + ", ".join(sorted(SCHEMAS))
    for key in ("symbol", "timeframe"):
        if not isinstance(packet.get(key), str) or not packet[key]:
            return f"missing field {key}"
    if schema == ORDER_SCHEMA:
        if packet.get("action") not in ORDER_ACTIONS:
            return "order action must be one of " + ", ".join(sorted(ORDER_ACTIONS))
    elif not isinstance(packet.get("event"), str):
        return "missing field event"
    return None


def store_packet(out_dir: Path, packet: dict, now: Optional[datetime] = None) -> str:
    """Save a validated packet. Returns the kind that was stored ("candle" or "order")."""
    packet["_received_at"] = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    out_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(packet) + "\n"
    with _write_lock:
        if packet["schema"] == ORDER_SCHEMA:
            with (out_dir / "orders.jsonl").open("a") as f:
                f.write(line)
            return "order"
        (out_dir / "latest").mkdir(exist_ok=True)
        chart = safe_name(f"{packet['symbol']}_{packet['timeframe']}")
        text = json.dumps(packet, indent=2)
        (out_dir / "latest.json").write_text(text)
        (out_dir / "latest" / f"{chart}.json").write_text(text)
        with (out_dir / "history.jsonl").open("a") as f:
            f.write(line)
        return "candle"


def token_ok(expected: str, given: str) -> bool:
    if not expected:
        return True
    return hmac.compare_digest(expected.encode(), given.encode())


def handle_body(raw: bytes, out_dir: Path) -> Tuple[int, str]:
    try:
        packet = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 400, "body is not valid JSON"
    error = validate_packet(packet)
    if error:
        return 400, error
    kind = store_packet(out_dir, packet)
    label = packet.get("action") if kind == "order" else packet.get("event")
    print(f"[{packet['_received_at']}] {kind} {label} {packet.get('state_code', packet.get('symbol'))}")
    return 200, "saved"


class Handler(BaseHTTPRequestHandler):
    out_dir: Path = Path("packets")
    token: str = ""

    def _reply(self, code: int, message: str) -> None:
        body = json.dumps({"ok": code == 200, "message": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._reply(200, "AI Agent Lens receiver is running")
        else:
            self._reply(404, "not found")

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path != "/webhook":
            return self._reply(404, "not found")
        if not token_ok(self.token, parse_qs(url.query).get("token", [""])[0]):
            return self._reply(401, "bad token")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            return self._reply(400, "empty or oversized body")
        code, message = handle_body(self.rfile.read(length), self.out_dir)
        self._reply(code, message)

    def log_message(self, *args) -> None:  # keep the console clean
        pass


def make_server(host: str, port: int, out_dir: Path, token: str) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"out_dir": Path(out_dir), "token": token})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Receive AI Agent Lens packets from TradingView.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--token", default="", help="shared secret expected as ?token=... in the webhook URL")
    parser.add_argument("--out", default="packets", help="folder where packets are saved")
    args = parser.parse_args()

    if not args.token:
        print("WARNING: no --token set. Anyone who finds your URL can post packets.")
    server = make_server(args.host, args.port, Path(args.out), args.token)
    print(f"Listening on http://{args.host}:{args.port}/webhook  (saving to {Path(args.out).resolve()})")
    server.serve_forever()


if __name__ == "__main__":
    main()
