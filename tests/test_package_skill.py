"""Offline packaging regression tests; no network or installed-skill mutation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_skill", ROOT / "scripts/package_skill.py")
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="local-research-package-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "skills" / "local-research"
        self.source.mkdir(parents=True)
        (self.source / "SKILL.md").write_text("---\nname: local-research\ndescription: Fixture\n---\n# Fixture\n")
        (self.source / "references").mkdir()
        (self.source / "references/workflow.md").write_text("Canonical fixture instructions\n")
        self.output = self.base / "packages" / "skill.zip"

    def test_round_trip_and_only_one_entry(self):
        result = packaging.build_zip(self.source, self.output)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(packaging.verify_zip(self.source, self.output)["status"], "valid")
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual([name for name in archive.namelist() if name.endswith("/SKILL.md")],
                             ["local-research/SKILL.md"])

    def test_nested_ignored_distribution_is_rejected(self):
        old = self.source / "dist" / "local-research"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("---\nname: local-research\n---\nOld scope")
        with self.assertRaisesRegex(ValueError, "canonical SKILL"):
            packaging.build_zip(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_output_inside_source_or_another_skill_root_is_rejected(self):
        for output in (self.source / "dist/new.zip", self.base / "skills" / "other" / "new.zip"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "outside"):
                packaging.build_zip(self.source, output)

    def test_runtime_state_and_git_are_not_packaged(self):
        for name in (".env", ".state/private.json", ".git/config", "Research/report.md", "dist/old.zip"):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture private runtime data")
        packaging.build_zip(self.source, self.output)
        with zipfile.ZipFile(self.output) as archive:
            names = set(archive.namelist())
        self.assertEqual(names, {"local-research/SKILL.md", "local-research/references/workflow.md",
                                 "local-research/_package-manifest.json"})

    def test_source_change_invalidates_stale_package(self):
        packaging.build_zip(self.source, self.output)
        (self.source / "references/workflow.md").write_text("Updated source\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            packaging.verify_zip(self.source, self.output)

    def test_tampered_or_missing_member_is_rejected(self):
        packaging.build_zip(self.source, self.output)
        damaged = self.base / "damaged.zip"
        with zipfile.ZipFile(self.output) as original, zipfile.ZipFile(damaged, "w") as archive:
            for name in original.namelist():
                if name.endswith("/workflow.md"):
                    archive.writestr(name, b"Changed instructions")
                else:
                    archive.writestr(name, original.read(name))
        with self.assertRaises(ValueError):
            packaging.verify_zip(self.source, damaged)

    def test_existing_output_is_preserved(self):
        packaging.build_zip(self.source, self.output)
        before = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            packaging.build_zip(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_external_symlink_cannot_enter_package(self):
        outside = self.base / "outside.txt"
        outside.write_text("outside fixture")
        (self.source / "references" / "linked.txt").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            packaging.build_zip(self.source, self.output)


if __name__ == "__main__":
    unittest.main()
