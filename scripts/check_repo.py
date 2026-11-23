#!/usr/bin/env python3
"""Structural checks for the hermes-skills repo. Read-only, no network.

Checks, per skill:
  1. frontmatter parses; name matches the folder; description present (warn if over 60 chars)
  2. every referenced in-skill path (references/, templates/, scripts/) exists
  3. code fences balanced
  4. markdown tables have a consistent column count per table
  5. no duplicate heading text within a file
  6. scripts/*.py compile
  7. local markdown links in README resolve
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "hermes-research-crew" / "scripts"))
import yaml_load  # noqa: E402


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    return text[3:end], text[end + 4 :]


def main() -> int:
    fails: list[str] = []
    warns: list[str] = []

    for skill in sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()):
        skill_md = skill / "SKILL.md"
        if not skill_md.exists():
            fails.append(f"{skill.name}: no SKILL.md")
            continue
        text = skill_md.read_text(encoding="utf-8")
        fm_raw, _ = parse_frontmatter(text)
        if fm_raw is None:
            fails.append(f"{skill.name}: no frontmatter")
            continue
        try:
            fm = yaml_load.load_text(fm_raw) or {}
        except Exception as exc:  # noqa: BLE001
            fails.append(f"{skill.name}: frontmatter does not parse: {exc}")
            continue

        if fm.get("name") != skill.name:
            fails.append(f"{skill.name}: frontmatter name {fm.get('name')!r} != folder")
        desc = str(fm.get("description", "")).strip().strip('"')
        if not desc:
            fails.append(f"{skill.name}: no description")
        elif len(desc) > 60:
            warns.append(f"{skill.name}: description is {len(desc)} chars (>60): {desc}")
        if not fm.get("version"):
            warns.append(f"{skill.name}: no version")
        platforms = fm.get("platforms")
        if platforms is not None:
            allowed = {"linux", "macos", "windows"}
            if not isinstance(platforms, list) or any(p not in allowed for p in platforms):
                fails.append(f"{skill.name}: platforms must be a list of {sorted(allowed)}")

        md_files = sorted(skill.rglob("*.md"))
        for md in md_files:
            body = md.read_text(encoding="utf-8")
            rel = md.relative_to(ROOT)

            if body.count("```") % 2:
                fails.append(f"{rel}: unbalanced code fences ({body.count('```')})")

            for ref in sorted(set(re.findall(r"`((?:references|templates|scripts|assets)/[^`\s]+)`", body))):
                if not (skill / ref).exists():
                    fails.append(f"{rel}: references missing file {ref}")

            # tables: consecutive lines starting with '|'
            block: list[str] = []
            for line in body.splitlines() + [""]:
                if line.lstrip().startswith("|"):
                    block.append(line)
                else:
                    if len(block) >= 2:
                        counts = {ln.count("|") for ln in block}
                        if len(counts) != 1:
                            fails.append(
                                f"{rel}: table columns vary {sorted(counts)} near {block[0][:60]!r}"
                            )
                    block = []

            heads = re.findall(r"^#{1,6} +(.+)$", body, flags=re.M)
            dupes = {h for h in heads if heads.count(h) > 1}
            for d in sorted(dupes):
                warns.append(f"{rel}: duplicate heading {d!r}")

        uses_fcntl = False
        for py in sorted((skill / "scripts").glob("*.py")) if (skill / "scripts").is_dir() else []:
            import py_compile

            try:
                py_compile.compile(str(py), doraise=True)
            except py_compile.PyCompileError as exc:
                fails.append(f"{py.relative_to(ROOT)}: does not compile: {exc}")
            if re.search(r"^\s*(import fcntl|from fcntl import)\b", py.read_text(encoding="utf-8"), re.M):
                uses_fcntl = True
        if uses_fcntl and not fm.get("platforms"):
            warns.append(f"{skill.name}: a script imports fcntl but frontmatter has no platforms")
        print(f"checked {skill.name}: {len(md_files)} md file(s)")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)#][^)]*)\)", readme):
        if link.startswith("http"):
            continue
        target = (ROOT / link).resolve()
        if not target.exists():
            fails.append(f"README: broken link {link}")

    for w in warns:
        print(f"WARN  {w}")
    for f in fails:
        print(f"FAIL  {f}")
    print(f"\nfails={len(fails)} warns={len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
