#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from resolve_release import (
    missing_toolchain_packages,
    normalize_nuget_version,
    release_revision,
    toolchain_package_version,
    validate_slang_release,
)
from toolchain_layout import PLATFORMS, package_ids


class NormalizeNuGetVersionTests(unittest.TestCase):
    def test_pads_missing_numeric_components(self) -> None:
        self.assertEqual(normalize_nuget_version("2026.15"), "2026.15.0")

    def test_preserves_three_numeric_components(self) -> None:
        self.assertEqual(normalize_nuget_version("2026.14.1"), "2026.14.1")

    def test_preserves_nonzero_revision(self) -> None:
        self.assertEqual(normalize_nuget_version("2026.12.0.1"), "2026.12.0.1")

    def test_omits_zero_revision_and_build_metadata(self) -> None:
        self.assertEqual(normalize_nuget_version("01.02.03.0+build.4"), "1.2.3")

    def test_preserves_prerelease(self) -> None:
        self.assertEqual(normalize_nuget_version("2026.15-rc.1"), "2026.15.0-rc.1")

    def test_rejects_more_than_four_numeric_components(self) -> None:
        with self.assertRaises(RuntimeError):
            normalize_nuget_version("2026.15.0.1.2")


class MissingToolchainPackagesTests(unittest.TestCase):
    def test_checks_the_sdk_and_every_platform_package(self) -> None:
        checked = []

        def package_exists(package_id: str, version: str) -> bool:
            checked.append((package_id, version))
            return True

        self.assertEqual(missing_toolchain_packages("2026.15.0", package_exists), [])
        self.assertEqual(
            checked,
            [
                ("SlangDxcBundle.Toolchain", "2026.15.0"),
                ("SlangDxcBundle.Toolchain.linux-arm64", "2026.15.0"),
                ("SlangDxcBundle.Toolchain.linux-x64", "2026.15.0"),
                ("SlangDxcBundle.Toolchain.osx-arm64", "2026.15.0"),
                ("SlangDxcBundle.Toolchain.osx-x64", "2026.15.0"),
                ("SlangDxcBundle.Toolchain.win-x64", "2026.15.0"),
            ],
        )
        self.assertEqual(list(package_ids()), [package_id for package_id, _ in checked])

    def test_reports_a_partially_published_release(self) -> None:
        def package_exists(package_id: str, version: str) -> bool:
            return package_id != "SlangDxcBundle.Toolchain.osx-x64"

        self.assertEqual(
            missing_toolchain_packages("2026.15.0", package_exists),
            ["SlangDxcBundle.Toolchain.osx-x64"],
        )

    def test_reports_every_package_when_nothing_is_published(self) -> None:
        self.assertEqual(
            missing_toolchain_packages("2026.15.0", lambda package_id, version: False),
            list(package_ids()),
        )


class ToolchainPackageVersionTests(unittest.TestCase):
    def test_appends_the_revision_to_a_two_component_slang_version(self) -> None:
        self.assertEqual(toolchain_package_version("2026.19", 1), "2026.19.0.1")

    def test_appends_the_revision_to_a_three_component_slang_version(self) -> None:
        self.assertEqual(toolchain_package_version("2026.18.3", 2), "2026.18.3.2")

    def test_places_the_revision_before_the_prerelease_label(self) -> None:
        self.assertEqual(toolchain_package_version("2026.20-rc.1", 1), "2026.20.0.1-rc.1")

    def test_rejects_a_four_component_slang_version(self) -> None:
        with self.assertRaises(RuntimeError):
            toolchain_package_version("2026.19.0.1", 1)


class ValidateSlangReleaseTests(unittest.TestCase):
    @staticmethod
    def release(tag: str) -> dict:
        version = tag.removeprefix("v")
        return {"tag_name": tag, "draft": False, "assets": [{"name": f"slang-{version}-{platform}.zip"} for platform in PLATFORMS]}

    def test_accepts_a_complete_release(self) -> None:
        validate_slang_release(self.release("v2026.19"))

    def test_rejects_a_tag_without_a_package_version(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_slang_release(self.release("v2026.20.1.2.3"))

    def test_rejects_a_missing_asset(self) -> None:
        release = self.release("v2026.19")
        release["assets"].pop()
        with self.assertRaises(RuntimeError):
            validate_slang_release(release)


class ReleaseRevisionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repository = Path(directory.name)
        self.git("init", "--quiet")

    def git(self, *arguments: str) -> str:
        environment = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com", "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com"}
        return subprocess.run(["git", "-C", str(self.repository), *arguments], check=True, capture_output=True, text=True, env=environment).stdout.strip()

    def commit(self, path: str, content: str) -> str:
        file = self.repository / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
        self.git("add", path)
        self.git("commit", "--quiet", "--message", f"Change {path}")
        return self.git("rev-parse", "HEAD")

    def test_pin_commit_is_revision_one(self) -> None:
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.assertEqual(release_revision(self.repository), (1, pin_commit))

    def test_counts_only_commits_under_release_paths(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        packaging_commit = self.commit("packaging/file.txt", "1")
        self.commit("README.md", "docs")
        self.commit(".github/workflows/update-slang.yml", "1")
        self.assertEqual(release_revision(self.repository), (2, packaging_commit))

    def test_counts_every_release_path(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("packaging/file.txt", "1")
        self.commit("scripts/file.py", "1")
        self.commit("tests/file.txt", "1")
        workflow_commit = self.commit(".github/workflows/release.yml", "1")
        self.assertEqual(release_revision(self.repository), (5, workflow_commit))

    def test_new_pin_resets_the_revision(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("scripts/file.py", "1")
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.20"}')
        self.assertEqual(release_revision(self.repository), (1, pin_commit))

    def test_returning_to_an_earlier_pin_continues_its_revisions(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("scripts/file.py", "1")
        self.commit("release.json", '{"slang_tag": "v2026.20"}')
        self.commit("scripts/file.py", "2")
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.assertEqual(release_revision(self.repository), (5, pin_commit))

    def test_tags_with_the_same_package_version_share_revisions(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("scripts/file.py", "1")
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.19.0"}')
        self.assertEqual(release_revision(self.repository), (3, pin_commit))

    def test_ignores_files_no_release_job_reads(self) -> None:
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("tests/test_resolve_release.py", "1")
        self.commit("scripts/update_slang.py", "1")
        self.assertEqual(release_revision(self.repository), (1, pin_commit))

    def test_prerelease_labels_match_case_insensitively(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.20-RC.1"}')
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.20-rc.1"}')
        self.assertEqual(release_revision(self.repository), (3, pin_commit))

    def test_skips_an_earlier_pin_without_a_package_version(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("release.json", '{"slang_tag": "v2026.20.1.2.3"}')
        pin_commit = self.commit("release.json", '{"slang_tag": "v2026.21"}')
        self.assertEqual(release_revision(self.repository), (1, pin_commit))

    def test_rejects_a_shallow_clone(self) -> None:
        self.commit("release.json", '{"slang_tag": "v2026.19"}')
        self.commit("scripts/file.py", "1")
        clone = self.repository / "clone"
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", self.repository.as_uri(), str(clone)], check=True, capture_output=True)
        with self.assertRaises(RuntimeError):
            release_revision(clone)


if __name__ == "__main__":
    unittest.main()
