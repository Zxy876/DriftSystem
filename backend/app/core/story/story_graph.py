# backend/app/core/story/story_graph.py

from collections import deque
import json
import os
from typing import Dict, List, Optional


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
        if current_level not in self.edges:
            return None
        neighbors = self.edges[current_level]
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
        return self.edges.get(level_id, [])

    # ================= 工具函数: 拿关卡数据、拿全部关卡 ================
    def get_level(self, level_name: str) -> Optional[dict]:
        return self.levels.get(level_name)

    def all_levels(self) -> List[str]:
        return list(self.levels.keys())