package com.driftmc.scene;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonSyntaxException;
import com.google.gson.reflect.TypeToken;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * Sends Minecraft-side rule events back to the backend so QuestRuntime can react.
 */
public final class RuleEventBridge {

    private static final long DEFAULT_COOLDOWN_MS = 1_500L;

    private static final Type MAP_TYPE = new TypeToken<Map<String, Object>>() {}.getType();

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final SceneAwareWorldPatchExecutor worldPatcher;
    private final Gson gson = new Gson();
    private final Map<String, Long> cooldowns = new ConcurrentHashMap<>();
    private final Map<UUID, PlayerRuleState> playerStates = new ConcurrentHashMap<>();
    private long cooldownMillis = DEFAULT_COOLDOWN_MS;

    public RuleEventBridge(JavaPlugin plugin, BackendClient backend, SceneAwareWorldPatchExecutor worldPatcher) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
        this.backend = Objects.requireNonNull(backend, "backend");
        this.worldPatcher = Objects.requireNonNull(worldPatcher, "worldPatcher");
    }

    public void setCooldownMillis(long millis) {
        this.cooldownMillis = Math.max(0L, millis);
    }

    public void emit(Player player, String eventType) {
        emit(player, eventType, Collections.emptyMap());
    }

    public void emit(Player player, String eventType, Map<String, Object> payload) {
        if (player == null) {
            return;
        }

        final UUID playerId = player.getUniqueId();
        final String playerName = player.getName();

        String type = normalize(eventType);
        if (type.isEmpty()) {
            return;
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("player_id", playerName);
        body.put("event_type", type);
        body.put("payload", payload != null ? new LinkedHashMap<>(payload) : Collections.emptyMap());

        if (shouldThrottle(player, type, body.get("payload"))) {
            return;
        }

        String json = gson.toJson(body);
        backend.postJsonAsync("/world/story/rule-event", json, new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().log(Level.WARNING, "[RuleEventBridge] emit failed: {0}", e.getMessage());
                Bukkit.getScheduler().runTask(plugin, () -> {
                    Player target = Bukkit.getPlayer(playerId);
                    if (target != null && target.isOnline()) {
                        target.sendMessage(ChatColor.RED + "【规则事件】后端暂时没有响应，请稍后再试。");
                    }
                });
            }

            @Override
            public void onResponse(Call call, Response response) {
                try (Response res = response) {
                    if (!res.isSuccessful()) {
                        plugin.getLogger().log(Level.WARNING,
                                "[RuleEventBridge] backend replied HTTP {0}", res.code());
                        return;
                    }
                    ResponseBody body = res.body();
                    if (body == null) {
                        return;
                    }
                    String payloadJson = body.string();
                    handleRuleEventResponse(playerId, playerName, payloadJson);
                } catch (IOException ex) {
                    plugin.getLogger().log(Level.WARNING,
                            "[RuleEventBridge] failed to read response: {0}", ex.getMessage());
                }
            }
        });
    }

    public void emitNearNpc(Player player, String npcName, Location location) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("target", npcName != null ? npcName : "unknown_npc");
        payload.put("quest_event", canonicalize("near", npcName));
        Map<String, Object> pos = extractLocation(location, player);
        if (!pos.isEmpty()) {
            payload.put("location", pos);
        }
        emit(player, "near", payload);
    }

    public void emitChat(Player player, String message) {
        Map<String, Object> payload = new LinkedHashMap<>();
        String text = message != null ? message : "";
        payload.put("text", text);
        payload.put("quest_event", canonicalize("chat", text));
        emit(player, "chat", payload);
    }

    public void emitInteractBlock(Player player, String action, Material material, Location location) {
        Map<String, Object> payload = new LinkedHashMap<>();
        String matName = material != null ? material.name().toLowerCase() : "unknown";
        payload.put("action", action != null ? action : "unknown");
        payload.put("block_type", matName);
        payload.put("quest_event", canonicalize("interact_block", matName));
        Map<String, Object> pos = extractLocation(location, player);
        if (!pos.isEmpty()) {
            payload.put("location", pos);
        }
        emit(player, "interact_block", payload);
    }

    public void emitInteractEntity(Player player, Entity entity, String interaction) {
        Map<String, Object> payload = new LinkedHashMap<>();
        String type = entity != null ? entity.getType().name().toLowerCase() : "unknown";
        payload.put("interaction", interaction != null ? interaction : "unknown");
        payload.put("entity_type", type);
        if (entity != null && entity.getCustomName() != null) {
            payload.put("entity_name", entity.getCustomName());
        }
        payload.put("quest_event", canonicalize("interact_entity", type));
        Map<String, Object> pos = extractLocation(entity != null ? entity.getLocation() : null, player);
        if (!pos.isEmpty()) {
            payload.put("location", pos);
        }
        emit(player, "interact_entity", payload);
    }

    private boolean shouldThrottle(Player player, String eventType, Object payloadObj) {
        if (cooldownMillis <= 0) {
            return false;
        }
        String payloadToken = payloadObj == null ? "" : gson.toJson(payloadObj);
        String key = player.getUniqueId() + ":" + eventType + ":" + payloadToken;
        long now = System.currentTimeMillis();
        Long last = cooldowns.get(key);
        if (last != null && now - last < cooldownMillis) {
            return true;
        }
        cooldowns.put(key, now);
        return false;
    }

    private void handleRuleEventResponse(UUID playerId, String playerName, String json) {
        if (json == null || json.isBlank()) {
            return;
        }

        JsonObject root;
        try {
            JsonElement parsed = JsonParser.parseString(json);
            if (!parsed.isJsonObject()) {
                plugin.getLogger().log(Level.FINE, "[RuleEventBridge] ignored non-object response: {0}", json);
                return;
            }
            root = parsed.getAsJsonObject();
        } catch (JsonSyntaxException ex) {
            plugin.getLogger().log(Level.WARNING, "[RuleEventBridge] invalid JSON: {0}", ex.getMessage());
            return;
        }

        JsonObject result = root.has("result") && root.get("result").isJsonObject()
                ? root.getAsJsonObject("result")
                : new JsonObject();

        JsonObject worldPatch = firstObject(result, root, "world_patch");
        JsonArray nodes = firstArray(result, root, "nodes");
        JsonArray commands = firstArray(result, root, "commands");
        JsonArray completedTasks = firstArray(result, root, "completed_tasks");
        JsonArray milestones = firstArray(result, root, "milestones");
        boolean exitReady = firstBoolean(result, root, "exit_ready");
        JsonObject summary = firstObject(result, root, "summary");

        Bukkit.getScheduler().runTask(plugin, () -> applyRuleEventResult(
                playerId,
                playerName,
                worldPatch,
                nodes,
                commands,
                completedTasks,
                milestones,
                exitReady,
                summary));
    }

    private void applyRuleEventResult(
            UUID playerId,
            String playerName,
            JsonObject worldPatch,
            JsonArray nodes,
            JsonArray commands,
            JsonArray completedTasks,
            JsonArray milestones,
            boolean exitReady,
            JsonObject summary) {

        Player player = Bukkit.getPlayer(playerId);
        if (player == null || !player.isOnline()) {
            plugin.getLogger().log(Level.FINE,
                    "[RuleEventBridge] player {0} offline, skipping rule response", playerName);
            return;
        }

        if (worldPatch != null && worldPatch.size() > 0) {
            Map<String, Object> patch = gson.fromJson(worldPatch, MAP_TYPE);
            if (patch != null && !patch.isEmpty()) {
                worldPatcher.execute(player, patch);
            }
        }

        if (summary != null && summary.size() > 0) {
            deliverNode(player, summary);
        }

        if (nodes != null) {
            for (JsonElement element : nodes) {
                if (element != null && element.isJsonObject()) {
                    deliverNode(player, element.getAsJsonObject());
                }
            }
        }

        if (completedTasks != null) {
            PlayerRuleState state = getOrCreateState(playerId);
            for (JsonElement element : completedTasks) {
                String taskId = safeString(element);
                if (taskId == null) {
                    continue;
                }
                if (state.completedTasks.add(taskId)) {
                    player.sendMessage(ChatColor.GREEN + "✔ 任务完成：" + ChatColor.WHITE + taskId);
                }
            }
        }

        if (milestones != null) {
            PlayerRuleState state = getOrCreateState(playerId);
            for (JsonElement element : milestones) {
                String milestoneId = safeString(element);
                if (milestoneId == null) {
                    continue;
                }
                if (state.milestones.add(milestoneId)) {
                    player.sendMessage(ChatColor.LIGHT_PURPLE + "★ 阶段完成：" + ChatColor.WHITE + milestoneId);
                }
            }
        }

        if (commands != null) {
            for (JsonElement element : commands) {
                String command = safeString(element);
                if (command == null || command.isBlank()) {
                    continue;
                }
                String resolved = resolveCommand(command, playerName);
                Bukkit.dispatchCommand(Bukkit.getConsoleSender(), resolved);
            }
        }

        if (exitReady) {
            player.sendMessage(ChatColor.GOLD + "★ 当前关卡任务全部完成，可以前往下一阶段或输入 /advance。");
        }
    }

    private void deliverNode(Player player, JsonObject node) {
        if (node == null || node.size() == 0) {
            return;
        }

        String type = safeString(node.get("type"));
        String title = safeString(node.get("title"));
        String text = safeString(node.get("text"));

        title = (title == null) ? "" : title;
        text = (text == null) ? "" : text;

        ChatColor prefixColor = ChatColor.YELLOW;
        String prefix = "【剧情】";

        if (type != null) {
            switch (type) {
                case "task" -> {
                    prefixColor = ChatColor.GOLD;
                    prefix = "【任务】";
                }
                case "task_progress" -> {
                    prefixColor = ChatColor.AQUA;
                    prefix = "【进度】";
                }
                case "task_complete" -> {
                    prefixColor = ChatColor.GREEN;
                    prefix = "【完成】";
                }
                case "task_milestone" -> {
                    prefixColor = ChatColor.LIGHT_PURPLE;
                    prefix = "【阶段】";
                }
                case "npc_dialogue" -> {
                    prefixColor = ChatColor.LIGHT_PURPLE;
                    prefix = "【NPC】";
                }
                case "task_summary" -> {
                    prefixColor = ChatColor.GOLD;
                    prefix = "【总结】";
                }
                default -> {
                    // 默认样式
                }
            }
        }

        String headline = !title.isBlank() ? title : text;
        if (!headline.isBlank()) {
            player.sendMessage(prefixColor + prefix + ChatColor.WHITE + " " + headline);
        }

        if (!text.isBlank() && !text.equals(headline)) {
            for (String line : text.split("\\r?\\n")) {
                if (!line.isBlank()) {
                    player.sendMessage(ChatColor.GRAY + line);
                }
            }
        }
    }

    private PlayerRuleState getOrCreateState(UUID playerId) {
        return playerStates.computeIfAbsent(playerId, id -> new PlayerRuleState());
    }

    private JsonObject firstObject(JsonObject primary, JsonObject secondary, String key) {
        if (primary.has(key) && primary.get(key).isJsonObject()) {
            return primary.getAsJsonObject(key);
        }
        if (secondary.has(key) && secondary.get(key).isJsonObject()) {
            return secondary.getAsJsonObject(key);
        }
        return null;
    }

    private JsonArray firstArray(JsonObject primary, JsonObject secondary, String key) {
        if (primary.has(key) && primary.get(key).isJsonArray()) {
            return primary.getAsJsonArray(key);
        }
        if (secondary.has(key) && secondary.get(key).isJsonArray()) {
            return secondary.getAsJsonArray(key);
        }
        return null;
    }

    private boolean firstBoolean(JsonObject primary, JsonObject secondary, String key) {
        JsonElement element = primary.get(key);
        if (element == null) {
            element = secondary.get(key);
        }
        if (element == null || element.isJsonNull()) {
            return false;
        }
        if (element.isJsonPrimitive()) {
            if (element.getAsJsonPrimitive().isBoolean()) {
                return element.getAsBoolean();
            }
            if (element.getAsJsonPrimitive().isNumber()) {
                return element.getAsInt() != 0;
            }
            if (element.getAsJsonPrimitive().isString()) {
                String value = element.getAsString();
                return value.equalsIgnoreCase("true") || value.equals("1");
            }
        }
        return false;
    }

    private String safeString(JsonElement element) {
        if (element == null || element.isJsonNull()) {
            return null;
        }
        if (element.isJsonPrimitive()) {
            return element.getAsJsonPrimitive().getAsString();
        }
        if (element.isJsonObject() && element.getAsJsonObject().has("id")) {
            return safeString(element.getAsJsonObject().get("id"));
        }
        return element.toString();
    }

    private String resolveCommand(String command, String playerName) {
        if (command == null) {
            return "";
        }
        return command
                .replace("{player}", playerName)
                .replace("%player%", playerName)
                .replace("@player", playerName);
    }

    private static final class PlayerRuleState {
        final Set<String> completedTasks = ConcurrentHashMap.newKeySet();
        final Set<String> milestones = ConcurrentHashMap.newKeySet();
    }

    private Map<String, Object> extractLocation(Location location, Player fallback) {
        Map<String, Object> pos = new LinkedHashMap<>();
        Location source = location;
        if (source == null && fallback != null) {
            source = fallback.getLocation();
        }
        if (source == null) {
            return pos;
        }
        String worldName = "world";
        if (source.getWorld() != null) {
            worldName = source.getWorld().getName();
        } else if (!Bukkit.getWorlds().isEmpty()) {
            worldName = Bukkit.getWorlds().get(0).getName();
        }
        pos.put("world", worldName);
        pos.put("x", source.getX());
        pos.put("y", source.getY());
        pos.put("z", source.getZ());
        return pos;
    }

    private String canonicalize(String prefix, String value) {
        String base = (value == null ? "" : value).toLowerCase();
        String combined = prefix + "_" + base;
        String normalized = combined.replaceAll("[^a-z0-9]+", "_");
        normalized = normalized.replaceAll("_+", "_");
        if (normalized.startsWith("_")) {
            normalized = normalized.substring(1);
        }
        if (normalized.endsWith("_")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        if (normalized.isEmpty()) {
            normalized = prefix;
        }
        return normalized;
    }

    private String normalize(String eventType) {
        if (eventType == null) {
            return "";
        }
        return eventType.trim().toLowerCase();
    }
}
