# backend/app/api/minimap_api.py
from fastapi import APIRouter, Response
import base64
from pathlib import Path
from app.core.story.story_engine import story_engine
from app.core.world.minimap_renderer import MiniMapRenderer

router = APIRouter(prefix="/minimap", tags=["MiniMap"])
renderer = MiniMapRenderer()

# -------------------------------------------------------
# ① 返回 PNG（原功能保留）
# -------------------------------------------------------
@router.get("/png/{player_id}")
def get_minimap_png(player_id: str):
    data = story_engine.minimap.to_dict(player_id)
    nodes = data["nodes"]
    pos = data.get("player_pos")

    png_path = renderer.render(nodes, pos)

    with open(png_path, "rb") as f:
        return Response(f.read(), media_type="image/png")


# -------------------------------------------------------
# ② 给 MC 玩家一张可用地图（必须新增）
# -------------------------------------------------------
@router.get("/give/{player_id}")
def give_map(player_id: str):
    """
    生成 minimap PNG → base64 → 返回 mc_patch
    """
    # --- 生成 minimap PNG ---
    data = story_engine.minimap.to_dict(player_id)
    png_path = renderer.render(data["nodes"], data.get("player_pos"))

    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    # --- 这里返回给 MC 插件，用于 give + 填充地图 ---
    return {
        "status": "ok",
        "mc": {
            "tell": "🗺 小地图已生成。",
            "give_item": "filled_map",
            "map_image": b64
        }
    }