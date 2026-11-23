#!/usr/bin/env python3
"""Load a YAML mapping without a required third-party package.

Order: ruamel.yaml (ships with the Hermes runtime), then PyYAML, then a
stdlib subset enough for Hermes config files: nested mappings, lists, scalars,
and empty ``[]`` / ``{}``. Block scalars, anchors, and tags raise
UnsupportedYAML so the caller can stop instead of diffing a wrong tree.
"""
from __future__ import annotations

import re

class UnsupportedYAML(ValueError):
    pass


def which_loader() -> str:
    try:
        import ruamel.yaml  # noqa: F401
        return "ruamel"
    except ImportError:
        pass
    try:
        import yaml  # noqa: F401
        return "pyyaml"
    except ImportError:
        return "stdlib"


def load_text(text: str, loader: str = "auto"):
    choice = which_loader() if loader == "auto" else loader
    if choice == "ruamel":
        from ruamel.yaml import YAML

        data = YAML(typ="safe").load(text)
        return {} if data is None else data
    if choice == "pyyaml":
        import yaml

        data = yaml.safe_load(text)
        return {} if data is None else data
    if choice == "stdlib":
        return load_stdlib(text)
    raise UnsupportedYAML(f"unknown loader {choice}")


def parse_scalar(raw: str):
    """Parse one --expect value or one YAML scalar."""
    return _scalar(raw.strip())


_KEY = re.compile(r"^([A-Za-z0-9_.-]+):\s*(.*)$")


def _strip_comment(line: str) -> str:
    out: list[str] = []
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote and line[i - 1] != "\\":
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_flow(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch == ",":
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf or parts:
        parts.append("".join(buf))
    return parts


def _flow_list(inner: str) -> list:
    body = inner.strip()
    if not body:
        return []
    return [_scalar(part.strip()) for part in _split_flow(body)]


def _flow_map(inner: str) -> dict:
    body = inner.strip()
    if not body:
        return {}
    out: dict = {}
    for part in _split_flow(body):
        if ":" not in part:
            raise UnsupportedYAML(f"flow map entry {part!r}")
        key, value = part.split(":", 1)
        out[_scalar(key.strip())] = _scalar(value.strip())
    return out


def _scalar(s: str):
    if s in ("", "null", "Null", "NULL", "~"):
        return None
    if s.startswith("[") and s.endswith("]"):
        return _flow_list(s[1:-1])
    if s.startswith("{") and s.endswith("}"):
        return _flow_map(s[1:-1])
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", s):
        return float(s)
    if any(tok in s for tok in ("|", ">", "&", "*", "!")):
        raise UnsupportedYAML(f"unsupported scalar {s!r}")
    return s


def load_stdlib(text: str):
    lines: list[tuple[int, int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw:
            raise UnsupportedYAML(f"tab on line {lineno}")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((lineno, indent, stripped.strip()))
    if not lines:
        return {}
    value, nxt = _parse(lines, 0, lines[0][1])
    if nxt != len(lines):
        raise UnsupportedYAML(f"trailing content at line {lines[nxt][0]}")
    if not isinstance(value, dict):
        raise UnsupportedYAML("document is not a mapping")
    return value


def _parse(lines, i, indent):
    if i >= len(lines):
        return {}, i
    if lines[i][2].startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    out: dict = {}
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise UnsupportedYAML(f"bad indent at line {lineno}")
        if text.startswith("- "):
            raise UnsupportedYAML(f"list item in a mapping at line {lineno}")
        match = _KEY.match(text)
        if not match:
            raise UnsupportedYAML(f"expected a key at line {lineno}")
        key, rest = match.group(1), match.group(2).strip()
        i += 1
        if rest == "":
            if i < len(lines) and lines[i][1] > indent:
                child, i = _parse(lines, i, lines[i][1])
                out[key] = child
            else:
                out[key] = None
        else:
            out[key] = _scalar(rest)
    return out, i


def _parse_list(lines, i, indent):
    out: list = []
    while i < len(lines) and lines[i][1] == indent and lines[i][2].startswith("- "):
        _lineno, _ind, text = lines[i]
        item = text[2:].strip()
        i += 1
        if item == "":
            if i < len(lines) and lines[i][1] > indent:
                child, i = _parse(lines, i, lines[i][1])
            else:
                child = None
            out.append(child)
            continue
        match = _KEY.match(item)
        nested_sibling = (
            i < len(lines) and lines[i][1] > indent and not lines[i][2].startswith("- ")
        )
        if match and (match.group(2).strip() == "" or nested_sibling):
            key, rest = match.group(1), match.group(2).strip()
            node: dict = {}
            if rest == "":
                if i < len(lines) and lines[i][1] > indent:
                    node[key], i = _parse(lines, i, lines[i][1])
                else:
                    node[key] = None
            else:
                node[key] = _scalar(rest)
            if i < len(lines) and lines[i][1] > indent and not lines[i][2].startswith("- "):
                extra, i = _parse_map(lines, i, lines[i][1])
                node.update(extra)
            out.append(node)
            continue
        out.append(_scalar(item))
    return out, i
