package com.driftmc.intent;

import java.lang.reflect.Type;
import java.util.HashMap;
import java.util.Map;

import org.bukkit.ChatColor;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.dsl.DslExecutor;
import com.driftmc.npc.NPCManager;
import com.driftmc.session.PlayerSessionManager;
import com.driftmc.world.WorldPatchExecutor;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

/**
 * IntentRouter
 * 负责处理自然语言 → 后端 → 世界补丁
 */
public class IntentRouter {

    private static final Gson GSON = new Gson();

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final DslExecutor dsl;
    private final NPCManager npcs;
    private final WorldPatchExecutor world;
    private final PlayerSessionManager sessions;

    public IntentRouter(
            JavaPlugin plugin,
            BackendClient backend,
            DslExecutor dsl,
            NPCManager npcs,
            WorldPatchExecutor world,
            PlayerSessionManager sessions
    ) {
        this.plugin = plugin;
        this.backend = backend;
        this.dsl = dsl;
        this.npcs = npcs;
        this.world = world;
        this.sessions = sessions;
    }

    /**
     * 玩家说话 → 走后端故事引擎 → world_patch → 世界变化
     */
    public void handlePlayerSpeak(Player player, String text) {

        if (text == null || text.isEmpty()) return;

        String playerId = player.getName();

        try {
            // ------- 构造请求 -------
            Map<String, Object> bodyMap = new HashMap<>();
            bodyMap.put("world_state", new HashMap<>());

            Map<String, Object> action = new HashMap<>();
            action.put("say", text);
            bodyMap.put("action", action);

            String body = GSON.toJson(bodyMap);

            // ------- 请求后端 -------
            String path = "/story/advance/" + playerId;
            String resp = backend.postJson(path, body);

            plugin.getLogger().info("[IntentRouter] speak='" + text + "', resp=" + resp);

            // ------- 解析 node 中的文本 -------
            JsonObject root = JsonParser.parseString(resp).getAsJsonObject();
            if (root.has("node") && root.get("node").isJsonObject()) {
                JsonObject node = root.getAsJsonObject("node");
                String title = node.has("title") ? node.get("title").getAsString() : "";
                String t = node.has("text") ? node.get("text").getAsString() : "";

                if (!title.isEmpty()) {
                    player.sendMessage(ChatColor.AQUA + "【" + title + "】");
                }
                if (!t.isEmpty()) {
                    player.sendMessage(ChatColor.WHITE + t);
                }
            }

            // ------- 执行 world_patch -------
            if (root.has("world_patch") && root.get("world_patch").isJsonObject()) {
                JsonObject patchObj = root.getAsJsonObject("world_patch");
                Type type = new TypeToken<Map<String, Object>>() {}.getType();
                Map<String, Object> patch = GSON.fromJson(patchObj, type);

                plugin.getLogger().info("[IntentRouter] world_patch(from backend) = " + patch);

                if (patch != null && !patch.isEmpty()) {
                    Object mcObj = patch.get("mc");

                    @SuppressWarnings("unchecked")
                    Map<String, Object> mcPatch = (mcObj instanceof Map)
                            ? (Map<String, Object>) mcObj
                            : patch;

                    plugin.getLogger().info("[IntentRouter] mc_patch = " + mcPatch);

                    world.execute(player, mcPatch);
                }
            }

        } catch (Exception e) {
            plugin.getLogger().warning("[IntentRouter] handlePlayerSpeak error: " + e.getMessage());
            player.sendMessage(ChatColor.RED + "❌ AI 解析失败: " + e.getMessage());
        }
    }
}