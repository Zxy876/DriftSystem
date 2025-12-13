package com.driftmc.scene;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
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
import com.driftmc.hud.QuestLogHud;
import com.driftmc.hud.dialogue.ChoicePanel;
import com.driftmc.hud.dialogue.DialoguePanel;
import com.driftmc.session.PlayerSessionManager;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import com.google.gson.JsonSyntaxException;
import com.google.gson.reflect.TypeToken;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
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

    private static final QuestMessageStyle STORY_STYLE = new QuestMessageStyle(ChatColor.YELLOW, "【剧情】", false);
    private static final QuestMessageStyle TASK_STYLE = new QuestMessageStyle(ChatColor.GOLD, "【任务】", true);
    private static final QuestMessageStyle PROGRESS_STYLE = new QuestMessageStyle(ChatColor.AQUA, "【进度】", true);
    private static final QuestMessageStyle COMPLETE_STYLE = new QuestMessageStyle(ChatColor.GREEN, "【完成】", true);
    private static final QuestMessageStyle MILESTONE_STYLE = new QuestMessageStyle(ChatColor.LIGHT_PURPLE, "【阶段】", true);
    private static final QuestMessageStyle SUMMARY_STYLE = new QuestMessageStyle(ChatColor.GOLD, "【总结】", true);
    private static final QuestMessageStyle NPC_STYLE = new QuestMessageStyle(ChatColor.LIGHT_PURPLE, "【NPC】", false);

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final SceneAwareWorldPatchExecutor worldPatcher;
    private final QuestLogHud questLogHud;
    private final DialoguePanel dialoguePanel;
    private final ChoicePanel choicePanel;
    private final PlayerSessionManager sessions;
    private final Gson gson = new Gson();
    private final Map<String, Long> cooldowns = new ConcurrentHashMap<>();
    private final Map<UUID, PlayerRuleState> playerStates = new ConcurrentHashMap<>();
    private long cooldownMillis = DEFAULT_COOLDOWN_MS;

    public RuleEventBridge(JavaPlugin plugin, BackendClient backend, SceneAwareWorldPatchExecutor worldPatcher,
            QuestLogHud questLogHud, DialoguePanel dialoguePanel, ChoicePanel choicePanel,
            PlayerSessionManager sessions) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
        this.backend = Objects.requireNonNull(backend, "backend");
        this.worldPatcher = Objects.requireNonNull(worldPatcher, "worldPatcher");
        this.questLogHud = questLogHud;
        this.dialoguePanel = dialoguePanel;
        this.choicePanel = choicePanel;
        this.sessions = sessions;
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
        Map<String, Object> payloadCopy = payload != null ? new LinkedHashMap<>(payload) : new LinkedHashMap<>();
        QuestEventCanonicalizer.canonicalizePayload(payloadCopy);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("player_id", playerName);
        body.put("event_type", type);
        body.put("payload", payloadCopy);

        if (shouldThrottle(player, type, payloadCopy)) {
            plugin.getLogger().log(Level.FINE,
                    "[RuleEventBridge] Throttled event {0} for player {1}",
                    new Object[]{type, playerName});
            return;
        }

        plugin.getLogger().log(Level.INFO,
                "[RuleEventBridge] Emitting event {0} for player {1} payload={2}",
                new Object[]{type, playerName, payloadCopy});
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
        payload.put("quest_event", QuestEventCanonicalizer.canonicalize(canonicalize("near", npcName)));
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
        payload.put("quest_event", QuestEventCanonicalizer.canonicalize(canonicalize("chat", text)));
        emit(player, "chat", payload);
    }

    public void emitInteractBlock(Player player, String action, Material material, Location location) {
        Map<String, Object> payload = new LinkedHashMap<>();
        String matName = material != null ? material.name().toLowerCase() : "unknown";
        payload.put("action", action != null ? action : "unknown");
        payload.put("block_type", matName);
        payload.put("quest_event", QuestEventCanonicalizer.canonicalize(canonicalize("interact_block", matName)));
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
        payload.put("quest_event", QuestEventCanonicalizer.canonicalize(canonicalize("interact_entity", type)));
        Map<String, Object> pos = extractLocation(entity != null ? entity.getLocation() : null, player);
        if (!pos.isEmpty()) {
            payload.put("location", pos);
        }
        plugin.getLogger().log(Level.INFO,
                "[RuleEventBridge] emitInteractEntity player={0}, entity={1}, interaction={2}",
                new Object[]{player != null ? player.getName() : "unknown", entity != null ? entity.getType() : "null", interaction});
        emit(player, "interact_entity", payload);
    }

    public void emitQuestEvent(Player player, String questEvent) {
        emitQuestEvent(player, questEvent, player != null ? player.getLocation() : null, Collections.emptyMap());
    }

    public void emitQuestEvent(Player player, String questEvent, Location location, Map<String, Object> extraPayload) {
        if (questEvent == null || questEvent.isBlank()) {
            return;
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        String canonical = QuestEventCanonicalizer.canonicalize(questEvent);
        if (!canonical.isEmpty()) {
            payload.put("quest_event", canonical);
        }
        if (location != null) {
            Map<String, Object> loc = extractLocation(location, player);
            if (!loc.isEmpty()) {
                payload.put("location", loc);
            }
        }
        if (extraPayload != null && !extraPayload.isEmpty()) {
            payload.putAll(extraPayload);
        }
        plugin.getLogger().log(Level.INFO,
                "[RuleEventBridge] emitQuestEvent {0} for player {1} payload={2}",
                new Object[]{canonical, player != null ? player.getName() : "unknown", payload});
        emit(player, "quest_event", payload);
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
        JsonObject activeTasks = firstObject(result, root, "active_tasks");

        Bukkit.getScheduler().runTask(plugin, () -> applyRuleEventResult(
                playerId,
                playerName,
                worldPatch,
                nodes,
                commands,
                completedTasks,
                milestones,
                exitReady,
                summary,
                activeTasks));
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
            JsonObject summary,
            JsonObject activeTasks) {

        Player player = Bukkit.getPlayer(playerId);
        if (player == null || !player.isOnline()) {
            plugin.getLogger().log(Level.FINE,
                    "[RuleEventBridge] player {0} offline, skipping rule response", playerName);
            return;
        }

        boolean tutorialMilestoneReached = containsTutorialComplete(milestones);
        boolean exitReadyDuringTutorial = sessions != null && sessions.isTutorial(player) && exitReady;
        if (sessions != null && (tutorialMilestoneReached || exitReadyDuringTutorial)) {
            boolean alreadyCompleted = sessions.hasCompletedTutorial(player);
            sessions.markTutorialComplete(player);
            if (!alreadyCompleted) {
                player.sendMessage(ChatColor.GOLD + "★ 教程完成，已进入正式剧情。\n" + ChatColor.WHITE + "欢迎探索主线章节。");
                player.sendActionBar(Component.text("教程完成，已进入正式剧情", NamedTextColor.GOLD));
            }
        }

        if (questLogHud != null && activeTasks != null && activeTasks.size() > 0) {
            questLogHud.handleSnapshot(player, activeTasks, QuestLogHud.Trigger.RULE_EVENT);
        }

        if (worldPatch != null && worldPatch.size() > 0) {
            Map<String, Object> patch = gson.fromJson(worldPatch, MAP_TYPE);
            if (patch != null && !patch.isEmpty()) {
                worldPatcher.execute(player, patch);
            }
        }

        if (summary != null && summary.size() > 0) {
            deliverNode(player, summary);
            if (questLogHud != null) {
                questLogHud.handleQuestNode(player, summary);
            }
        }

        if (nodes != null) {
            for (JsonElement element : nodes) {
                if (element != null && element.isJsonObject()) {
                    JsonObject node = element.getAsJsonObject();
                    deliverNode(player, node);
                    if (questLogHud != null) {
                        questLogHud.handleQuestNode(player, node);
                    }
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

    private boolean containsTutorialComplete(JsonArray milestones) {
        if (milestones == null) {
            return false;
        }
        for (JsonElement element : milestones) {
            String value = safeString(element);
            if (value != null && value.equalsIgnoreCase("tutorial_complete")) {
                return true;
            }
        }
        return false;
    }

    private void deliverNode(Player player, JsonObject node) {
        if (node == null || node.size() == 0) {
            return;
        }

        String type = safeString(node.get("type"));

        if ("npc_dialogue".equalsIgnoreCase(type) && dialoguePanel != null) {
            dialoguePanel.showDialogue(player, node);
            return;
        }

        if ("story_choice".equalsIgnoreCase(type) && choicePanel != null) {
            choicePanel.presentChoiceNode(player, node);
            return;
        }

        QuestMessageStyle style = resolveStyle(type);

        String title = safeString(node.get("title"));
        String text = safeString(node.get("text"));
        String hint = safeString(node.get("hint"));
        int remaining = safeInt(node.get("remaining"), -1);
        int progress = safeInt(node.get("progress"), -1);
        int count = safeInt(node.get("count"), -1);

        if (style.quest) {
            String headline = !isBlank(title) ? title : (!isBlank(text) ? text : "任务更新");
            player.sendMessage(style.color + style.prefix + ChatColor.WHITE + " " + headline);

            List<String> details = new ArrayList<>();
            appendDetail(details, hint);

            if (remaining >= 0) {
                StringBuilder progressLine = new StringBuilder("剩余 ").append(remaining).append(" 项");
                if (progress >= 0 && count > 0) {
                    progressLine.append(" (")
                            .append(Math.min(progress, count))
                            .append("/")
                            .append(count)
                            .append(")");
                }
                appendDetail(details, progressLine.toString());
            }

            if (!isBlank(text) && !text.equals(headline)) {
                for (String fragment : text.split("\\r?\\n")) {
                    appendDetail(details, fragment);
                }
            }

            if (!details.isEmpty()) {
                sendDetailLines(player, details);
            }
            return;
        }

        String headline = !isBlank(title) ? title : text;
        if (!isBlank(headline)) {
            player.sendMessage(style.color + style.prefix + ChatColor.WHITE + " " + headline);
        }

        List<String> details = new ArrayList<>();
        appendDetail(details, hint);

        if (!isBlank(text) && !text.equals(headline)) {
            for (String fragment : text.split("\\r?\\n")) {
                appendDetail(details, fragment);
            }
        }

        if (!details.isEmpty()) {
            sendDetailLines(player, details);
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

    private QuestMessageStyle resolveStyle(String type) {
        if (type == null) {
            return STORY_STYLE;
        }
        switch (type) {
            case "task":
                return TASK_STYLE;
            case "task_progress":
                return PROGRESS_STYLE;
            case "task_complete":
                return COMPLETE_STYLE;
            case "task_milestone":
                return MILESTONE_STYLE;
            case "task_summary":
                return SUMMARY_STYLE;
            case "npc_dialogue":
                return NPC_STYLE;
            default:
                return STORY_STYLE;
        }
    }

    private int safeInt(JsonElement element, int defaultValue) {
        if (element == null || element.isJsonNull()) {
            return defaultValue;
        }
        if (element.isJsonPrimitive()) {
            JsonPrimitive primitive = element.getAsJsonPrimitive();
            if (primitive.isNumber()) {
                return primitive.getAsInt();
            }
            if (primitive.isString()) {
                try {
                    return Integer.parseInt(primitive.getAsString());
                } catch (NumberFormatException ignored) {
                    return defaultValue;
                }
            }
        }
        return defaultValue;
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private void appendDetail(List<String> details, String value) {
        if (value == null) {
            return;
        }
        String trimmed = value.trim();
        if (trimmed.isEmpty()) {
            return;
        }
        if (!details.contains(trimmed)) {
            details.add(trimmed);
        }
    }

    private void sendDetailLines(Player player, List<String> lines) {
        for (String detail : lines) {
            player.sendMessage(ChatColor.GRAY + "› " + ChatColor.WHITE + detail);
        }
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

    private static final class QuestMessageStyle {
        final ChatColor color;
        final String prefix;
        final boolean quest;

        QuestMessageStyle(ChatColor color, String prefix, boolean quest) {
            this.color = color;
            this.prefix = prefix;
            this.quest = quest;
        }
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
