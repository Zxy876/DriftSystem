package com.driftmc.intent2;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public class IntentDispatcher2 {

    private final Plugin plugin;

    public IntentDispatcher2(Plugin plugin) {
        this.plugin = plugin;
    }

    public void dispatch(Player p, IntentResponse2 intent) {
        switch (intent.type) {
            case SHOW_MINIMAP -> showMinimap(p, intent);
            case GOTO_NEXT_LEVEL, GOTO_LEVEL -> gotoLevel(p, intent);
            case SAY_ONLY -> p.sendMessage("§d[心悦宇宙] " + intent.rawText);
            default -> {
                // UNKNOWN -> fallback to story engine
            }
        }
    }

    private void showMinimap(Player p, IntentResponse2 intent) {
        JsonObject mm = intent.minimap;
        if (mm == null) {
            p.sendMessage("§c[小地图] 后端没有返回地图数据。");
            return;
        }

        String currentLevel =
                mm.has("current_level") && !mm.get("current_level").isJsonNull()
                        ? mm.get("current_level").getAsString()
                        : "无";

        String next =
                mm.has("recommended_next") && !mm.get("recommended_next").isJsonNull()
                        ? mm.get("recommended_next").getAsString()
                        : "无";

        p.sendMessage("§b========== 心悦 · 小地图 ==========");
        p.sendMessage("§7当前关卡: §a" + currentLevel);
        p.sendMessage("§7推荐下一站: §d" + next);
        p.sendMessage("§7你可以说：“带我去下一关” 或 “去 level_08”");
        p.sendMessage("§b================================");
    }

    private void gotoLevel(Player p, IntentResponse2 intent) {
        if (intent.levelId == null) {
            p.sendMessage("§c[传送] AI 没给目标关卡。");
            return;
        }

        JsonObject mm = intent.minimap;
        if (mm == null || !mm.has("nodes")) {
            p.sendMessage("§c[传送] 地图缺失。");
            return;
        }

        JsonArray nodes = mm.getAsJsonArray("nodes");

        Integer x = null;
        Integer z = null;

        for (int i = 0; i < nodes.size(); i++) {
            JsonObject n = nodes.get(i).getAsJsonObject();

            String lv = n.get("level").getAsString();
            if (!lv.equals(intent.levelId)) continue;

            JsonObject pos = n.getAsJsonObject("pos");

            x = pos.get("x").getAsInt();
            int yIndex = pos.get("y").getAsInt();
            z = yIndex;
            break;
        }

        if (x == null || z == null) {
            p.sendMessage("§c[传送] 找不到关卡坐标。");
            return;
        }

        int tx = x;
        int ty = 80;
        int tz = z;

        Bukkit.getScheduler().runTask(plugin, () -> {
            Location loc = new Location(p.getWorld(), tx, ty, tz);
            p.teleport(loc);

            p.sendMessage("§a已传送到 §f" + intent.levelId +
                    " §7(" + tx + ", " + ty + ", " + tz + ")");
        });
    }
}