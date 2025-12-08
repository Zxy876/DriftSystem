# backend/app/core/story/story_engine.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from app.core.events.event_manager import EventManager


class StoryEngine:
    DEFAULT_EXIT_ALIASES = ["结束剧情", "离开关卡", "退出剧情", "退出", "leave", "exit"]
    DEFAULT_RETURN_SPAWNS: Dict[str, Dict[str, Any]] = {
        "KunmingLakeHub": {
            "world": "KunmingLakeHub",
            "x": 128.5,
            "y": 72.0,
            "z": -16.5,
            "yaw": 180.0,
            "pitch": 0.0,
        }
    }

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

        # Phase 2 runtime
        self.event_manager = EventManager()
        quest_runtime.set_rule_callback(self._handle_rule_catalyst)

        print(f"[StoryEngine] loading levels from {level_dir}")

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
            quest_runtime.register_rule_listener(level.level_id, listener)

    def inject_tasks(self, player_id: str, level: Level) -> None:
        """Inject Phase 1.5 task definitions into QuestRuntime."""

        tasks = getattr(level, "tasks", [])
        if not tasks:
            return

        # TODO: convert TaskConfig dataclasses into legacy dicts and load them
        # into QuestRuntime once serialization is finalized.
        player_state = self.players.setdefault(player_id, {})
        player_state["pending_tasks"] = tasks

    def exit_level_with_cleanup(self, player_id: str, level: Level) -> Dict[str, Any]:
        """Compose a cleanup patch when a player exits the level."""

        player_state = self.players.setdefault(player_id, {})
        exit_profile = player_state.pop("exit_profile", None)
        player_state.pop("scene_handle", None)
        player_state.pop("current_beat", None)
        player_state.pop("beat_state", None)
        player_state.pop("pending_nodes", None)
        player_state.pop("pending_patches", None)
        self.event_manager.unregister(player_id)
        quest_runtime.exit_level(player_id)

        cleanup_meta = {
            "level_id": getattr(level, "level_id", None),
            "scene": getattr(level, "scene", None) is not None,
        }
        hub_target = self._resolve_exit_target(exit_profile)

        farewell = None
        if isinstance(exit_profile, dict):
            farewell = exit_profile.get("farewell")
        if not farewell:
            farewell = f"已离开《{getattr(level, 'title', getattr(level, 'level_id', '该关卡'))}》，即将返回主线。"

        mc_payload: Dict[str, Any] = {
            "_scene_cleanup": cleanup_meta,
            "tell": farewell,
            "title": {
                "main": "§6剧情结束",
                "sub": "欢迎回到昆明湖主线",
                "fade_in": 10,
                "stay": 80,
                "fade_out": 20,
            },
        }

        if hub_target:
            mc_payload["teleport"] = {
                "mode": "absolute",
                "world": hub_target.get("world"),
                "x": hub_target.get("x", 0.0),
                "y": hub_target.get("y", 70.0),
                "z": hub_target.get("z", 0.0),
                "yaw": hub_target.get("yaw", 0.0),
                "pitch": hub_target.get("pitch", 0.0),
                "safe_platform": {
                    "material": "LIGHT_GRAY_CONCRETE",
                    "radius": 3,
                },
            }

        self.graph.update_trajectory(
            player_id,
            getattr(level, "level_id", None),
            "exit",
            {
                "hub": hub_target,
                "farewell": farewell,
                "aliases": exit_profile.get("aliases") if isinstance(exit_profile, dict) else None,
            },
        )

        exit_summary: Dict[str, Any] = {
            "hub": hub_target,
            "farewell": farewell,
        }
        if isinstance(exit_profile, dict) and exit_profile.get("aliases"):
            exit_summary["aliases"] = list(exit_profile["aliases"])

        return {"mc": mc_payload, "exit_summary": exit_summary}

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
            "exit_profile": self.get_exit_profile(player_id) if player_id else None,
        }

    def get_exit_profile(self, player_id: str) -> Optional[Dict[str, Any]]:
        profile = self.players.get(player_id, {}).get("exit_profile")
        if isinstance(profile, dict):
            return dict(profile)
        return None

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
    # Scene metadata helpers
    # ============================================================
    def _attach_scene_metadata(self, mc_payload: Dict[str, Any], level: Level) -> None:
        """Enrich world patches with scene metadata consumed by the plugin."""

        if not isinstance(mc_payload, dict):
            return

        existing = mc_payload.get("_scene")
        scene_meta = dict(existing) if isinstance(existing, dict) else {}

        level_id = getattr(level, "level_id", None)
        if level_id and "level_id" not in scene_meta:
            scene_meta["level_id"] = level_id

        if "scene" not in scene_meta:
            scene_meta["scene"] = True

        scene_cfg = getattr(level, "scene", None)
        scene_world = getattr(scene_cfg, "world", None) if scene_cfg else None
        if scene_world and "scene_world" not in scene_meta:
            scene_meta["scene_world"] = scene_world

        radius = self._estimate_scene_radius(mc_payload)
        if radius is not None and "radius" not in scene_meta:
            scene_meta["radius"] = radius

        scene_meta["ts"] = time.time()

        if scene_meta:
            mc_payload["_scene"] = scene_meta

    def _estimate_scene_radius(self, mc_payload: Dict[str, Any]) -> Optional[float]:
        """Best-effort radius guess so the client can size cleanup triggers."""

        build = mc_payload.get("build")
        if isinstance(build, dict):
            for key in ("radius", "size"):
                value = build.get(key)
                if isinstance(value, (int, float)):
                    return float(value)

        build_multi = mc_payload.get("build_multi")
        if isinstance(build_multi, list):
            for entry in build_multi:
                if not isinstance(entry, dict):
                    continue
                for key in ("radius", "size"):
                    value = entry.get(key)
                    if isinstance(value, (int, float)):
                        return float(value)
        return None

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

        exit_profile = self._build_exit_profile(level)
        if exit_profile:
            p["exit_profile"] = exit_profile
        else:
            p.pop("exit_profile", None)

        self.graph.update_trajectory(
            player_id,
            level.level_id,
            "enter",
            {"title": level.title},
        )

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
        self._attach_scene_metadata(base_mc, level)

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

        self._prepare_phase2_state(player_id, level)

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

    def _build_exit_profile(self, level: Level) -> Optional[Dict[str, Any]]:
        exit_cfg = getattr(level, "exit", None)
        if not exit_cfg:
            return None

        aliases: List[str] = []
        alias_source = getattr(exit_cfg, "phrase_aliases", None)
        if isinstance(alias_source, (list, tuple)):
            aliases = [alias.strip() for alias in alias_source if isinstance(alias, str) and alias.strip()]
        elif isinstance(alias_source, str) and alias_source.strip():
            aliases = [token.strip() for token in alias_source.split("|") if token.strip()]

        if not aliases:
            aliases = list(self.DEFAULT_EXIT_ALIASES)
        else:
            lower_aliases = {alias.lower() for alias in aliases}
            for default_alias in self.DEFAULT_EXIT_ALIASES:
                if default_alias.lower() not in lower_aliases:
                    aliases.append(default_alias)

        profile: Dict[str, Any] = {
            "level_id": getattr(level, "level_id", None),
            "aliases": aliases,
            "return_spawn": getattr(exit_cfg, "return_spawn", None),
        }

        farewell = getattr(exit_cfg, "farewell", None)
        if isinstance(farewell, str) and farewell.strip():
            profile["farewell"] = farewell.strip()

        teleport_cfg = getattr(exit_cfg, "teleport", None)
        target: Optional[Dict[str, Any]] = None

        if teleport_cfg:
            x = getattr(teleport_cfg, "x", None)
            y = getattr(teleport_cfg, "y", None)
            z = getattr(teleport_cfg, "z", None)
            if None not in (x, y, z):
                target = {
                    "world": getattr(teleport_cfg, "world", None)
                    or getattr(getattr(level, "scene", None), "world", None),
                    "x": float(x),
                    "y": float(y),
                    "z": float(z),
                    "yaw": float(getattr(teleport_cfg, "yaw", 0.0) or 0.0),
                    "pitch": float(getattr(teleport_cfg, "pitch", 0.0) or 0.0),
                }

        if not target:
            spawn_name = getattr(exit_cfg, "return_spawn", None)
            if spawn_name and spawn_name in self.DEFAULT_RETURN_SPAWNS:
                target = dict(self.DEFAULT_RETURN_SPAWNS[spawn_name])

        if not target:
            default_target = self.DEFAULT_RETURN_SPAWNS.get("KunmingLakeHub")
            if default_target:
                target = dict(default_target)

        if target:
            profile["teleport"] = target

        return profile

    def _resolve_exit_target(self, exit_profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not exit_profile:
            return self.DEFAULT_RETURN_SPAWNS.get("KunmingLakeHub")

        if isinstance(exit_profile, dict):
            teleport = exit_profile.get("teleport")
            if isinstance(teleport, dict) and teleport:
                return teleport

            spawn_name = exit_profile.get("return_spawn")
            if isinstance(spawn_name, str):
                resolved = self.DEFAULT_RETURN_SPAWNS.get(spawn_name)
                if resolved:
                    return resolved

        return self.DEFAULT_RETURN_SPAWNS.get("KunmingLakeHub")

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

        beat_result = self._process_beat_progress(player_id, world_state, action)

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
        pending_nodes = p.setdefault("pending_nodes", [])

        primary_node = beat_result.get("node")

        if primary_node and node:
            pending_nodes.append(node)
        elif not primary_node:
            primary_node = node

        if primary_node:
            node = primary_node
            try:
                pending_nodes.remove(primary_node)
            except ValueError:
                pass
            p["nodes"].append(primary_node)
            p["messages"].append(
                {
                    "role": "assistant",
                    "content": f"{primary_node.get('title', '')}\n{primary_node.get('text', '')}".strip(),
                }
            )
            cur_level = p["level"].level_id
            self.minimap.mark_unlocked(player_id, cur_level)
        elif pending_nodes:
            node = pending_nodes.pop(0)
            p["nodes"].append(node)
            p["messages"].append(
                {
                    "role": "assistant",
                    "content": f"{node.get('title', '')}\n{node.get('text', '')}".strip(),
                }
            )
            cur_level = p["level"].level_id
            self.minimap.mark_unlocked(player_id, cur_level)

        patch = self._merge_patch(beat_result.get("world_patch"), patch)
        for pending in p.get("pending_patches", []):
            patch = self._merge_patch(pending, patch)
        p["pending_patches"] = []

        # 结束标记
        if mc_patch.get("ending"):
            p["ended"] = True

        # 时间戳（仅统计，不再作为 gating）
        now = time.time()
        if say and say.strip():
            p["last_say_time"] = now
        else:
            p["last_time"] = now

        quest_updates = quest_runtime.check_completion(p["level"], player_id)
        if quest_updates:
            patch = self._merge_patch(quest_updates.get("world_patch"), patch)
            additional_nodes = quest_updates.get("nodes") or []
            if additional_nodes:
                p.setdefault("pending_nodes", []).extend(additional_nodes)
            completed = quest_updates.get("summary")
            if completed:
                p.setdefault("pending_nodes", []).append(completed)

        return option, node, patch

    # ============================================================
    # Phase 2 helpers (private)
    # ============================================================
    def _prepare_phase2_state(self, player_id: str, level: Level) -> None:
        player_state = self.players[player_id]
        player_state.pop("pending_nodes", None)
        player_state.pop("pending_patches", None)

        beats = list(getattr(level, "beats", []) or [])
        beat_ids: List[str] = []
        beats_by_id: Dict[str, Any] = {}
        for idx, beat in enumerate(beats):
            beat_id = getattr(beat, "id", None) or f"beat_{idx:02d}"
            beat_ids.append(beat_id)
            beats_by_id[beat_id] = beat
        player_state["beat_state"] = {
            "order": beat_ids,
            "index": 0,
            "by_id": beats_by_id,
            "completed": set(),
            "event_map": {},
        }

        self.event_manager.unregister(player_id)

        quest_runtime.load_level_tasks(level, player_id)

        for beat_id in beat_ids:
            beat = beats_by_id.get(beat_id)
            if beat:
                self._register_trigger(player_id, level, beat_id, beat)

        initial_updates = self._auto_trigger_beats(player_id, level)
        for update in initial_updates:
            self._queue_beat_update(player_id, update)

    def _register_trigger(self, player_id: str, level: Level, beat_id: str, beat: Any) -> None:
        trigger_spec = self._parse_trigger(getattr(beat, "trigger", None))

        if trigger_spec["kind"] in {"near", "interact", "item_use"}:
            definition = {"type": trigger_spec["kind"]}
            if trigger_spec["value"]:
                key, value = self._parse_key_value(trigger_spec["value"])
                if key:
                    definition[key] = value
                else:
                    if trigger_spec["kind"] == "near":
                        definition["entity"] = trigger_spec["value"]
                    elif trigger_spec["kind"] == "interact":
                        definition["targets"] = [trigger_spec["value"]]
                    elif trigger_spec["kind"] == "item_use":
                        definition["items"] = [trigger_spec["value"]]

            event_id = f"{player_id}:{beat_id}"

            def _callback(payload: Dict[str, Any], pid: str = player_id, bid: str = beat_id) -> None:
                normalized = {
                    "event_type": payload.get("type"),
                    "target": payload.get("config", {}).get("target")
                    or payload.get("config", {}).get("entity")
                    or payload.get("config", {}).get("items"),
                    "meta": payload.get("config", {}),
                }
                quest_runtime.record_event(pid, normalized)
                update = self._activate_beat(pid, bid, level, source="event_manager", context={"payload": payload})
                if update:
                    self._queue_beat_update(pid, update)

            self.event_manager.register(player_id, event_id, definition, _callback)
            state = self.players[player_id].setdefault("beat_state", {})
            state.setdefault("event_map", {})[event_id] = beat_id

    def _auto_trigger_beats(self, player_id: str, level: Level) -> List[Dict[str, Any]]:
        updates: List[Dict[str, Any]] = []
        while True:
            beat = self._current_pending_beat(player_id)
            if not beat:
                break
            parsed = self._parse_trigger(getattr(beat, "trigger", None))
            if parsed["kind"] in {"auto", "on_enter", "immediate", ""}:
                beat_state = self.players[player_id].setdefault("beat_state", {})
                beat_id = next((identifier for identifier, candidate in (beat_state.get("by_id") or {}).items() if candidate is beat), None)
                if beat_id is None:
                    beat_id = getattr(beat, "id", None) or ""
                update = self._activate_beat(player_id, beat_id, level, source="auto", chain=False)
                if update:
                    updates.append(update)
            else:
                break
        return updates

    def _current_pending_beat(self, player_id: str) -> Optional[Any]:
        player_state = self.players.get(player_id, {})
        beat_state = player_state.get("beat_state") or {}
        order = beat_state.get("order") or []
        completed = beat_state.get("completed") or set()
        for beat_id in order:
            if beat_id not in completed:
                return beat_state.get("by_id", {}).get(beat_id)
        return None

    def _process_beat_progress(
        self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]
    ) -> Dict[str, Any]:
        player_state = self.players[player_id]
        beat_state = player_state.get("beat_state") or {}
        if not beat_state.get("order"):
            return {}

        updates: List[Dict[str, Any]] = []

        triggered_ids = self.event_manager.evaluate(player_id, action, world_state)
        for event_id in triggered_ids:
            beat_id = beat_state.get("event_map", {}).get(event_id)
            if beat_id:
                beat = beat_state.get("by_id", {}).get(beat_id)
                if beat:
                    updates.append(self._activate_beat(player_id, beat_id, self.players[player_id]["level"], source="event_manager"))

        say = action.get("say")
        if isinstance(say, str) and say.strip():
            updates.extend(self._check_keyword_triggers(player_id, say))

        result_patch: Dict[str, Any] = {}
        node: Optional[Dict[str, Any]] = None
        extra_nodes: List[Dict[str, Any]] = []

        for update in updates:
            if not update:
                continue
            result_patch = self._merge_patch(result_patch, update.get("world_patch"))
            primary = update.get("node")
            if primary and not node:
                node = primary
            elif primary:
                extra_nodes.append(primary)
            extra_nodes.extend(update.get("extra_nodes", []))
            self._queue_beat_update(player_id, update, include_primary=False, include_patch=False)

        return {
            "world_patch": result_patch,
            "node": node,
            "extra_nodes": extra_nodes,
        }

    def _check_keyword_triggers(self, player_id: str, say_text: str) -> List[Dict[str, Any]]:
        player_state = self.players[player_id]
        beat_state = player_state.get("beat_state") or {}
        if not beat_state:
            return []

        lowered = say_text.lower()
        updates: List[Dict[str, Any]] = []
        for beat_id in beat_state.get("order", []):
            if beat_id in beat_state.get("completed", set()):
                continue
            beat = beat_state.get("by_id", {}).get(beat_id)
            if not beat:
                continue
            parsed = self._parse_trigger(getattr(beat, "trigger", None))
            if parsed["kind"] in {"keyword", "say", "command"}:
                values = [value.strip() for value in (parsed["value"].split("|") if parsed["value"] else []) if value.strip()]
                if not values:
                    continue
                if any(value.lower() in lowered for value in values):
                    updates.append(self._activate_beat(player_id, beat_id, self.players[player_id]["level"], source="keyword"))

        return updates

    def _activate_beat(
        self,
        player_id: str,
        beat_id: str,
        level: Level,
        *,
        source: str,
        context: Optional[Dict[str, Any]] = None,
        chain: bool = True,
    ) -> Optional[Dict[str, Any]]:
        _ = context  # context reserved for future bridge metadata
        player_state = self.players[player_id]
        beat_state = player_state.get("beat_state") or {}
        if not beat_state:
            return None

        beats_by_id = beat_state.get("by_id", {})
        beat = beats_by_id.get(beat_id)
        if not beat:
            return None

        completed = beat_state.setdefault("completed", set())
        if beat_id in completed:
            return None

        completed.add(beat_id)
        self.advance_with_beat(player_id, beat_id)

        event_id = f"{player_id}:{beat_id}"
        self.event_manager.unregister(player_id, event_id)

        beat_patch = self._resolve_scene_patch(level, beat)
        quest_update = quest_runtime.issue_tasks_on_beat(level, player_id, {"id": beat_id})
        rule_refs = list(getattr(beat, "rule_refs", []) or [])
        if rule_refs:
            quest_runtime.activate_rule_refs(level, player_id, rule_refs)

        extra_nodes = []
        if quest_update and quest_update.get("nodes"):
            extra_nodes.extend(quest_update["nodes"])

        node = {
            "title": f"剧情推进 · {beat_id}",
            "text": f"触发来源：{source}",
            "type": "beat",
            "beat_id": beat_id,
        }

        mc_patch = beat_patch.setdefault("mc", {})
        scene_meta: Dict[str, Any] = {
            "beat_id": beat_id,
            "source": source,
            "ts": time.time(),
            "level_id": getattr(level, "level_id", None),
        }
        if rule_refs:
            scene_meta["rule_refs"] = list(rule_refs)
        mc_patch.setdefault("_scene", scene_meta)

        if chain:
            chained_updates = self._auto_trigger_beats(player_id, level)
            for chained in chained_updates:
                beat_patch = self._merge_patch(chained.get("world_patch"), beat_patch)
                chained_node = chained.get("node")
                if chained_node:
                    extra_nodes.append(chained_node)
                extra_nodes.extend(chained.get("extra_nodes", []))

        return {
            "world_patch": beat_patch,
            "node": node,
            "extra_nodes": extra_nodes,
        }

    def _queue_beat_update(
        self,
        player_id: str,
        update: Optional[Dict[str, Any]],
        *,
        include_primary: bool = True,
        include_patch: bool = True,
    ) -> None:
        if not update:
            return

        player_state = self.players[player_id]
        if include_patch and update.get("world_patch"):
            player_state.setdefault("pending_patches", []).append(update["world_patch"])

        nodes_to_store: List[Dict[str, Any]] = []
        if include_primary and update.get("node"):
            nodes_to_store.append(update["node"])
        nodes_to_store.extend(update.get("extra_nodes", []) or [])

        if nodes_to_store:
            player_state.setdefault("pending_nodes", []).extend(nodes_to_store)

    def _resolve_scene_patch(self, level: Level, beat: Any) -> Dict[str, Any]:
        scene_key = getattr(beat, "scene_patch", None)
        patches = getattr(level, "scene_patches", None)
        if isinstance(patches, dict) and scene_key in patches:
            candidate = patches.get(scene_key)
            if isinstance(candidate, dict):
                return dict(candidate)
        if scene_key:
            return {"mc": {"tell": f"{level.title} · 场景变化：{scene_key}"}}
        return {}

    @staticmethod
    def _merge_patch(primary: Optional[Dict[str, Any]], secondary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not primary and not secondary:
            return {}
        if not secondary:
            return dict(primary or {})
        if not primary:
            return dict(secondary or {})

        merged = dict(secondary or {})
        for key, value in (primary or {}).items():
            if key == "mc" and isinstance(value, dict):
                existing = merged.get("mc")
                if isinstance(existing, dict):
                    merged["mc"] = {**existing, **value}
                else:
                    merged["mc"] = dict(value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _parse_trigger(raw: Optional[str]) -> Dict[str, str]:
        if not raw:
            return {"kind": "", "value": ""}
        token = raw.strip().lower()
        if ":" in token:
            kind, value = token.split(":", 1)
            return {"kind": kind.strip(), "value": value.strip()}
        return {"kind": token, "value": ""}

    @staticmethod
    def _parse_key_value(raw: str) -> Tuple[Optional[str], Optional[str]]:
        if "=" not in raw:
            return None, None
        key, value = raw.split("=", 1)
        return key.strip(), value.strip()

    def _handle_rule_catalyst(self, player_id: str, payload: Dict[str, Any]) -> None:
        beat_state = self.players.get(player_id, {}).get("beat_state") or {}
        matches: List[str] = []
        event_type = str(payload.get("event_type") or "").lower()
        quest_event = str(payload.get("payload", {}).get("quest_event") or "").lower()

        for beat_id, beat in (beat_state.get("by_id") or {}).items():
            if beat_id in (beat_state.get("completed") or set()):
                continue
            refs = [ref.lower() for ref in getattr(beat, "rule_refs", []) or []]
            if not refs:
                continue
            if event_type and event_type in refs:
                matches.append(beat_id)
                continue
            if quest_event and quest_event in refs:
                matches.append(beat_id)

        level = self.players.get(player_id, {}).get("level")
        if not level:
            return
        for bid in matches:
            update = self._activate_beat(player_id, bid, level, source="rule_event", context=payload)
            if update:
                self._queue_beat_update(player_id, update)

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