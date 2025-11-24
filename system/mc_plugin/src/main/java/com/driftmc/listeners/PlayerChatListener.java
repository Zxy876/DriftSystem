// src/main/java/com/driftmc/listeners/PlayerChatListener.java
package com.driftmc.listeners;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.json.JSONObject;

import com.driftmc.BackendClient;
import com.driftmc.DriftMCPlugin;
import com.driftmc.actions.WorldPatchExecutor;

public class PlayerChatListener implements Listener {

    private final DriftMCPlugin plugin;
    private final BackendClient backend;
    private final WorldPatchExecutor executor;

    public PlayerChatListener(
            DriftMCPlugin plugin,
            BackendClient backend,
            WorldPatchExecutor executor
    ) {
        this.plugin = plugin;
        this.backend = backend;
        this.executor = executor;
    }

    @EventHandler
    public void onChat(AsyncPlayerChatEvent event) {
        Player player = event.getPlayer();
        String text = event.getMessage();

        // 不让聊天原样广播（你的输入要变成“指令/剧情”）
        event.setCancelled(true);

        plugin.getLogger().info("[CHAT->BACKEND] " + player.getName() + ": " + text);

        backend.sendSay(player, text, new BackendClient.BackendResponse() {

            @Override
            public void onSuccess(JSONObject resp) {

                Bukkit.getScheduler().runTask(plugin, () -> {

                    plugin.getLogger().info("[BACKEND OK] " + resp.toString());

                    // 1) 显示剧情
                    if (resp.has("story_node") && !resp.isNull("story_node")) {
                        JSONObject node = resp.getJSONObject("story_node");
                        String title = node.optString("title", "剧情");
                        String storyText = node.optString("text", "");
                        player.sendMessage("§b[" + title + "] §f" + storyText);
                    }

                    // 2) 应用世界修改（造物主 patch）
                    if (resp.has("world_patch") && !resp.isNull("world_patch")) {
                        executor.apply(player, resp.getJSONObject("world_patch"));
                    }
                });
            }

            @Override
            public void onError(Exception error) {
                Bukkit.getScheduler().runTask(plugin, () -> {
                    plugin.getLogger().warning("[BACKEND ERROR] " + error.getMessage());
                    player.sendMessage("§c后端连接失败：" + error.getMessage());
                });
            }
        });
    }
}