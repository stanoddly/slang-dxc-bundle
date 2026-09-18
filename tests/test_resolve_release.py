#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from resolve_release import missing_toolchain_packages, normalize_nuget_version
from toolchain_layout import package_ids


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


if __name__ == "__main__":
    unittest.main()
