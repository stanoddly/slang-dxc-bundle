#!/usr/bin/env python3

import unittest

from scripts.resolve_release import normalize_nuget_version


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


if __name__ == "__main__":
    unittest.main()
