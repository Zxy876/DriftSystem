package com.driftmc.commands;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

/**
 * /taskdebug, /debugscene, /debuginventory, /debugpatch
 * surface backend debug snapshots for admins.
 */
public class TaskDebugCommand implements CommandExecutor {

    public enum ViewMode {
        TASKS,
        SCENE,
        INVENTORY,
        PATCH,
        WORLDSTATE,
        LEVELDEBUG,
        EVENTDEBUG
    }

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final String debugToken;
    private final ViewMode viewMode;

    public TaskDebugCommand(JavaPlugin plugin, BackendClient backend, String debugToken) {
        this(plugin, backend, debugToken, ViewMode.TASKS);
    }

    public TaskDebugCommand(JavaPlugin plugin, BackendClient backend, String debugToken, ViewMode viewMode) {
        this.plugin = plugin;
        this.backend = backend;
        this.debugToken = debugToken != null ? debugToken : "";
        this.viewMode = viewMode != null ? viewMode : ViewMode.TASKS;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (sender == null) {
            return true;
        }
        String safeLabel = label != null && !label.isBlank() ? label : "taskdebug";
        if (!(sender instanceof Player player)) {
            sender.sendMessage("只有玩家可以执行 /" + safeLabel + "。记录型调试请使用后端工具。");
            return true;
        }

        if (!player.hasPermission("drift.taskdebug") && !player.isOp()) {
            player.sendMessage(Component.text("你没有权限查看任务调试信息。", NamedTextColor.RED));
            return true;
        }

        fetchDebugSnapshot(player);
        return true;
    }

    private void fetchDebugSnapshot(Player player) {
        final UUID playerId = player.getUniqueId();
        final String playerName = player.getName();
        final String path = "/world/story/" + urlSegment(playerName) + "/debug/tasks";

        Map<String, String> headers = Collections.emptyMap();
        if (!debugToken.isBlank()) {
            headers = new HashMap<>();
            headers.put("X-Debug-Token", debugToken);
        }

        backend.getAsync(path, headers, new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().log(Level.WARNING,
                        "[TaskDebug] backend fetch failed for {0}: {1}",
                        new Object[] { playerName, e.getMessage() });
                Bukkit.getScheduler().runTask(plugin, () -> {
                    Player target = Bukkit.getPlayer(playerId);
                    if (target != null && target.isOnline()) {
                        target.sendMessage(Component.text("任务调试接口暂时不可用。", NamedTextColor.RED));
                    }
                });
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                boolean success = response.isSuccessful();
                String payload;
                try (Response res = response) {
                    okhttp3.ResponseBody body = res.body();
                    payload = body != null ? body.string() : "{}";
                }

                JsonObject root = null;
                if (success) {
                    try {
                        JsonElement parsed = JsonParser.parseString(payload);
                        if (parsed.isJsonObject()) {
                            root = parsed.getAsJsonObject();
                        }
                    } catch (IllegalStateException ex) {
                        plugin.getLogger().log(Level.WARNING, "[TaskDebug] failed to parse payload", ex);
                    }
                }

                final JsonObject snapshot = root;
                final boolean isSuccess = success;

                Bukkit.getScheduler().runTask(plugin, () -> {
                    Player target = Bukkit.getPlayer(playerId);
                    if (target == null || !target.isOnline()) {
                        return;
                    }

                    if (!isSuccess || snapshot == null) {
                        target.sendMessage(Component.text("未能获取调试信息。", NamedTextColor.RED));
                        return;
                    }

                    renderSnapshotByMode(target, snapshot);
                });
            }
        });
    }

    private void renderSnapshotByMode(Player player, JsonObject root) {
        switch (viewMode) {
            case SCENE -> renderSceneSnapshot(player, root);
            case INVENTORY -> renderInventorySnapshot(player, root);
            case PATCH -> renderPatchSnapshot(player, root);
            case WORLDSTATE -> renderWorldStateSnapshot(player, root);
            case LEVELDEBUG -> renderLevelDebugSnapshot(player, root);
            case EVENTDEBUG -> renderEventDebugSnapshot(player, root);
            case TASKS -> renderDebugSnapshot(player, root);
        }
    }

    private void renderEventDebugSnapshot(Player player, JsonObject root) {
        JsonArray recent = getArray(root, "recent_rule_events");
        JsonObject lastEvent = getObject(root, "last_rule_event");

        player.sendMessage(Component.text("====== Event Debug ======", NamedTextColor.AQUA));

        if (recent == null || recent.size() == 0) {
            player.sendMessage(Component.text("recent_rule_events: 无", NamedTextColor.GRAY));
            if (lastEvent != null) {
                boolean matched = getBoolean(lastEvent, "matched", false);
                JsonObject event = getObject(lastEvent, "event");
                player.sendMessage(Component.text(
                        "last_event: " + extractEventLabel(event) + (matched ? " ✓" : " ✘"),
                        matched ? NamedTextColor.GREEN : NamedTextColor.RED));
            }
            renderSceneScoringDebug(player, root);
            return;
        }

        player.sendMessage(Component.text("recent_rule_events: " + recent.size(), NamedTextColor.YELLOW));
        int limit = Math.min(8, recent.size());
        for (int idx = Math.max(0, recent.size() - limit); idx < recent.size(); idx++) {
            JsonElement element = recent.get(idx);
            if (element == null || !element.isJsonObject()) {
                continue;
            }

            JsonObject row = element.getAsJsonObject();
            JsonObject raw = getObject(row, "raw_payload");
            JsonObject event = getObject(row, "event");
            JsonObject payload = raw != null ? getObject(raw, "payload") : null;

            String eventType = raw != null ? getString(raw, "event_type") : null;
            if (eventType == null || eventType.isBlank()) {
                eventType = event != null ? getString(event, "event_type") : null;
            }
            eventType = defaultString(eventType, "unknown");

            String trigger = payload != null ? getString(payload, "trigger") : null;
            String questEvent = payload != null ? getString(payload, "quest_event") : null;
            if (questEvent == null || questEvent.isBlank()) {
                questEvent = event != null ? getString(event, "quest_event") : null;
            }
            String npc = payload != null ? getString(payload, "npc_id") : null;
            if (npc == null || npc.isBlank()) {
                npc = payload != null ? getString(payload, "npc") : null;
            }
            if (npc == null || npc.isBlank()) {
                npc = payload != null ? getString(payload, "target") : null;
            }

            String item = payload != null ? getString(payload, "resource") : null;
            if (item == null || item.isBlank()) {
                item = payload != null ? getString(payload, "item_type") : null;
            }
            if (item == null || item.isBlank()) {
                item = payload != null ? getString(payload, "item") : null;
            }

            boolean matched = getBoolean(row, "matched", false);
            JsonArray matchedTasks = getArray(row, "matched_tasks");
            int matchedCount = matchedTasks != null ? matchedTasks.size() : 0;

            StringBuilder line = new StringBuilder();
            line.append("- ").append(eventType);
            if (trigger != null && !trigger.isBlank()) {
                line.append(" | trigger=").append(trigger);
            }
            if (questEvent != null && !questEvent.isBlank()) {
                line.append(" | quest=").append(questEvent);
            }
            if (npc != null && !npc.isBlank()) {
                line.append(" | npc=").append(npc);
            }
            if (item != null && !item.isBlank()) {
                line.append(" | item=").append(item);
            }
            line.append(" | matched=").append(matched);
            if (matchedCount > 0) {
                line.append("(").append(matchedCount).append(")");
            }

            player.sendMessage(Component.text(line.toString(), matched ? NamedTextColor.GREEN : NamedTextColor.WHITE));
        }

        if (lastEvent != null) {
            boolean matched = getBoolean(lastEvent, "matched", false);
            JsonObject event = getObject(lastEvent, "event");
            player.sendMessage(Component.text(
                    "last_event: " + extractEventLabel(event) + (matched ? " ✓" : " ✘"),
                    matched ? NamedTextColor.GREEN : NamedTextColor.LIGHT_PURPLE));
        }

        renderSceneScoringDebug(player, root);
    }

    private void renderSceneScoringDebug(Player player, JsonObject root) {
        JsonObject scene = getObject(root, "scene_generation");
        if (scene == null) {
            return;
        }

        String selectedRoot = getString(scene, "selected_root");
        JsonArray candidateScores = getArray(scene, "candidate_scores");
        JsonArray selectedChildren = getArray(scene, "selected_children");
        JsonArray blocked = getArray(scene, "blocked");
        JsonObject reasons = getObject(scene, "reasons");

        boolean hasScoring = (selectedRoot != null && !selectedRoot.isBlank())
                || (candidateScores != null && candidateScores.size() > 0)
                || (selectedChildren != null && selectedChildren.size() > 0)
                || (blocked != null && blocked.size() > 0)
                || (reasons != null && !reasons.entrySet().isEmpty());
        if (!hasScoring) {
            return;
        }

        String selectedReason = reasons != null ? getString(reasons, "selected_root") : null;

        player.sendMessage(Component.text("scene_scoring:", NamedTextColor.AQUA));
        if (selectedRoot != null && !selectedRoot.isBlank()) {
            StringBuilder selectedLine = new StringBuilder("selected_root: ").append(selectedRoot);
            if (selectedReason != null && !selectedReason.isBlank()) {
                selectedLine.append(" | reason=").append(selectedReason);
            }
            player.sendMessage(Component.text(selectedLine.toString(), NamedTextColor.GOLD));
        } else {
            player.sendMessage(Component.text("selected_root: 无", NamedTextColor.GRAY));
        }

        if (candidateScores != null && candidateScores.size() > 0) {
            player.sendMessage(Component.text("candidate_scores:", NamedTextColor.YELLOW));
            int limit = Math.min(6, candidateScores.size());
            for (int idx = 0; idx < limit; idx++) {
                JsonElement element = candidateScores.get(idx);
                if (element == null || !element.isJsonObject()) {
                    continue;
                }
                JsonObject candidate = element.getAsJsonObject();
                String fragment = defaultString(getString(candidate, "fragment"), "unknown");
                String scoreText = formatDecimal(getDouble(candidate, "score", 0.0));
                String reason = getString(candidate, "reason");

                StringBuilder line = new StringBuilder("- ")
                        .append(fragment)
                        .append(": ")
                        .append(scoreText);
                if (reason != null && !reason.isBlank()) {
                    line.append(" | ").append(reason);
                }

                player.sendMessage(Component.text(line.toString(), NamedTextColor.WHITE));
            }
            if (candidateScores.size() > limit) {
                player.sendMessage(Component.text("… 其余 " + (candidateScores.size() - limit) + " 条候选已省略", NamedTextColor.GRAY));
            }
        }

        if (selectedChildren != null && selectedChildren.size() > 0) {
            player.sendMessage(Component.text("selected_children: " + joinStringArray(selectedChildren), NamedTextColor.WHITE));
        }

        if (blocked != null && blocked.size() > 0) {
            player.sendMessage(Component.text("blocked:", NamedTextColor.RED));
            int limit = Math.min(6, blocked.size());
            for (int idx = 0; idx < limit; idx++) {
                JsonElement element = blocked.get(idx);
                if (element == null || !element.isJsonObject()) {
                    continue;
                }
                JsonObject row = element.getAsJsonObject();
                String fragment = defaultString(getString(row, "fragment"), "unknown");
                String stage = defaultString(getString(row, "stage"), "unknown");
                String reason = defaultString(getString(row, "reason"), "blocked");
                player.sendMessage(Component.text("- " + fragment + " | stage=" + stage + " | " + reason, NamedTextColor.GRAY));
            }
            if (blocked.size() > limit) {
                player.sendMessage(Component.text("… 其余 " + (blocked.size() - limit) + " 条阻塞已省略", NamedTextColor.GRAY));
            }
        }

        renderSceneCompositionDebug(player, scene);
    }

    private void renderSceneCompositionDebug(Player player, JsonObject scene) {
        JsonObject sceneGraph = getObject(scene, "scene_graph");
        JsonObject layout = getObject(scene, "layout");

        boolean hasGraph = sceneGraph != null && !sceneGraph.entrySet().isEmpty();
        boolean hasLayout = layout != null && !layout.entrySet().isEmpty();
        if (!hasGraph && !hasLayout) {
            return;
        }

        if (hasGraph) {
            String root = defaultString(getString(sceneGraph, "root"), "none");
            JsonArray nodes = getArray(sceneGraph, "nodes");
            JsonArray edges = getArray(sceneGraph, "edges");

            player.sendMessage(Component.text("scene_graph:", NamedTextColor.AQUA));
            player.sendMessage(Component.text("root: " + root, NamedTextColor.GOLD));

            if (nodes != null && nodes.size() > 0) {
                player.sendMessage(Component.text("nodes: " + joinStringArray(nodes), NamedTextColor.WHITE));
            }

            if (edges != null && edges.size() > 0) {
                player.sendMessage(Component.text("edges:", NamedTextColor.YELLOW));
                int edgeLimit = Math.min(8, edges.size());
                for (int idx = 0; idx < edgeLimit; idx++) {
                    JsonElement edgeElement = edges.get(idx);
                    if (edgeElement == null || !edgeElement.isJsonObject()) {
                        continue;
                    }
                    JsonObject edge = edgeElement.getAsJsonObject();
                    String from = defaultString(getString(edge, "from"), "?");
                    String to = defaultString(getString(edge, "to"), "?");
                    player.sendMessage(Component.text("- " + from + " -> " + to, NamedTextColor.WHITE));
                }
                if (edges.size() > edgeLimit) {
                    player.sendMessage(Component.text("… 其余 " + (edges.size() - edgeLimit) + " 条边已省略", NamedTextColor.GRAY));
                }
            }
        }

        if (hasLayout) {
            String strategy = defaultString(getString(layout, "strategy"), "radial_v1");
            JsonObject positions = getObject(layout, "positions");

            player.sendMessage(Component.text("layout: strategy=" + strategy, NamedTextColor.AQUA));
            if (positions == null || positions.entrySet().isEmpty()) {
                player.sendMessage(Component.text("positions: 无", NamedTextColor.GRAY));
                return;
            }

            player.sendMessage(Component.text("positions:", NamedTextColor.YELLOW));
            int shown = 0;
            for (Map.Entry<String, JsonElement> entry : positions.entrySet()) {
                if (shown >= 8) {
                    player.sendMessage(Component.text("… 其余布局节点已省略", NamedTextColor.GRAY));
                    break;
                }

                JsonElement value = entry.getValue();
                if (value == null || !value.isJsonObject()) {
                    continue;
                }

                JsonObject pos = value.getAsJsonObject();
                String x = formatDecimal(getDouble(pos, "x", 0.0));
                String z = formatDecimal(getDouble(pos, "z", 0.0));
                player.sendMessage(Component.text("- " + entry.getKey() + " (" + x + ", " + z + ")", NamedTextColor.WHITE));
                shown++;
            }
        }
    }

    private void renderLevelDebugSnapshot(Player player, JsonObject root) {
        JsonObject levelState = getObject(root, "level_state");
        JsonObject levelEvolution = getObject(root, "level_evolution");

        if (levelState == null && levelEvolution == null) {
            player.sendMessage(Component.text("暂无关卡状态机调试信息。", NamedTextColor.YELLOW));
            return;
        }

        String currentStage = levelState != null ? getString(levelState, "current_stage") : null;
        int stageIndex = getInt(levelState, "stage_index", -1);
        JsonArray stagePath = getArray(levelState, "stage_path");
        JsonArray history = getArray(levelState, "history");

        String nextStage = levelEvolution != null ? getString(levelEvolution, "next_stage") : null;
        boolean transitionReady = getBoolean(levelEvolution, "transition_ready", false);
        JsonArray blockedBy = getArray(levelEvolution, "blocked_by");
        JsonObject signals = getObject(levelEvolution, "signals");

        player.sendMessage(Component.text("====== Level Debug ======", NamedTextColor.AQUA));
        player.sendMessage(Component.text("stage: " + defaultString(currentStage, "unknown"), NamedTextColor.GOLD));
        if (stageIndex >= 0) {
            player.sendMessage(Component.text("stage_index: " + stageIndex, NamedTextColor.WHITE));
        }
        player.sendMessage(Component.text("next_stage: " + defaultString(nextStage, "none"), NamedTextColor.YELLOW));
        player.sendMessage(Component.text("transition_ready: " + transitionReady, NamedTextColor.WHITE));

        player.sendMessage(Component.text("stage_path: " + (stagePath != null ? joinStagePath(stagePath) : "无"), NamedTextColor.LIGHT_PURPLE));

        if (blockedBy != null && blockedBy.size() > 0) {
            player.sendMessage(Component.text("blocked_by: " + joinStringArray(blockedBy), NamedTextColor.RED));
        } else {
            player.sendMessage(Component.text("blocked_by: 无", NamedTextColor.GRAY));
        }

        player.sendMessage(Component.text("signals:", NamedTextColor.YELLOW));
        if (signals != null && !signals.entrySet().isEmpty()) {
            for (Map.Entry<String, JsonElement> entry : signals.entrySet()) {
                JsonElement value = entry.getValue();
                if (value != null && value.isJsonObject()) {
                    player.sendMessage(Component.text("- " + entry.getKey() + ": ...", NamedTextColor.WHITE));
                } else {
                    player.sendMessage(Component.text("- " + entry.getKey() + ": " + valueAsText(value), NamedTextColor.WHITE));
                }
            }
        } else {
            player.sendMessage(Component.text("- 无", NamedTextColor.GRAY));
        }

        player.sendMessage(Component.text("stage_history:", NamedTextColor.YELLOW));
        if (history != null && history.size() > 0) {
            int limit = Math.min(5, history.size());
            for (int idx = Math.max(0, history.size() - limit); idx < history.size(); idx++) {
                JsonElement element = history.get(idx);
                if (element == null || !element.isJsonObject()) {
                    continue;
                }
                JsonObject row = element.getAsJsonObject();
                String from = defaultString(getString(row, "from"), "?");
                String to = defaultString(getString(row, "to"), "?");
                String reason = defaultString(getString(row, "reason"), "unknown");
                player.sendMessage(Component.text("- " + from + " -> " + to + " | reason=" + reason, NamedTextColor.WHITE));
            }
        } else {
            player.sendMessage(Component.text("- 无", NamedTextColor.GRAY));
        }
    }

    private String joinStagePath(JsonArray array) {
        StringBuilder builder = new StringBuilder();
        for (JsonElement element : array) {
            if (element == null || !element.isJsonPrimitive()) {
                continue;
            }
            String value = element.getAsString();
            if (value == null || value.isBlank()) {
                continue;
            }
            if (builder.length() > 0) {
                builder.append(" -> ");
            }
            builder.append(value);
        }
        return builder.length() > 0 ? builder.toString() : "无";
    }

    private String valueAsText(JsonElement value) {
        if (value == null || value.isJsonNull()) {
            return "null";
        }
        if (value.isJsonPrimitive()) {
            return value.getAsString();
        }
        return value.toString();
    }

    private void renderWorldStateSnapshot(Player player, JsonObject root) {
        JsonObject levelState = getObject(root, "level_state");
        JsonObject levelEvolution = getObject(root, "level_evolution");
        JsonObject scene = getObject(root, "scene_generation");
        JsonObject resources = scene != null ? getObject(scene, "inventory_resources") : null;
        if (resources == null) {
            resources = getObject(root, "inventory_resources");
        }

        String currentStage = levelState != null ? getString(levelState, "current_stage") : null;
        String nextStage = levelEvolution != null ? getString(levelEvolution, "next_stage") : null;
        boolean transitionReady = getBoolean(levelEvolution, "transition_ready", false);

        player.sendMessage(Component.text("====== World State ======", NamedTextColor.AQUA));
        player.sendMessage(Component.text("current_stage: " + defaultString(currentStage, "unknown"), NamedTextColor.GOLD));
        player.sendMessage(Component.text("next_stage: " + defaultString(nextStage, "none"), NamedTextColor.YELLOW));
        player.sendMessage(Component.text("transition_ready: " + transitionReady, NamedTextColor.WHITE));

        player.sendMessage(Component.text("resources:", NamedTextColor.LIGHT_PURPLE));
        if (resources != null && !resources.entrySet().isEmpty()) {
            for (Map.Entry<String, JsonElement> entry : resources.entrySet()) {
                int amount = getInt(entry.getValue(), 0);
                player.sendMessage(Component.text("- " + entry.getKey() + ": " + amount, NamedTextColor.WHITE));
            }
        } else {
            player.sendMessage(Component.text("- 无", NamedTextColor.GRAY));
        }
    }

    private void renderDebugSnapshot(Player player, JsonObject root) {
        String status = getString(root, "status");
        if (status != null && !"ok".equalsIgnoreCase(status)) {
            String msg = getString(root, "msg");
            if (msg != null && !msg.isBlank()) {
                player.sendMessage(Component.text("任务状态: " + msg, NamedTextColor.RED));
            }
        }

        JsonObject active = getObject(root, "active_tasks");
        String currentTask = extractCurrentTask(active);
        String pendingSummary = extractPendingSummary(root);
        JsonObject lastEvent = getObject(root, "last_rule_event");

        String eventLabel = "无";
        boolean matched = false;
        if (lastEvent != null) {
            JsonObject event = getObject(lastEvent, "event");
            eventLabel = extractEventLabel(event);
            matched = getBoolean(lastEvent, "matched", false);
        }

        NamedTextColor barColor = matched ? NamedTextColor.GREEN : NamedTextColor.RED;
        StringBuilder overlay = new StringBuilder("任务调试: ");
        overlay.append(currentTask != null ? currentTask : "无活跃任务");
        overlay.append(" | 待: ").append(pendingSummary);
        overlay.append(" | 事件: ").append(eventLabel);
        overlay.append(matched ? " ✓" : " ✘");

        player.sendActionBar(Component.text(overlay.toString(), barColor));

        player.sendMessage(Component.text("======= 任务调试快照 =======", NamedTextColor.AQUA));
        if (currentTask != null) {
            player.sendMessage(Component.text("活跃任务: " + currentTask, NamedTextColor.GOLD));
        }

        JsonArray pending = getArray(root, "pending_conditions");
        if (pending != null && pending.size() > 0) {
            player.sendMessage(Component.text("待处理阶段:", NamedTextColor.YELLOW));
            for (JsonElement element : pending) {
                if (!element.isJsonObject()) {
                    continue;
                }
                JsonObject obj = element.getAsJsonObject();
                String taskTitle = getString(obj, "task_title");
                String milestoneTitle = getString(obj, "milestone_title");
                int remaining = getInt(obj, "remaining", -1);
                String expected = getString(obj, "expected_event");
                StringBuilder line = new StringBuilder();
                if (taskTitle != null && !taskTitle.isBlank()) {
                    line.append(taskTitle);
                }
                if (milestoneTitle != null && !milestoneTitle.isBlank()) {
                    if (line.length() > 0) {
                        line.append(" · ");
                    }
                    line.append(milestoneTitle);
                }
                if (remaining > 0) {
                    line.append(" (剩余").append(remaining).append(")");
                }
                if (expected != null && !expected.isBlank()) {
                    line.append(" → 事件: ").append(expected);
                }
                player.sendMessage(Component.text("- " + line, NamedTextColor.WHITE));
            }
        } else {
            player.sendMessage(Component.text("无待处理阶段。", NamedTextColor.GRAY));
        }

        if (lastEvent != null) {
            player.sendMessage(Component.text("最后事件: " + eventLabel, NamedTextColor.LIGHT_PURPLE));
            JsonArray matchedTasks = getArray(lastEvent, "matched_tasks");
            if (matchedTasks != null && matchedTasks.size() > 0) {
                player.sendMessage(Component.text("匹配任务:", NamedTextColor.GREEN));
                for (JsonElement element : matchedTasks) {
                    if (!element.isJsonObject()) {
                        continue;
                    }
                    JsonObject obj = element.getAsJsonObject();
                    String taskTitle = getString(obj, "task_title");
                    String milestoneId = getString(obj, "milestone_id");
                    StringBuilder line = new StringBuilder();
                    if (taskTitle != null && !taskTitle.isBlank()) {
                        line.append(taskTitle);
                    }
                    if (milestoneId != null && !milestoneId.isBlank()) {
                        if (line.length() > 0) {
                            line.append(" → ");
                        }
                        line.append(milestoneId);
                    }
                    player.sendMessage(Component.text("• " + line, NamedTextColor.WHITE));
                }
            } else {
                player.sendMessage(Component.text("未匹配任何任务。", NamedTextColor.RED));
            }
        }
    }

    private void renderSceneSnapshot(Player player, JsonObject root) {
        JsonObject scene = getObject(root, "scene_generation");
        if (scene == null) {
            player.sendMessage(Component.text("暂无 scene_generation（请先执行“创建剧情 …”）。", NamedTextColor.YELLOW));
            return;
        }

        String sceneTheme = defaultString(getString(scene, "scene_theme"), "无");
        String sceneHint = defaultString(getString(scene, "scene_hint"), "无");
        String anchor = defaultString(getString(scene, "selected_anchor"), "未指定");
        String initialAnchor = defaultString(getString(scene, "initial_anchor"), anchor);
        String finalAnchor = defaultString(getString(scene, "final_anchor"), anchor);
        int eventCount = getInt(scene, "event_count", 0);
        JsonObject playerPos = getObject(scene, "player_pos");
        JsonObject initialAnchorPos = getObject(scene, "initial_anchor_pos");
        JsonObject finalAnchorPos = getObject(scene, "final_anchor_pos");
        JsonObject anchorPos = getObject(scene, "anchor_pos");
        if (initialAnchorPos == null) {
            initialAnchorPos = anchorPos;
        }
        if (finalAnchorPos == null) {
            finalAnchorPos = anchorPos;
        }

        player.sendMessage(Component.text("======= Scene Debug =======", NamedTextColor.AQUA));
        player.sendMessage(Component.text("theme: " + sceneTheme, NamedTextColor.GOLD));
        player.sendMessage(Component.text("hint: " + sceneHint + " | anchor: " + anchor, NamedTextColor.YELLOW));
        player.sendMessage(Component.text("initial_anchor: " + initialAnchor + " | final_anchor: " + finalAnchor, NamedTextColor.YELLOW));
        player.sendMessage(Component.text("player_pos: " + formatPosition(playerPos), NamedTextColor.WHITE));
        player.sendMessage(Component.text("initial_anchor_pos: " + formatPosition(initialAnchorPos), NamedTextColor.WHITE));
        player.sendMessage(Component.text("final_anchor_pos: " + formatPosition(finalAnchorPos), NamedTextColor.WHITE));
        player.sendMessage(Component.text("anchor_pos: " + formatPosition(anchorPos), NamedTextColor.WHITE));

        JsonArray fragments = getArray(scene, "fragments");
        if (fragments != null && fragments.size() > 0) {
            player.sendMessage(Component.text("fragments: " + joinStringArray(fragments), NamedTextColor.WHITE));
        } else {
            player.sendMessage(Component.text("fragments: 无", NamedTextColor.GRAY));
        }

        JsonArray eventPlan = getArray(scene, "event_plan");
        if (eventPlan != null && eventPlan.size() > 0) {
            int limit = Math.min(eventPlan.size(), 8);
            player.sendMessage(Component.text("event_plan(" + eventPlan.size() + "):", NamedTextColor.LIGHT_PURPLE));
            for (int idx = 0; idx < limit; idx++) {
                JsonElement element = eventPlan.get(idx);
                if (!element.isJsonObject()) {
                    continue;
                }
                JsonObject event = element.getAsJsonObject();
                String eventId = defaultString(getString(event, "event_id"), "unknown_event");
                String eventType = defaultString(getString(event, "type"), "unknown_type");

                JsonObject data = getObject(event, "data");
                String variant = data != null ? getString(data, "scene_variant") : null;
                String hint = data != null ? getString(data, "scene_hint") : null;

                StringBuilder line = new StringBuilder();
                line.append(idx + 1).append(". ").append(eventId).append(" | ").append(eventType);
                if (hint != null && !hint.isBlank()) {
                    line.append(" | hint=").append(hint);
                }
                if (variant != null && !variant.isBlank()) {
                    line.append(" | variant=").append(variant);
                }

                player.sendMessage(Component.text(line.toString(), NamedTextColor.WHITE));
            }
            if (eventPlan.size() > limit) {
                player.sendMessage(Component.text("… 其余 " + (eventPlan.size() - limit) + " 条已省略", NamedTextColor.GRAY));
            }
        } else {
            player.sendMessage(Component.text("event_plan: 无（仅有 event_count=" + eventCount + "）", NamedTextColor.GRAY));
        }
    }

    private void renderInventorySnapshot(Player player, JsonObject root) {
        JsonObject scene = getObject(root, "scene_generation");
        if (scene == null) {
            player.sendMessage(Component.text("暂无库存调试数据（scene_generation 缺失）。", NamedTextColor.YELLOW));
            return;
        }

        JsonObject resources = getObject(scene, "inventory_resources");
        JsonArray fragments = getArray(scene, "fragments");

        player.sendMessage(Component.text("===== Inventory Debug =====", NamedTextColor.AQUA));
        player.sendMessage(Component.text("来源: recent rule events 聚合库存", NamedTextColor.GRAY));

        if (resources != null && !resources.entrySet().isEmpty()) {
            int total = 0;
            for (Map.Entry<String, JsonElement> entry : resources.entrySet()) {
                int amount = getInt(entry.getValue(), 0);
                total += amount;
                player.sendMessage(Component.text("- " + entry.getKey() + " x" + amount, NamedTextColor.WHITE));
            }
            player.sendMessage(Component.text("总计: " + total, NamedTextColor.GREEN));
        } else {
            player.sendMessage(Component.text("inventory_resources: 无", NamedTextColor.GRAY));
        }

        if (fragments != null && fragments.size() > 0) {
            player.sendMessage(Component.text("命中片段: " + joinStringArray(fragments), NamedTextColor.YELLOW));
        }
    }

    private void renderPatchSnapshot(Player player, JsonObject root) {
        JsonObject report = getObject(root, "last_apply_report");

        player.sendMessage(Component.text("======= Patch Debug =======", NamedTextColor.AQUA));
        if (report == null) {
            player.sendMessage(Component.text("暂无 last_apply_report（还未执行 payload 或无回传）。", NamedTextColor.YELLOW));
        } else {
            player.sendMessage(Component.text("build_id: " + defaultString(getString(report, "build_id"), "unknown"), NamedTextColor.GOLD));
            player.sendMessage(Component.text("status: " + defaultString(getString(report, "last_status"), "unknown"), NamedTextColor.WHITE));
            player.sendMessage(Component.text("failure: " + defaultString(getString(report, "last_failure_code"), "NONE"), NamedTextColor.WHITE));
            player.sendMessage(Component.text(
                    "executed/failed: "
                            + defaultString(getString(report, "last_executed"), "0")
                            + "/"
                            + defaultString(getString(report, "last_failed"), "0"),
                    NamedTextColor.WHITE));
            player.sendMessage(Component.text("duration_ms: " + defaultString(getString(report, "last_duration_ms"), "0"), NamedTextColor.WHITE));
        }

        String fallbackFlag = defaultString(getString(root, "last_fallback_flag"), "false");
        String fallbackReason = defaultString(getString(root, "last_fallback_reason"), "none");
        String fallbackLevel = defaultString(getString(root, "last_fallback_level_id"), "none");
        player.sendMessage(Component.text(
                "fallback: " + fallbackFlag + " | reason: " + fallbackReason + " | level: " + fallbackLevel,
                NamedTextColor.LIGHT_PURPLE));

        JsonArray recentReports = getArray(root, "recent_apply_reports");
        if (recentReports != null && recentReports.size() > 0) {
            int limit = Math.min(3, recentReports.size());
            player.sendMessage(Component.text("recent_apply_reports:", NamedTextColor.YELLOW));
            for (int idx = 0; idx < limit; idx++) {
                JsonElement element = recentReports.get(idx);
                if (!element.isJsonObject()) {
                    continue;
                }
                JsonObject row = element.getAsJsonObject();
                String line = defaultString(getString(row, "build_id"), "unknown")
                        + " | "
                        + defaultString(getString(row, "last_status"), "unknown")
                        + " | exec="
                        + defaultString(getString(row, "last_executed"), "0")
                        + " failed="
                        + defaultString(getString(row, "last_failed"), "0");
                player.sendMessage(Component.text("- " + line, NamedTextColor.WHITE));
            }
        }
    }

    private String extractCurrentTask(JsonObject active) {
        if (active == null || !active.has("tasks") || !active.get("tasks").isJsonArray()) {
            return null;
        }
        JsonArray tasks = active.getAsJsonArray("tasks");
        for (JsonElement element : tasks) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject task = element.getAsJsonObject();
            String status = getString(task, "status");
            if (status == null || "completed".equalsIgnoreCase(status)) {
                continue;
            }
            String title = getString(task, "title");
            if (title != null && !title.isBlank()) {
                return title;
            }
        }
        return null;
    }

    private String extractPendingSummary(JsonObject root) {
        JsonArray pending = getArray(root, "pending_conditions");
        if (pending == null || pending.size() == 0) {
            return "无";
        }
        JsonElement firstElement = pending.get(0);
        if (!firstElement.isJsonObject()) {
            return "无";
        }
        JsonObject first = firstElement.getAsJsonObject();
        String milestone = getString(first, "milestone_title");
        if (milestone != null && !milestone.isBlank()) {
            return milestone;
        }
        String taskTitle = getString(first, "task_title");
        if (taskTitle != null && !taskTitle.isBlank()) {
            return taskTitle;
        }
        return "无";
    }

    private String extractEventLabel(JsonObject event) {
        if (event == null) {
            return "无";
        }
        String questEvent = getString(event, "quest_event");
        if (questEvent != null && !questEvent.isBlank()) {
            return questEvent;
        }
        String target = getString(event, "target");
        if (target != null && !target.isBlank()) {
            return target;
        }
        String eventType = getString(event, "event_type");
        if (eventType != null && !eventType.isBlank()) {
            return eventType;
        }
        return "无";
    }

    private String joinStringArray(JsonArray array) {
        StringBuilder builder = new StringBuilder();
        for (JsonElement element : array) {
            if (element == null || !element.isJsonPrimitive()) {
                continue;
            }
            String value = element.getAsString();
            if (value == null || value.isBlank()) {
                continue;
            }
            if (builder.length() > 0) {
                builder.append(", ");
            }
            builder.append(value);
        }
        if (builder.length() == 0) {
            return "无";
        }
        return builder.toString();
    }

    private String defaultString(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value;
    }

    private String urlSegment(String text) {
        return URLEncoder.encode(text != null ? text : "", StandardCharsets.UTF_8);
    }

    private JsonObject getObject(JsonObject root, String key) {
        if (root == null || key == null || !root.has(key)) {
            return null;
        }
        JsonElement element = root.get(key);
        if (element != null && element.isJsonObject()) {
            return element.getAsJsonObject();
        }
        return null;
    }

    private JsonArray getArray(JsonObject root, String key) {
        if (root == null || key == null || !root.has(key)) {
            return null;
        }
        JsonElement element = root.get(key);
        if (element != null && element.isJsonArray()) {
            return element.getAsJsonArray();
        }
        return null;
    }

    private String getString(JsonObject root, String key) {
        if (root == null || key == null || !root.has(key)) {
            return null;
        }
        JsonElement element = root.get(key);
        if (element != null && element.isJsonPrimitive()) {
            return element.getAsString();
        }
        return null;
    }

    private boolean getBoolean(JsonObject root, String key, boolean fallback) {
        if (root == null || key == null || !root.has(key)) {
            return fallback;
        }
        JsonElement element = root.get(key);
        if (element != null && element.isJsonPrimitive()) {
            try {
                return element.getAsBoolean();
            } catch (UnsupportedOperationException ex) {
                return fallback;
            }
        }
        return fallback;
    }

    private int getInt(JsonObject root, String key, int fallback) {
        if (root == null || key == null || !root.has(key)) {
            return fallback;
        }
        JsonElement element = root.get(key);
        if (element != null && element.isJsonPrimitive()) {
            try {
                return element.getAsInt();
            } catch (NumberFormatException | UnsupportedOperationException ex) {
                return fallback;
            }
        }
        return fallback;
    }

    private int getInt(JsonElement element, int fallback) {
        if (element == null || !element.isJsonPrimitive()) {
            return fallback;
        }
        try {
            return element.getAsInt();
        } catch (NumberFormatException | UnsupportedOperationException ex) {
            return fallback;
        }
    }

    private double getDouble(JsonObject root, String key, double fallback) {
        if (root == null || key == null || !root.has(key)) {
            return fallback;
        }
        JsonElement element = root.get(key);
        if (element != null && element.isJsonPrimitive()) {
            try {
                return element.getAsDouble();
            } catch (NumberFormatException | UnsupportedOperationException ex) {
                return fallback;
            }
        }
        return fallback;
    }

    private String formatPosition(JsonObject position) {
        if (position == null) {
            return "无";
        }
        String world = defaultString(getString(position, "world"), "world");
        double x = getDouble(position, "x", 0.0);
        double y = getDouble(position, "y", 64.0);
        double z = getDouble(position, "z", 0.0);
        return String.format(Locale.ROOT, "(%.1f, %.1f, %.1f) @ %s", x, y, z, world);
    }

    private String formatDecimal(double value) {
        return String.format(Locale.ROOT, "%.3f", value);
    }
}
