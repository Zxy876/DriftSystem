# backend/app/core/npc/npc_behavior_engine.py
"""
NPC行为引擎：处理NPC的AI驱动行为
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class NPCBehavior:
    """NPC行为定义"""
    type: str  # patrol, stand, interact, quest, wander, etc.
    config: Dict[str, Any]
    description: str


class NPCBehaviorEngine:
    """NPC行为引擎"""
    
    def __init__(self):
        self.active_npcs: Dict[str, Dict[str, Any]] = {}  # level_id -> npc_data
    
    def register_npc(self, level_id: str, npc_data: Dict[str, Any]):
        """注册NPC及其行为"""
        self.active_npcs[level_id] = npc_data
    
    def get_npc_behaviors(self, level_id: str) -> List[NPCBehavior]:
        """获取NPC的所有行为"""
        if level_id not in self.active_npcs:
            return []
        
        npc_data = self.active_npcs[level_id]
        behaviors = npc_data.get("behaviors", [])
        
        return [
            NPCBehavior(
                type=b.get("type", "stand"),
                config=b,
                description=b.get("description", "")
            )
            for b in behaviors
        ]
    
    def get_npc_ai_hints(self, level_id: str) -> str:
        """获取NPC的AI提示（用于对话生成）"""
        if level_id not in self.active_npcs:
            return ""
        
        return self.active_npcs[level_id].get("ai_hints", "")
    
    def handle_player_interaction(
        self, 
        level_id: str, 
        player_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理玩家与NPC的交互
        返回NPC的响应和行为变化
        """
        if level_id not in self.active_npcs:
            return None
        
        npc_data = self.active_npcs[level_id]
        behaviors = npc_data.get("behaviors", [])
        
        # 检查是否触发任务
        for behavior in behaviors:
            if behavior.get("type") == "quest":
                keywords = behavior.get("trigger_keywords", [])
                if any(kw in player_message for kw in keywords):
                    return {
                        "type": "quest_trigger",
                        "quest_name": behavior.get("quest_name"),
                        "rewards": behavior.get("rewards", []),
                        "npc_response": f"看来你对{behavior.get('quest_name')}感兴趣！让我来帮助你。"
                    }
        
        # 检查普通互动
        for behavior in behaviors:
            if behavior.get("type") == "interact":
                keywords = behavior.get("trigger_keywords", [])
                if not keywords or any(kw in player_message for kw in keywords):
                    return {
                        "type": "dialogue",
                        "messages": behavior.get("messages", []),
                        "npc_name": npc_data.get("name", "NPC")
                    }
        
        return None
    
    def generate_mc_commands(
        self, 
        level_id: str, 
        spawn_location: Dict[str, float]
    ) -> List[str]:
        """
        根据NPC行为生成MC命令
        """
        if level_id not in self.active_npcs:
            return []
        
        npc_data = self.active_npcs[level_id]
        behaviors = npc_data.get("behaviors", [])
        commands = []
        
        base_x = spawn_location.get("x", 0)
        base_y = spawn_location.get("y", 100)
        base_z = spawn_location.get("z", 0)
        
        for behavior in behaviors:
            btype = behavior.get("type")
            
            if btype == "patrol":
                # 巡逻路径标记
                path = behavior.get("path", [])
                for i, point in enumerate(path):
                    marker_x = base_x + point.get("dx", 0)
                    marker_z = base_z + point.get("dz", 0)
                    commands.append(
                        f"summon armor_stand {marker_x} {base_y} {marker_z} "
                        f"{{Invisible:1b,Marker:1b,CustomName:'\"patrol_point_{i}\"'}}"
                    )
            
            elif btype == "particle":
                # 粒子效果
                particle_type = behavior.get("particle", "end_rod")
                commands.append(
                    f"particle {particle_type} {base_x} {base_y + 1} {base_z} "
                    f"0.5 0.5 0.5 0.1 10 force"
                )
        
        return commands
    
    def get_behavior_context_for_ai(self, level_id: str) -> str:
        """
        获取NPC行为的上下文描述，用于AI对话生成
        """
        if level_id not in self.active_npcs:
            return ""
        
        npc_data = self.active_npcs[level_id]
        ai_hints = npc_data.get("ai_hints", "")
        behaviors = npc_data.get("behaviors", [])
        
        behavior_descriptions = []
        for b in behaviors:
            if b.get("description"):
                behavior_descriptions.append(f"- {b.get('description')}")
        
        context = f"""
【NPC性格与背景】
{ai_hints}

【NPC当前行为】
{chr(10).join(behavior_descriptions) if behavior_descriptions else "- 站立等待"}

【可触发的互动】
"""
        
        # 添加可触发的关键词提示
        for b in behaviors:
            if b.get("type") == "quest":
                keywords = ", ".join(b.get("trigger_keywords", []))
                context += f"- 任务「{b.get('quest_name')}」: 关键词包括 {keywords}\n"
        
        return context.strip()


# 全局实例
npc_engine = NPCBehaviorEngine()
