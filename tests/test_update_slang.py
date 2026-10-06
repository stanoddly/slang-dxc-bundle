#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from update_slang import should_update


class ShouldUpdateTests(unittest.TestCase):
    def test_keeps_the_pinned_tag(self) -> None:
        self.assertFalse(should_update("v2026.19", "v2026.19", explicit=False))
        self.assertFalse(should_update("v2026.19", "v2026.19", explicit=True))

    def test_moves_forward_to_the_latest_release(self) -> None:
        self.assertTrue(should_update("v2026.19", "v2026.19.1", explicit=False))
        self.assertTrue(should_update("v2026.19", "v2026.20", explicit=False))

    def test_latest_release_never_moves_the_pin_backwards(self) -> None:
        self.assertFalse(should_update("v2026.20-rc.1", "v2026.19", explicit=False))
        self.assertFalse(should_update("v2026.19.1", "v2026.19", explicit=False))

    def test_explicit_tag_may_move_the_pin_backwards(self) -> None:
        self.assertTrue(should_update("v2026.19", "v2026.18.3", explicit=True))


if __name__ == "__main__":
    unittest.main()
