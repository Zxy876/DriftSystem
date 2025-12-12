package com.driftmc.commands;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
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
 * /taskdebug — surfaces backend task debug snapshot for admins.
 */
public class TaskDebugCommand implements CommandExecutor {

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final String debugToken;

    public TaskDebugCommand(JavaPlugin plugin, BackendClient backend, String debugToken) {
        this.plugin = plugin;
        this.backend = backend;
        this.debugToken = debugToken != null ? debugToken : "";
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage(ChatColor.RED + "只有玩家可以执行 /taskdebug。记录型调试请使用后端工具。");
            return true;
        }

        if (!player.hasPermission("drift.taskdebug") && !player.isOp()) {
            player.sendMessage(ChatColor.RED + "你没有权限查看任务调试信息。");
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

                    if (!isSuccess || snapshot == null || !"ok".equalsIgnoreCase(getString(snapshot, "status"))) {
                        target.sendMessage(Component.text("未能获取任务调试信息。", NamedTextColor.RED));
                        return;
                    }

                    renderDebugSnapshot(target, snapshot);
                });
            }
        });
    }

    private void renderDebugSnapshot(Player player, JsonObject root) {
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
        JsonObject first = pending.get(0).getAsJsonObject();
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
}
