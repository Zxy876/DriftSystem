# backend/app/core/story/story_graph.py

from collections import Counter, deque
import json
import os
import time
from typing import Any, Dict, List, Optional


class StoryGraph:
    """
    StoryGraph — 关卡图控制器

    目标：
    - 从本地 JSON 关卡构建一个有向图
    - 提供：下一关 BFS 主线推进
    - 后面可扩展为分支、多结局等
    """

    def __init__(self, level_dir: str):
        """
        level_dir: like backend/data/heart_levels
        """
        self.level_dir = level_dir
        self.levels: Dict[str, dict] = {}
        self.edges: Dict[str, List[str]] = {}   # 邻接表
        self.trajectory: Dict[str, List[Dict[str, Any]]] = {}
        self._load_levels()
        self._build_linear_graph()

    # ================= 加载所有 level_X.json =================
    def _load_levels(self):
        if not os.path.isdir(self.level_dir):
            print(f"[StoryGraph] level_dir not found: {self.level_dir}")
            return

        for fname in sorted(os.listdir(self.level_dir)):
            if not fname.endswith(".json"):
                continue

            path = os.path.join(self.level_dir, fname)
            try:
                with open(path, "r", encoding="utf8") as f:
                    data = json.load(f)

                key = fname.replace(".json", "")  # e.g. "level_01"
                self.levels[key] = data

            except Exception as e:
                print(f"[StoryGraph] Failed to load {fname}: {e}")

        print(f"[StoryGraph] Loaded {len(self.levels)} levels from {self.level_dir}")

    # ============== 线性主线：01→02→…→30 =============
    def _build_linear_graph(self):
        keys = sorted(self.levels.keys())
        for i, key in enumerate(keys):
            if i < len(keys) - 1:
                self.edges[key] = [keys[i + 1]]
            else:
                self.edges[key] = []  # 最后一关无后继
        print(f"[StoryGraph] Graph edges = {self.edges}")

    # ================= 主线推进：下一关（bfs next） ===============
    def bfs_next(self, current_level: str) -> Optional[str]:
        key = self._canonical_level_id(current_level)
        if not key or key not in self.edges:
            return None
        neighbors = self.edges[key]
        if not neighbors:
            return None
        return neighbors[0]

    # ================= MiniMap：整条主线顺序 =================
    def bfs_order(self, start: str) -> List[str]:
        """
        从某个关卡开始，按照图结构做 BFS，返回遍历顺序。
        MiniMap 会用它来决定「主线大地图」的绘制顺序。
        """
        if start not in self.levels:
            return []

        visited = set()
        order: List[str] = []

        q: deque[str] = deque([start])

        while q:
            lv = q.popleft()
            if lv in visited:
                continue
            visited.add(lv)
            order.append(lv)

            for nb in self.edges.get(lv, []):
                if nb not in visited:
                    q.append(nb)

        return order

    # ================= MiniMap：邻接节点 =================
    def neighbors(self, level_id: str) -> List[str]:
        """
        返回此关卡的相邻关卡（MiniMap 需要）
        """
        key = self._canonical_level_id(level_id)
        if not key:
            return []
        return self.edges.get(key, [])

    # ================= 工具函数: 拿关卡数据、拿全部关卡 ================
    def get_level(self, level_name: str) -> Optional[dict]:
        key = self._canonical_level_id(level_name)
        if not key:
            return None
        return self.levels.get(key)

    def all_levels(self) -> List[str]:
        return list(self.levels.keys())

    def canonicalize_level_id(self, level_id: Optional[str]) -> Optional[str]:
        return self._canonical_level_id(level_id)

    # ================= Phase 5: 记录剧情轨迹 =================
    def update_trajectory(self, player_id: str, level_id: Optional[str], action: str,
                          meta: Optional[Dict[str, Any]] = None) -> None:
        """Append a trajectory entry for a player's storyline."""

        if not player_id:
            return

        entry = {
            "level": level_id,
            "action": action,
            "meta": meta or {},
            "ts": time.time(),
        }
        self.trajectory.setdefault(player_id, []).append(entry)

    # ================= Phase 10: 智能推荐下一关 =================
    def recommend_next_levels(
        self,
        player_id: str,
        current_level: Optional[str],
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Recommend next levels with light-weight heuristics."""

        limit = max(0, limit or 0)
        if limit == 0:
            return []

        canonical_current = self._canonical_level_id(current_level)
        history = self.trajectory.get(player_id, []) or []

        normalized_history: List[Dict[str, Any]] = []
        for entry in history:
            raw_level = entry.get("level")
            normalized = self._canonical_level_id(raw_level)
            normalized_history.append({
                "raw": raw_level,
                "canonical": normalized,
                "action": entry.get("action"),
                "meta": entry.get("meta", {}),
                "ts": entry.get("ts"),
            })

        completed_levels = {
            item["canonical"]
            for item in normalized_history
            if item["canonical"] and item["action"] == "exit"
        }
        seen_levels = [item["canonical"] for item in normalized_history if item["canonical"]]

        last_exit_level = None
        for item in reversed(normalized_history):
            if item["canonical"] and item["action"] == "exit":
                last_exit_level = item["canonical"]
                break

        tag_counter: Counter[str] = Counter()
        chapter_values: List[int] = []
        for item in normalized_history:
            canonical = item["canonical"]
            if not canonical or item["action"] != "exit":
                continue
            level_data = self.get_level(canonical) or {}
            for tag in level_data.get("tags", []) or []:
                if isinstance(tag, str):
                    tag_counter[tag] += 1
            meta = level_data.get("meta") or {}
            chapter = meta.get("chapter")
            if isinstance(chapter, int):
                chapter_values.append(chapter)

        avg_chapter = sum(chapter_values) / len(chapter_values) if chapter_values else None

        candidate_ids: List[str] = []

        # 1) 当前关卡的邻居优先
        if canonical_current:
            candidate_ids.extend(self.neighbors(canonical_current))
            if canonical_current not in completed_levels:
                candidate_ids.append(canonical_current)

        # 2) 最近退出关卡的主线后继
        reference_level = canonical_current or last_exit_level
        if reference_level:
            next_mainline = self.bfs_next(reference_level)
            if next_mainline:
                candidate_ids.append(next_mainline)

        # 3) 补充未体验过的关卡，直到数量够用
        unvisited = [lv for lv in sorted(self.levels.keys()) if lv not in seen_levels]
        for lv in unvisited:
            if len(candidate_ids) >= max(limit * 2, limit + 1):
                break
            candidate_ids.append(lv)

        # 4) 最后兜底：全部关卡（保持顺序）
        if not candidate_ids:
            candidate_ids.extend(sorted(self.levels.keys()))

        scored: Dict[str, Dict[str, Any]] = {}
        primary_mainline = None
        if reference_level:
            primary_mainline = self.bfs_next(reference_level)

        tag_total = sum(tag_counter.values())

        for candidate in candidate_ids:
            canonical = self._canonical_level_id(candidate)
            if not canonical:
                continue

            if canonical not in scored:
                scored[canonical] = {
                    "level_id": canonical,
                    "score": 0.0,
                    "reasons": [],
                }

            entry = scored[canonical]
            reasons = entry["reasons"]

            if canonical == primary_mainline:
                entry["score"] += 50.0
                reasons.append("主线推进")

            if canonical not in completed_levels:
                entry["score"] += 25.0
                reasons.append("尚未通关")
            else:
                exit_count = sum(1 for item in normalized_history if item["canonical"] == canonical and item["action"] == "exit")
                entry["score"] -= 10.0 * exit_count
                if exit_count > 0:
                    reasons.append("曾经通关")

            if canonical_current and canonical in self.neighbors(canonical_current):
                entry["score"] += 15.0
                reasons.append("连接当前剧情")

            if canonical == canonical_current:
                entry["score"] += 20.0
                reasons.append("继续当前关卡")

            level_data = self.get_level(canonical) or {}
            tags = [t for t in (level_data.get("tags") or []) if isinstance(t, str)]
            if tags and "tags" not in entry:
                entry["tags"] = list(tags)

            title = level_data.get("title") if isinstance(level_data, dict) else None
            if isinstance(title, str) and title:
                entry.setdefault("title", title)
            else:
                entry.setdefault("title", canonical)
            for tag in tags:
                if tag_total:
                    weight = tag_counter.get(tag, 0) / tag_total
                    if weight > 0:
                        entry["score"] += 20.0 * weight
                        if f"偏好：{tag}" not in reasons:
                            reasons.append(f"偏好：{tag}")

            meta = level_data.get("meta") or {}
            chapter = meta.get("chapter")
            if isinstance(chapter, int) and avg_chapter is not None:
                diff = abs(chapter - avg_chapter)
                if diff < 1:
                    entry["score"] += 8.0
                    reasons.append("章节节奏相似")
                elif diff <= 3:
                    entry["score"] += 2.0
                else:
                    entry["score"] -= 2.5
            if isinstance(chapter, int):
                entry.setdefault("chapter", chapter)

            if canonical in seen_levels and canonical not in completed_levels:
                entry["score"] += 5.0
                reasons.append("正在进行中")

        ranked = sorted(
            scored.values(),
            key=lambda item: (-item["score"], item["level_id"]),
        )

        top_ranked = ranked[:limit]

        for item in top_ranked:
            reasons_list = item.get("reasons") or []
            if reasons_list:
                deduped = list(dict.fromkeys(reasons_list))
                item["reasons"] = deduped
                summary = "、".join(deduped[:3])
                if summary:
                    item["reason_summary"] = summary
            if "title" not in item:
                item["title"] = item.get("level_id")

        return top_ranked

    # ================= 内部工具 =================
    def _canonical_level_id(self, level_id: Optional[str]) -> Optional[str]:
        if not level_id:
            return None

        if level_id in self.levels:
            return level_id

        if isinstance(level_id, str):
            normalized = level_id.replace(".json", "")
            if normalized in self.levels:
                return normalized

            if normalized.startswith("level_"):
                suffix = normalized.split("_", 1)[1]
                if suffix.isdigit():
                    padded = f"level_{int(suffix):02d}"
                    if padded in self.levels:
                        return padded

        return level_id if level_id in self.levels else None