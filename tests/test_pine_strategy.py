"""Static checks for the Pine Script files.

TradingView is the only real Pine compiler, so these tests cannot replace a compile in the
Pine Editor. They catch the mistakes that are easy to make when adding a signal module or a
filter: a module whose toggle input does not exist, a duplicate name, an undocumented module,
packet fields that drift from the documented example, broken brackets, bad indentation,
lookahead leaks, and order ids that do not match.

Run:  python3 -m unittest discover -s tests -v
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = ROOT / "ai-agent-lens-strategy.pine"
INDICATOR = ROOT / "ai-agent-lens.pine"
STRATEGY_DOC = ROOT / "docs" / "STRATEGY.md"
SCHEMA_DOC = ROOT / "docs" / "PACKET_SCHEMA.md"

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def source(path):
    return path.read_text(encoding="utf-8")


def code_lines(text):
    """Yield (line_no, code) with // comments removed (string-aware)."""
    for no, line in enumerate(text.splitlines(), 1):
        yield no, strip_comment(line)


def strip_comment(line):
    out, quote = [], None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif line.startswith("//", i):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def strip_strings(line):
    return re.sub(r'"[^"]*"|\'[^\']*\'', '""', line)


def registrations(text, kind):
    text = "\n".join(code for _, code in code_lines(text))
    pattern = re.compile(kind + r'\.new\(\s*"([^"]+)"\s*,\s*([A-Za-z_][A-Za-z0-9_]*)')
    return pattern.findall(text)


def flatten_keys(obj, keys=None):
    keys = set() if keys is None else keys
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            flatten_keys(v, keys)
    elif isinstance(obj, list):
        for v in obj:
            flatten_keys(v, keys)
    return keys


class CommonPineChecks:
    path = None

    @classmethod
    def setUpClass(cls):
        cls.text = source(cls.path)

    def test_version_6(self):
        self.assertIn("//@version=6", self.text)

    def test_brackets_balanced_per_line(self):
        pairs = {"(": ")", "[": "]", "{": "}"}
        for no, line in code_lines(self.text):
            stack = []
            for ch in strip_strings(line):
                if ch in pairs:
                    stack.append(pairs[ch])
                elif ch in pairs.values():
                    self.assertTrue(stack and stack.pop() == ch, f"line {no}: unbalanced '{ch}'")
            self.assertEqual(stack, [], f"line {no}: unclosed bracket")

    def test_quotes_balanced_per_line(self):
        for no, line in code_lines(self.text):
            rest = re.sub(r'"[^"]*"|\'[^\']*\'', "", line)
            self.assertNotIn('"', rest, f"line {no}: unbalanced double quote")
            self.assertNotIn("'", rest, f"line {no}: unbalanced single quote")

    def test_indentation_is_four_spaces(self):
        for no, line in enumerate(self.text.splitlines(), 1):
            self.assertNotIn("\t", line, f"line {no}: tab character")
            indent = len(line) - len(line.lstrip(" "))
            if line.strip():
                self.assertEqual(indent % 4, 0, f"line {no}: indentation {indent} is not a multiple of 4")

    def test_no_lookahead_leak(self):
        for no, line in code_lines(self.text):
            if "lookahead_on" in line:
                self.assertIn("[1]", line, f"line {no}: lookahead_on without [1] leaks future data")

    def test_every_packet_key_is_documented_in_schema(self):
        doc = source(SCHEMA_DOC)
        keys = set(re.findall(r'\\?"([a-z_0-9]+)\\?":', self.text))
        missing = sorted(k for k in keys if not re.search(rf"[`.]{k}(\[\])?`", doc))
        self.assertEqual(missing, [], "packet keys missing from docs/PACKET_SCHEMA.md")


class IndicatorTests(CommonPineChecks, unittest.TestCase):
    path = INDICATOR

    def test_is_indicator(self):
        self.assertRegex(self.text, r"\nindicator\(")


class StrategyTests(CommonPineChecks, unittest.TestCase):
    path = STRATEGY

    def test_is_strategy_without_repainting_options(self):
        decl = re.search(r"\nstrategy\((.*)\)\n", self.text).group(1)
        self.assertIn("calc_on_every_tick = false", decl)
        self.assertIn("pyramiding = 0", decl)

    def test_no_alertcondition(self):
        # alertcondition() does nothing in a strategy; alerts must use alert() or order messages
        for _, line in code_lines(self.text):
            self.assertNotIn("alertcondition(", line)

    def test_modules_registered_with_existing_bool_inputs(self):
        mods = registrations(self.text, "SignalModule")
        self.assertGreaterEqual(len(mods), 4)
        for name, toggle in mods:
            with self.subTest(module=name):
                self.assertRegex(name, NAME_RE)
                self.assertRegex(self.text, rf"bool\s+{toggle}\s*=\s*input\.bool\(", f"{name}: toggle {toggle} is not an input.bool")

    def test_filters_registered(self):
        filters = registrations(self.text, "FilterModule")
        names = [n for n, _ in filters]
        self.assertIn("direction", names)
        for name, toggle in filters:
            with self.subTest(filter=name):
                self.assertRegex(name, NAME_RE)
                if toggle != "true":
                    self.assertRegex(self.text, rf"bool\s+{toggle}\s*=\s*input\.bool\(")

    def test_names_unique(self):
        for kind in ("SignalModule", "FilterModule"):
            names = [n for n, _ in registrations(self.text, kind)]
            self.assertEqual(len(names), len(set(names)), f"duplicate {kind} name")

    def test_modules_and_filters_documented(self):
        doc = source(STRATEGY_DOC)
        for kind in ("SignalModule", "FilterModule"):
            for name, _ in registrations(self.text, kind):
                self.assertIn(f"`{name}`", doc, f"{name} is not documented in docs/STRATEGY.md")

    def test_extension_markers_present(self):
        for marker in ("ADD NEW MODULE INPUTS HERE", "ADD NEW MODULE CONDITIONS HERE", "ADD NEW MODULES HERE", "ADD NEW FILTERS HERE"):
            self.assertIn(marker, self.text)

    def test_registry_lines_are_global(self):
        for no, line in code_lines(self.text):
            if re.search(r"(modules|filters)\.push\(", line):
                self.assertFalse(line.startswith(" "), f"line {no}: register modules at global scope so they run on every bar")

    def test_order_ids_are_consistent(self):
        entries = set(re.findall(r'strategy\.entry\("([^"]+)"', self.text))
        exits = re.findall(r'strategy\.exit\("([^"]+)",\s*"([^"]+)"', self.text)
        cancels = set(re.findall(r'strategy\.cancel\("([^"]+)"', self.text))
        self.assertEqual(entries, {"Long", "Short"})
        for exit_id, from_entry in exits:
            self.assertIn(from_entry, entries)
            self.assertTrue(exit_id.startswith(from_entry + " "), exit_id)
        self.assertTrue(cancels <= {e for e, _ in exits})

    def test_exit_comments_are_known_reasons(self):
        comments = set(re.findall(r'comment(?:_profit|_loss)? = "([^"]+)"', self.text))
        reason_fn = re.search(r"f_reason\(string c\) =>\n(.*)\n", self.text).group(1)
        for c in comments - {"Long", "Short"}:
            self.assertIn(f'"{c}"', reason_fn, f"exit comment {c} is not mapped in f_reason")

    def test_packet_keys_match_example(self):
        sample = json.loads((ROOT / "examples" / "sample_strategy_packet.json").read_text())
        sample_keys = flatten_keys(sample)
        pine_keys = set(re.findall(r'\\?"([a-z_0-9]+)\\?":', self.text))
        order_only = {"action", "reason", "order_id", "price_ref", "tag", "price", "type", "entry_price", "exit_price", "profit"}
        self.assertEqual(sorted(sample_keys - pine_keys), [], "keys in the example that the strategy never sends")
        self.assertEqual(sorted(pine_keys - sample_keys - order_only), [], "keys the strategy sends that the example lacks")

    def test_order_message_keys_match_example(self):
        sample = json.loads((ROOT / "examples" / "sample_order.json").read_text())
        body = re.search(r"f_orderMsg\(.*?\n\n", self.text, re.S).group(0)
        keys = set(re.findall(r'"([a-z_0-9]+)":', body)) - {"tag"}
        self.assertEqual(keys, set(sample))

    def test_schemas_match_receiver(self):
        import sys
        sys.path.insert(0, str(ROOT / "examples"))
        import webhook_receiver as wr
        for schema in re.findall(r'"schema":"([^"]+)"', self.text):
            self.assertIn(schema, wr.SCHEMAS)

    def test_order_actions_match_receiver(self):
        import sys
        sys.path.insert(0, str(ROOT / "examples"))
        import webhook_receiver as wr
        actions = set(re.findall(r'f_orderMsg\("([A-Z_]+)"', self.text))
        actions |= set(re.findall(r'"(OPEN_LONG|OPEN_SHORT|CLOSE_LONG|CLOSE_SHORT)"', self.text))
        self.assertEqual(actions, wr.ORDER_ACTIONS)


if __name__ == "__main__":
    unittest.main()
