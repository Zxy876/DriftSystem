package com.driftmc.actor;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.reflect.TypeToken;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

/**
 * 演员控制器（v1.21 最小版）。
 * 仅消费演员控制意图：聊天/姿态/视角/罗盘提示，不做任何世界写入或方块修改。
 */
public final class ActorController {

    private static final Gson GSON = new Gson();
    private static final long TICK_INTERVAL = 40L; // 2s

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final AtomicBoolean running = new AtomicBoolean(false);
    private BukkitTask task;

    public ActorController(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    public void start() {
        if (!running.compareAndSet(false, true)) {
            return;
        }
        this.task = Bukkit.getScheduler().runTaskTimerAsynchronously(plugin, this::pollOnce, 40L, TICK_INTERVAL);
        plugin.getLogger().info("[ActorController] 已启动（仅演员动作，无世界写入）。");
    }

    public void stop() {
        running.set(false);
        if (task != null) {
            task.cancel();
            task = null;
        }
    }

    private void pollOnce() {
        if (!running.get()) {
            return;
        }
        try {
            backend.getAsync("/director/actor/next", new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    plugin.getLogger().log(Level.FINE, "[ActorController] 后端请求失败: {0}", e.getMessage());
                }

                @Override
                public void onResponse(Call call, Response response) throws IOException {
                    int code = response.code();
                    String body = response.body() != null ? response.body().string() : "";
                    response.close();

                    if (code == 204 || code == 404) {
                        return;
                    }
                    if (code != 200) {
                        plugin.getLogger().log(Level.FINE, "[ActorController] 后端返回 {0}: {1}",
                                new Object[] { code, body });
                        return;
                    }
                    if (!running.get()) {
                        return;
                    }
                    JsonObject json;
                    try {
                        json = GSON.fromJson(body, JsonObject.class);
                    } catch (Exception ex) {
                        plugin.getLogger().log(Level.FINE, "[ActorController] 无法解析响应: {0}", body);
                        return;
                    }
                    if (json == null || !json.has("intent")) {
                        return;
                    }
                    JsonObject intentJson = json.getAsJsonObject("intent");
                    String actorId = optString(intentJson, "actor_id");
                    String action = optString(intentJson, "action");
                    Map<String, Object> payload = GSON.fromJson(intentJson.get("payload"),
                            new TypeToken<Map<String, Object>>() {
                            }.getType());
                    if (payload == null) {
                        payload = Map.of();
                    }
                    if (actorId == null || action == null) {
                        return;
                    }
                    Map<String, Object> finalPayload = payload;
                    String finalActorId = actorId;
                    String finalAction = action.toLowerCase();
                    Bukkit.getScheduler().runTask(plugin, () -> dispatch(finalActorId, finalAction, finalPayload));
                }
            });
        } catch (Exception e) {
            plugin.getLogger().log(Level.FINE, "[ActorController] 轮询异常: {0}", e.getMessage());
        }
    }

    private void dispatch(String actorId, String action, Map<String, Object> payload) {
        Player target = findPlayer(actorId);
        if (target == null) {
            plugin.getLogger().log(Level.FINE, "[ActorController] 演员离线: {0}", actorId);
            return;
        }

        switch (action) {
            case "say" -> performSay(target, payload);
            case "emote" -> performEmote(target, payload);
            case "look" -> performLook(target, payload);
            case "turn" -> performTurn(target, payload);
            case "walk_to" -> performWalkTo(target, payload);
            default -> plugin.getLogger().log(Level.FINE, "[ActorController] 未知动作: {0}", action);
        }
    }

    private void performSay(Player player, Map<String, Object> payload) {
        String line = asString(payload.getOrDefault("line", payload.get("text")));
        if (line == null || line.isBlank()) {
            return;
        }
        player.chat(line);
    }

    private void performEmote(Player player, Map<String, Object> payload) {
        String mood = asString(payload.getOrDefault("mood", payload.get("emote")));
        if (mood == null || mood.isBlank()) {
            mood = "...";
        }
        String message = "* " + player.getName() + " " + mood;
        Bukkit.getServer().broadcastMessage(ChatColor.LIGHT_PURPLE + message);
        player.sendActionBar(ChatColor.LIGHT_PURPLE + mood);
    }

    private void performLook(Player player, Map<String, Object> payload) {
        double yaw = asDouble(payload.get("yaw"), player.getLocation().getYaw());
        double pitch = asDouble(payload.get("pitch"), player.getLocation().getPitch());
        Location loc = player.getLocation().clone();
        loc.setYaw((float) yaw);
        loc.setPitch((float) pitch);
        player.teleport(loc);
    }

    private void performTurn(Player player, Map<String, Object> payload) {
        double delta = asDouble(payload.get("delta"), asDouble(payload.get("yaw"), 0.0d));
        Location loc = player.getLocation().clone();
        loc.setYaw((float) (loc.getYaw() + delta));
        player.teleport(loc);
    }

    private void performWalkTo(Player player, Map<String, Object> payload) {
        World world = player.getWorld();
        double x = asDouble(payload.get("x"), player.getLocation().getX());
        double y = asDouble(payload.get("y"), player.getLocation().getY());
        double z = asDouble(payload.get("z"), player.getLocation().getZ());
        Location target = new Location(world, x, y, z);
        player.setCompassTarget(target);
        player.sendMessage(ChatColor.AQUA + "→ 请走向 " + formatCoords(target));
        player.sendActionBar(ChatColor.AQUA + "指向罗盘: " + formatCoords(target));
    }

    private static String formatCoords(Location loc) {
        return String.format("[%.1f, %.1f, %.1f]", loc.getX(), loc.getY(), loc.getZ());
    }

    private Player findPlayer(String actorId) {
        try {
            UUID uuid = UUID.fromString(actorId);
            return Bukkit.getPlayer(uuid);
        } catch (IllegalArgumentException ignored) {
        }
        return Bukkit.getPlayerExact(actorId);
    }

    private static String optString(JsonObject obj, String key) {
        if (obj == null || !obj.has(key)) {
            return null;
        }
        try {
            return obj.get(key).getAsString();
        } catch (Exception e) {
            return null;
        }
    }

    private static String asString(Object value) {
        if (value == null) {
            return null;
        }
        return String.valueOf(value);
    }

    private static double asDouble(Object value, double def) {
        if (value == null) {
            return def;
        }
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (NumberFormatException e) {
            return def;
        }
    }
}
