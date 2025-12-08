# backend/app/core/story/story_engine.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.ai.deepseek_agent import deepseek_decide
from app.core.story.story_loader import load_level, build_level_prompt, Level
from app.core.story.story_graph import StoryGraph
from app.core.world.minimap import MiniMap
from app.core.world.scene_generator import SceneGenerator
from app.core.world.trigger import trigger_engine
from app.core.world.trigger import TriggerPoint
from app.core.npc import npc_engine
from app.core.quest.runtime import quest_runtime
from app.core.story.level_schema import ensure_level_extensions


class StoryEngine:
    def __init__(self):
        # 每个玩家的剧情状态
        self.players: Dict[str, Dict[str, Any]] = {}

        # 这些冷却参数保留字段，但 v2 不再用于“是否推进”判断
        self.move_cooldown = 3.0
        self.say_cooldown = 0.8

        # 关卡目录
        base_dir = Path(__file__).resolve().parents[3]
        level_dir = base_dir / "data" / "heart_levels"

        # 整体剧情图谱 + 小地图 + 场景生成
        self.graph = StoryGraph(str(level_dir))
        self.minimap = MiniMap(self.graph)
        self.scene_gen = SceneGenerator()

        # 触发器（v2：暂时禁用螺旋触发，避免乱飞）
        self._inject_spiral_triggers()

        print(
            f"[StoryEngine] loaded {len(self.graph.all_levels())} levels "
            f"from {level_dir}"
        )

    # ============================================================
    # Phase 1.5 scaffolding hooks (stubs)
    # ============================================================
    def enter_level_with_scene(self, player_id: str, level: Level) -> None:
        """Apply deterministic scene metadata when available.

        TODO: integrate with SceneOrchestrator to emit world patches and handle
        cleanup. For now we retain the handle on the player state to avoid
        losing context when future integrations arrive.
        """

        scene_cfg = getattr(level, "scene", None)
        if not scene_cfg:
            return

        player_state = self.players.setdefault(player_id, {})
        player_state["scene_handle"] = {
            "scene": scene_cfg,
            "applied": False,
        }

    def advance_with_beat(self, player_id: str, beat_id: str) -> None:
        """Move the active beat pointer forward.

        TODO: trigger beat-driven world patches and ensure quest/task syncing
        once the runtime supports these hooks.
        """

        player_state = self.players.setdefault(player_id, {})
        player_state["current_beat"] = beat_id

    def register_rule_listeners(self, level: Level) -> None:
        """Register rule listeners with the quest runtime.

        TODO: Bridge into the Minecraft plugin once a transport layer exists.
        """

        rule_cfg = getattr(level, "rules", None)
        if not rule_cfg or not getattr(rule_cfg, "listeners", None):
            return

        for listener in rule_cfg.listeners:
            quest_runtime.register_rule_listener(listener)

    def inject_tasks(self, player_id: str, level: Level) -> None:
        """Inject Phase 1.5 task definitions into QuestRuntime."""

        tasks = getattr(level, "tasks", [])
        if not tasks:
            return

        # TODO: convert TaskConfig dataclasses into legacy dicts and load them
        # into QuestRuntime once serialization is finalized.
        player_state = self.players.setdefault(player_id, {})
        player_state["pending_tasks"] = tasks

    def exit_level_with_cleanup(self, player_id: str, level: Level) -> None:
        """Placeholder for future exit wiring."""

        # TODO: invoke SceneCleanupService and QuestRuntime teardown once ready.
        player_state = self.players.setdefault(player_id, {})
        player_state.pop("scene_handle", None)
        player_state.pop("current_beat", None)

    # ============================================================
    # 状态查询
    # ============================================================
    def get_public_state(self, player_id: Optional[str] = None):
        return {
            "total_levels": len(self.graph.all_levels()),
            "levels": sorted(list(self.graph.all_levels())),
            "players": list(self.players.keys()),
            "player_current_level": (
                self.players.get(player_id, {}).get("level").level_id
                if player_id in self.players and self.players[player_id].get("level")
                else None
            ),
        }

    def _ensure_player(self, player_id: str):
        if player_id not in self.players:
            self.players[player_id] = {
                "messages": [],
                "nodes": [],
                "level": None,
                "level_loaded": False,
                "tree_state": None,
                "ended": False,
                "last_time": 0.0,
                "last_say_time": 0.0,
            }

    # ============================================================
    # 关卡跳转逻辑（下一关）
    # ============================================================
    def get_next_level_id(self, current_level_id: Optional[str]):
        if not current_level_id or not current_level_id.startswith("level_"):
            all_levels = sorted(self.graph.all_levels())
            return "level_01" if "level_01" in all_levels else all_levels[0]
        return self.graph.bfs_next(current_level_id)

    def load_next_level_for_player(self, player_id: str) -> Dict[str, Any]:
        self._ensure_player(player_id)
        p = self.players[player_id]
        current_level = getattr(p["level"], "level_id", None)
        next_id = self.get_next_level_id(current_level)
        if not next_id:
            p["ended"] = True
            return {"mc": {"tell": "🎉 已经是最后一关了。"}}
        return self.load_level_for_player(player_id, next_id)

    # ============================================================
    # ⭐ 剧情舞台渲染器 v2
    # ============================================================
    def _build_stage_patch(self, level: Level) -> Dict[str, Any]:
        """
        根据关卡信息，构建一个“剧情舞台”的 world_patch：
        - 固定在安全坐标附近渲染平台 / 粒子 / 标题 / 天气 / 时间 / 背景音
        - 不包含 teleport（teleport 由上层统一控制）
        """
        meta = level.meta or {}
        mood = level.mood or {}
        base_mood = mood.get("base", "calm")
        chapter = meta.get("chapter")

        # 默认主题
        theme = "dawn"

        # 粗略按章节区间分主题
        if isinstance(chapter, int):
            if chapter <= 5:
                theme = "dawn"
            elif chapter <= 10:
                theme = "noon"
            elif chapter <= 20:
                theme = "dusk"
            else:
                theme = "night"

        # 情绪覆盖：如果 mood 里写得比较“压抑”就强制 night/dusk
        if isinstance(base_mood, str):
            b = base_mood.lower()
            if any(k in b for k in ["sad", "dark", "痛", "压抑", "night"]):
                theme = "night"
            elif any(k in b for k in ["hope", "light", "晨", "morning"]):
                theme = "dawn"

        # 根据 theme 决定舞台参数
        if theme == "dawn":
            time_of_day = "sunrise"
            weather = "clear"
            particle_type = "END_ROD"
            sound_type = "MUSIC_DISC_OTHERSIDE"
            platform_mat = "SMOOTH_QUARTZ"
            accent_color = "§e"
            subtitle_hint = "清晨的风把故事轻轻翻开。"
        elif theme == "noon":
            time_of_day = "day"
            weather = "clear"
            particle_type = "HAPPY_VILLAGER"
            sound_type = "MUSIC_DISC_BLOCKS"
            platform_mat = "OAK_PLANKS"
            accent_color = "§a"
            subtitle_hint = "阳光很亮，世界也变得清晰。"
        elif theme == "dusk":
            time_of_day = "sunset"
            weather = "dream_sky"
            particle_type = "CHERRY_LEAVES"
            sound_type = "MUSIC_DISC_FAR"
            platform_mat = "PINK_STAINED_GLASS"
            accent_color = "§d"
            subtitle_hint = "夕阳像一页慢慢合上的剧本。"
        else:  # night
            time_of_day = "night"
            weather = "dark_sky"
            particle_type = "SOUL"
            sound_type = "MUSIC_DISC_STRAD"
            platform_mat = "BLACK_STAINED_GLASS"
            accent_color = "§9"
            subtitle_hint = "夜色把没说完的话藏了起来。"

        title_main = f"{accent_color}《{level.title}》§r"
        title_sub = subtitle_hint

        stage_mc: Dict[str, Any] = {
            # 舞台平台：统一在安全点附近，由 SafeTeleport 决定精确坐标
            "build": {
                "shape": "platform",
                "material": platform_mat,
                "size": 6,
                # 让平台中心正好在玩家脚下（teleport 会传到平台上方）
                "safe_offset": {"dx": 0, "dy": -1, "dz": 0},
            },
            # 情绪氛围
            "weather": weather,
            "time": time_of_day,
            "particle": {
                "type": particle_type,
                "count": 80,
                "radius": 2.5,
            },
            "sound": {
                "type": sound_type,
                "volume": 0.8,
                "pitch": 1.0,
            },
            "title": {
                "main": title_main,
                "sub": title_sub,
                "fade_in": 10,
                "stay": 60,
                "fade_out": 20,
            },
        }

        return {"mc": stage_mc}

    # ============================================================
    # 加载指定关卡（带剧情舞台 + 安全传送）
    # ============================================================
    def load_level_for_player(self, player_id: str, level_id: str) -> Dict[str, Any]:
        """
        加载指定关卡：
        - 绑定到玩家状态
        - 注入 minimap / tree / messages
        - 生成「剧情舞台 patch」+ 场景 patch + 原始 bootstrap_patch
        - 强制附带一个全局 SafeTeleport 到安全坐标（永不掉海里）
        """
        self._ensure_player(player_id)
        level: Level = load_level(level_id)
        ensure_level_extensions(level)
        p = self.players[player_id]

        # 绑定关卡状态
        p["level"] = level
        p["level_loaded"] = False
        p["tree_state"] = level.tree
        p["ended"] = False
        p["messages"].clear()
        p["nodes"].clear()

        # minimap：进度记录 + 点亮节点
        self.minimap.enter_level(player_id, level_id)
        self.minimap.mark_unlocked(player_id, level_id)

        # ---------------------------------------------
        # 🎭 剧情舞台渲染器
        # ---------------------------------------------
        stage_patch = self._build_stage_patch(level)  # 只负责 build/天气/时间/粒子/音效/标题

        # ---------------------------------------------
        # 场景生成（SceneGenerator）
        # 依然允许布置 NPC / 装置等，但禁止改 teleport
        # ---------------------------------------------
        scene_patch = self.scene_gen.generate_for_level(level_id, level.__dict__) or {}
        scene_mc = dict(scene_patch.get("mc") or {})
        if "teleport" in scene_mc:
            # 不允许 SceneGenerator 再改玩家传送位置，避免掉进奇怪地方
            del scene_mc["teleport"]

        # ---------------------------------------------
        # 原始 bootstrap_patch（现在是 world_patch，来自 level.json）
        # ---------------------------------------------
        base_patch = dict(level.bootstrap_patch or {})
        base_mc = dict(base_patch.get("mc") or {})

        # 合并：场景 → 舞台 → world_patch
        # world_patch优先级最高（最后合并，覆盖前面的配置）
        def merge_mc(dst: Dict[str, Any], src: Dict[str, Any]):
            for k, v in (src or {}).items():
                if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
                    # 深度合并字典
                    dst[k] = {**dst[k], **v}
                else:
                    dst[k] = v

        # 临时存储world_patch的配置
        world_patch_mc = dict(base_mc)
        temp_mc = {}
        
        # 先合并场景和舞台
        merge_mc(temp_mc, scene_mc)
        merge_mc(temp_mc, stage_patch.get("mc", {}))
        
        # 最后用world_patch覆盖（保留world_patch中的所有配置）
        merge_mc(temp_mc, world_patch_mc)
        base_mc = temp_mc

        # ---------------------------------------------
        # 🌈 全局安全传送（固定出生点 + 平台）
        # ---------------------------------------------
        SAFE_X, SAFE_Y, SAFE_Z = 0, 120, 0
        safe_tp_mc = {
            "teleport": {
                "mode": "absolute",
                "x": SAFE_X,
                "y": SAFE_Y,
                "z": SAFE_Z,
                "safe_platform": {
                    "material": "GLASS",
                    "radius": 6,
                },
            },
            "tell": f"进入剧情：《{level.title}》",
        }
        merge_mc(base_mc, safe_tp_mc)

        base_patch["mc"] = base_mc
        
        # ---------------------------------------------
        # 🤖 注册NPC行为到引擎
        # ---------------------------------------------
        spawn_data = base_mc.get("spawn")
        if spawn_data and "behaviors" in spawn_data:
            npc_engine.register_npc(level_id, spawn_data)
        
        # ============================================================
        # Phase 1.5 stubs
        # ============================================================
        if getattr(level, "scene", None):
            self.enter_level_with_scene(player_id, level)

        self.register_rule_listeners(level)
        self.inject_tasks(player_id, level)

        beats = getattr(level, "beats", [])
        if beats:
            first = beats[0]
            beat_id = getattr(first, "id", None) or "beat_0"
            self.advance_with_beat(player_id, beat_id)

        return base_patch

    # ============================================================
    # prompt 注入（第一次进入关卡时插入 system 提示词）
    # ============================================================
    def _inject_level_prompt_if_needed(self, player_id: str):
        p = self.players[player_id]
        level = p["level"]
        if not level or p["level_loaded"]:
            return
        
        # 构建关卡基础提示词
        base_prompt = build_level_prompt(level)
        
        # 添加NPC行为上下文
        npc_context = npc_engine.get_behavior_context_for_ai(level.level_id)
        if npc_context:
            base_prompt += f"\n\n{npc_context}"
        
        p["messages"].insert(
            0, {"role": "system", "content": base_prompt}
        )
        p["level_loaded"] = True

    # ============================================================
    # 触发区（v2：暂时禁用螺旋触发器，避免随机传送）
    # ============================================================
    def _inject_spiral_triggers(self):
        trigger_engine.triggers.clear()
        # 如果将来想重新启用，可以在这里重新 append TriggerPoint
        print("[Trigger] spiral triggers disabled (StoryEngine v2.stage)")

    # ============================================================
    # 冷却判断（/world/apply 用）
    # ============================================================
    def should_advance(
        self,
        player_id: str,
        world_state: Dict[str, Any],
        action: Dict[str, Any],
    ) -> bool:
        """
        v2：永远允许推进剧情。
        冷却节奏交给 deepseek_agent.MIN_INTERVAL 控制。
        world_api.py 如果调用了 should_advance，现在总是 True。
        """
        self._ensure_player(player_id)
        # 仍然更新时间戳，方便以后需要统计
        now = time.time()
        p = self.players[player_id]
        say = action.get("say")
        if isinstance(say, str) and say.strip():
            p["last_say_time"] = now
        else:
            p["last_time"] = now
        return True

    # ============================================================
    # 主推进逻辑
    # ============================================================
    def advance(
        self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
        self._ensure_player(player_id)
        p = self.players[player_id]

        # 默认 free 模式
        self._ensure_free_mode_level(player_id)
        self._inject_level_prompt_if_needed(player_id)

        if p["ended"]:
            return None, None, {"mc": {"tell": "本关已结束。"}}

        # 记录玩家发言
        say = action.get("say")
        if isinstance(say, str) and say.strip():
            p["messages"].append({"role": "user", "content": say})

        # 更新 minimap 上的位置
        vars_ = world_state.get("variables") or {}
        x, y, z = vars_.get("x", 0.0), vars_.get("y", 0.0), vars_.get("z", 0.0)
        self.minimap.update_player_pos(player_id, (x, y, z))

        # 触发器（目前为空，保留结构）
        trg = trigger_engine.check(player_id, x, y, z)
        if trg and trg.action == "load_level" and trg.level_id:
            patch = self.load_level_for_player(player_id, trg.level_id)
            node = {
                "title": "世界触发点",
                "text": f"你抵达了关键地点，关卡 {trg.level_id} 被唤醒。",
            }
            return None, node, patch

        # AI 决策
        ai_input = {
            "player_id": player_id,
            "player_action": action,
            "world_state": world_state,
            "recent_nodes": p["nodes"][-5:],
            "tree_state": p["tree_state"],
            "level_id": p["level"].level_id,
        }

        ai_result = deepseek_decide(ai_input, p["messages"])

        option = ai_result.get("option")
        node = ai_result.get("node")
        patch = ai_result.get("world_patch", {}) or {}
        mc_patch = patch.get("mc", {}) or {}

        # 更新 tree_state
        if option is not None:
            p["tree_state"] = {"last_option": option, "ts": time.time()}

        # 记录 AI 节点
        if node:
            p["nodes"].append(node)
            p["messages"].append(
                {
                    "role": "assistant",
                    "content": f"{node.get('title', '')}\n{node.get('text', '')}".strip(),
                }
            )
            cur_level = p["level"].level_id
            self.minimap.mark_unlocked(player_id, cur_level)

        # 结束标记
        if mc_patch.get("ending"):
            p["ended"] = True

        # 时间戳（仅统计，不再作为 gating）
        now = time.time()
        if say and say.strip():
            p["last_say_time"] = now
        else:
            p["last_time"] = now

        return option, node, patch

    # ============================================================
    # 自由模式关卡（无正式 level 时的 fallback）
    # ============================================================
    def _ensure_free_mode_level(self, player_id: str):
        p = self.players[player_id]
        if p["level"] is None:

            class FreeLevel:
                level_id = "heart_free"
                tree = None
                bootstrap_patch = {"mc": {"tell": "🌌 进入心悦自由宇宙模式。"}}

            p["level"] = FreeLevel()
            p["level_loaded"] = True


story_engine = StoryEngine()