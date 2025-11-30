from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, Tuple


class MiniMapRenderer:

    def __init__(self):
        base = Path(__file__).resolve().parents[2]

        # 输出路径
        self.output_dir = base / "static" / "minimap"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.png_path = self.output_dir / "minimap.png"

        # 背景：你生成的书本 PNG
        bg_path = self.output_dir / "background.png"
        if bg_path.exists():
            self.background = Image.open(bg_path).convert("RGBA")
        else:
            self.background = Image.new("RGBA", (1024, 1024), (0, 0, 0, 255))

        # 风格色彩
        self.color_locked = (70, 150, 255, 255)       # 蓝光
        self.color_unlocked = (50, 255, 200, 255)     # 青绿
        self.color_player = (255, 255, 90, 255)       # 黄色
        self.color_text = (230, 240, 255, 255)

        # 字体
        try:
            self.font = ImageFont.truetype(
                "/Library/Fonts/Arial Unicode.ttf", 24
            )
        except:
            self.font = ImageFont.load_default()

    # ------------------------------------------------------------------
    def render(self, nodes: list, player_pos: Tuple[float, float, float] = None):
        canvas = self.background.copy()
        draw = ImageDraw.Draw(canvas)

        # 绘制关卡节点
        for node in nodes:
            pos = node["pos"]
            x, y = pos["x"], pos["y"]
            unlocked = node.get("unlocked", False)

            color = self.color_unlocked if unlocked else self.color_locked

            # 外圈光晕
            draw.ellipse((x - 12, y - 12, x + 12, y + 12),
                         fill=(color[0], color[1], color[2], 100))
            # 实心球
            draw.ellipse((x - 7, y - 7, x + 7, y + 7),
                         fill=color)

            draw.text((x + 12, y - 8),
                      node["level"],
                      fill=self.color_text, font=self.font)

        # 玩家位置
        if player_pos:
            px, py, _ = player_pos
            draw.ellipse(
                (px - 8, py - 8, px + 8, py + 8),
                fill=self.color_player
            )

        # 保存
        canvas.save(self.png_path)
        return str(self.png_path)