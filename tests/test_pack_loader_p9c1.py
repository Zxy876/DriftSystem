from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.api import world_api
from app.core.packs.pack_loader import load_packs
from app.core.packs.pack_registry import PackRegistry
from app.core.packs.pack_types import PackMeta


class PackLoaderP9C1Test(unittest.TestCase):
    def test_load_packs_returns_pack_meta_rows(self):
        packs = load_packs()
        self.assertIsInstance(packs, list)
        self.assertTrue(all(isinstance(pack_meta, PackMeta) for pack_meta in packs))

    def test_sample_pack_ids_are_present(self):
        pack_ids = {pack_meta.pack_id for pack_meta in load_packs()}
        self.assertTrue({"vanilla_core", "ruins_pack", "poetry_pack"}.issubset(pack_ids))

    def test_registry_enabled_ids_filter_disabled_packs(self):
        registry = PackRegistry(
            packs=[
                PackMeta("alpha_pack", "1.0", "alpha", 10, True, ""),
                PackMeta("beta_pack", "1.0", "beta", 20, False, ""),
            ]
        )

        self.assertEqual(registry.enabled_ids(), ["alpha_pack"])

    def test_world_state_exposes_enabled_packs(self):
        with patch("app.api.world_api.story_engine.get_public_state", return_value={"player_current_level": "flagship_01"}), patch(
            "app.api.world_api.world_engine.get_state",
            return_value={"variables": {"x": 1}, "entities": {}},
        ), patch(
            "app.api.world_api.quest_runtime.get_debug_snapshot",
            return_value={
                "level_state": {"current_stage": "camp", "stage_path": ["forest", "camp"]},
                "recent_rule_events": [],
            },
        ), patch(
            "app.api.world_api._scene_generation_for_player",
            return_value={"scene_state": {"root": "camp", "nodes": ["camp"]}},
        ), patch(
            "app.api.world_api._enabled_packs_payload",
            return_value={"enabled_packs": ["vanilla_core", "ruins_pack"]},
        ):
            response = world_api.world_state("vivn")

        self.assertEqual(response.get("status"), "ok")
        self.assertEqual(response.get("enabled_packs"), ["vanilla_core", "ruins_pack"])


if __name__ == "__main__":
    unittest.main()
