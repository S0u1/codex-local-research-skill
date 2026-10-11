#!/usr/bin/env python3
"""Check one canonical Skill entry and build/verify a source-matching ZIP.

Writes ZIP files only, outside discoverable skills directories. Never extracts,
copies an installed skill, downloads data, or publishes the package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile


ROOT_FILES = {"SKILL.md", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"}
SOURCE_DIRS = {"agents", "references", "scripts", "tests", "licenses", "assets"}
MANIFEST = "_package-manifest.json"
NAME = "local-research"


def source_files(root):
    root = Path(root).resolve()
    entries = sorted(p.relative_to(root).as_posix() for p in root.rglob("SKILL.md"))
    if entries != ["SKILL.md"]:
        raise ValueError(f"Expected only the canonical SKILL.md; found {entries}. Move unpacked distributions outside skill roots.")
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n") or not re.search(r"(?m)^name:\s*local-research\s*$", text.split("---", 2)[1]):
        raise ValueError("Canonical SKILL.md must declare name: local-research")
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts) or path.suffix == ".pyc":
            continue
        if not (rel.as_posix() in ROOT_FILES or rel.parts[0] in SOURCE_DIRS):
            continue
        if path.is_symlink():
            raise ValueError(f"Package source must be a real file/directory, not a symlink: {rel}")
        if path.is_file():
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"Package source escapes the canonical directory: {rel}")
            result[rel.as_posix()] = path.read_bytes()
    return result


def hashes(files):
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def verify_zip(root, archive):
    files = source_files(root)
    expected = {f"{NAME}/{name}": data for name, data in files.items()}
    manifest_name = f"{NAME}/{MANIFEST}"
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected) | {manifest_name}:
            raise ValueError("ZIP has missing, duplicated, or unexpected entries")
        for name, data in expected.items():
            if package.getinfo(name).file_size != len(data) or package.read(name) != data:
                raise ValueError(f"ZIP differs from canonical source: {name}")
        recorded = json.loads(package.read(manifest_name))
        if recorded != {"schema_version": 1, "skill": NAME, "files": hashes(files)}:
            raise ValueError("ZIP source-hash manifest does not match canonical source")
    return {"status": "valid", "skill": NAME, "files": len(files), "entrypoints": ["SKILL.md"]}


def check_output(root, output):
    output = Path(output).expanduser()
    resolved = output.resolve()
    root = Path(root).resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("Package output must be a .zip file; this command never extracts a directory")
    if resolved == root or root in resolved.parents or any(parent.name == "skills" for parent in resolved.parents):
        raise ValueError("ZIP output must be outside the source and all skills directories")
    if output.is_symlink() or output.exists():
        raise ValueError("Output already exists; choose a new archive name")
    return resolved


def build_zip(root, output):
    files = source_files(root)
    output = check_output(root, output)
    manifest = json.dumps({"schema_version": 1, "skill": NAME, "files": hashes(files)},
                          ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".local-research-", suffix=".zip", dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for name, data in sorted({**files, MANIFEST: manifest}.items()):
                info = zipfile.ZipInfo(f"{NAME}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                package.writestr(info, data)
        result = verify_zip(root, temporary)
        os.link(temporary, output)  # Atomic creation; never replace an existing delivery.
    finally:
        temporary.unlink(missing_ok=True)
    return {**result, "output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Validate unique entry and selected source files")
    action.add_argument("--output", type=Path, help="Build a new external ZIP, verifying against source")
    action.add_argument("--verify", type=Path, help="Read-only exact comparison of a ZIP with canonical source")
    args = parser.parse_args()
    try:
        if args.output:
            result = build_zip(args.source, args.output)
        elif args.verify:
            result = verify_zip(args.source, args.verify)
        else:
            files = source_files(args.source)
            result = {"status": "valid", "skill": NAME, "files": len(files), "entrypoints": ["SKILL.md"]}
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
