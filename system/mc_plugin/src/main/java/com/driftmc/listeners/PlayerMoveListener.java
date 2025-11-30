package com.driftmc.listeners;

import java.util.HashMap;
import java.util.Map;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerMoveEvent;

import com.driftmc.backend.BackendClient;
import com.driftmc.world.WorldPatchExecutor;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

public class PlayerMoveListener implements Listener {

    private final BackendClient backend;
    private final WorldPatchExecutor worldRunner;
    private final Gson gson = new Gson();

    public PlayerMoveListener(BackendClient backend, WorldPatchExecutor worldRunner) {
        this.backend = backend;
        this.worldRunner = worldRunner;
    }

    @EventHandler
    public void onMove(PlayerMoveEvent event) {

        Player player = event.getPlayer();
        String playerId = player.getName();

        double x = player.getLocation().getX();
        double y = player.getLocation().getY();
        double z = player.getLocation().getZ();
        double speed = player.getVelocity().length();

        // === 正确 JSON 结构 ===
        Map<String, Object> move = new HashMap<>();
        move.put("x", x);
        move.put("y", y);
        move.put("z", z);
        move.put("speed", speed);
        move.put("moving", speed > 0.01);

        Map<String, Object> action = new HashMap<>();
        action.put("move", move);

        Map<String, Object> payload = new HashMap<>();
        payload.put("player_id", playerId);
        payload.put("action", action);

        String json = gson.toJson(payload);

        // ---- 异步发送 ----
        Bukkit.getScheduler().runTaskAsynchronously(worldRunner.getPlugin(), () -> {
            try {
                String respStr = backend.postJson("/world/apply", json);

                if (respStr == null || respStr.isEmpty()) return;

                Map<String, Object> resp = gson.fromJson(
                        respStr,
                        new TypeToken<Map<String, Object>>(){}.getType()
                );

                Object patchObj = resp.get("world_patch");
                if (!(patchObj instanceof Map)) return;

                @SuppressWarnings("unchecked")
                Map<String, Object> patch = (Map<String, Object>) patchObj;

                // ---- 回主线程执行补丁 ----
                Bukkit.getScheduler().runTask(worldRunner.getPlugin(), () -> {
                    worldRunner.execute(player, patch);
                });

            } catch (Exception e) {
                // 静默
            }
        });
    }
}