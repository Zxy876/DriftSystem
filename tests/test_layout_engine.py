from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

for candidate in (str(ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.core.narrative.layout_engine import layout_scene_graph
from app.core.narrative.scene_graph import SceneGraph


def _clearance(size_a: int, size_b: int, min_gap: int) -> int:
    return int(math.ceil((float(size_a) + float(size_b)) / 2.0 + float(min_gap)))


class LayoutEngineTest(unittest.TestCase):
    @staticmethod
    def _sample_graph_and_fragments() -> tuple[SceneGraph, dict]:
        graph = SceneGraph(root="village")
        graph.add_edge("village", "market")
        graph.add_edge("village", "forge")
        graph.add_edge("village", "farm")
        graph.add_edge("village", "shrine")

        fragments = {
            "village": {"size": [9, 9]},
            "market": {"size": [7, 5]},
            "forge": {"size": [5, 5]},
            "farm": {"size": [7, 7]},
            "shrine": {"size": [5, 5]},
        }
        return graph, fragments

    @staticmethod
    def _assert_no_overlap(positions: dict, fragments: dict, min_gap: int) -> None:
        expected_nodes = ["village", "market", "forge", "farm", "shrine"]
        unique_points = {(int(p.get("x", 0)), int(p.get("z", 0))) for p in positions.values() if isinstance(p, dict)}
        assert len(unique_points) == len(expected_nodes)

        for index, left in enumerate(expected_nodes):
            left_size = tuple(fragments[left]["size"])
            left_pos = positions[left]
            left_x = int(left_pos.get("x", 0))
            left_z = int(left_pos.get("z", 0))

            for right in expected_nodes[index + 1 :]:
                right_size = tuple(fragments[right]["size"])
                right_pos = positions[right]
                right_x = int(right_pos.get("x", 0))
                right_z = int(right_pos.get("z", 0))

                clearance_x = _clearance(int(left_size[0]), int(right_size[0]), min_gap)
                clearance_z = _clearance(int(left_size[1]), int(right_size[1]), min_gap)

                overlap_x = abs(left_x - right_x) < clearance_x
                overlap_z = abs(left_z - right_z) < clearance_z
                assert not (overlap_x and overlap_z)

    def test_radial_layout_min_distance_collision_avoidance(self):
        graph, fragments = self._sample_graph_and_fragments()

        first = layout_scene_graph(graph, fragments=fragments)
        second = layout_scene_graph(graph, fragments=fragments)

        self.assertEqual(first, second)
        self.assertEqual(first.get("root"), "village")

        positions = (first.get("positions") or {})
        self.assertTrue(isinstance(positions, dict) and positions)
        self.assertEqual(positions.get("village"), {"x": 0, "z": 0})

        expected_nodes = ["village", "market", "forge", "farm", "shrine"]
        for node in expected_nodes:
            self.assertIn(node, positions)
            self.assertTrue(isinstance(positions[node], dict))

        self._assert_no_overlap(positions, fragments, min_gap=2)

    def test_radial_layout_respects_configurable_min_gap(self):
        graph, fragments = self._sample_graph_and_fragments()

        default_layout = layout_scene_graph(graph, fragments=fragments)
        with patch.dict("os.environ", {"DRIFT_LAYOUT_MIN_GAP": "6"}, clear=False):
            widened_layout_first = layout_scene_graph(graph, fragments=fragments)
            widened_layout_second = layout_scene_graph(graph, fragments=fragments)

        self.assertEqual(widened_layout_first, widened_layout_second)
        self.assertNotEqual(default_layout.get("positions"), widened_layout_first.get("positions"))

        widened_positions = widened_layout_first.get("positions") or {}
        self._assert_no_overlap(widened_positions, fragments, min_gap=6)


if __name__ == "__main__":
    unittest.main()
