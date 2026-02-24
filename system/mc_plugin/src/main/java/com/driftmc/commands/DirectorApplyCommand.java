package com.driftmc.commands;

import java.io.IOException;
import java.util.UUID;
import java.util.HashMap;
import java.util.Map;
import java.util.List;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

/**
 * 导演建造指令：
 * - /director apply build <task_id> : 触发 bridge.js 执行（唯一开关）
 * - /director status build <task_id> : 查询状态
 * 默认所有建造意图均为 dry-run；只有 apply 才执行。
 */
public class DirectorApplyCommand implements CommandExecutor {

    private static final Gson GSON = new Gson();
    private final JavaPlugin plugin;
    private final BackendClient backend;

    public DirectorApplyCommand(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage(ChatColor.RED + "仅玩家可使用该指令。");
            return true;
        }
        if (!player.hasPermission("drift.directorapply")) {
            player.sendMessage(ChatColor.RED + "仅导演可执行建造任务。");
            return true;
        }
        if (args.length != 3 || (!"apply".equalsIgnoreCase(args[0]) && !"status".equalsIgnoreCase(args[0])) ||
                !"build".equalsIgnoreCase(args[1])) {
            player.sendMessage(
                    ChatColor.YELLOW + "用法: /director apply build <task_id> 或 /director status build <task_id>");
            return true;
        }

        String action = args[0].toLowerCase();
        String taskId = args[2];
        UUID playerId = player.getUniqueId();

        Map<String, Object> payload = new HashMap<>();
        payload.put("task_id", taskId);
        String json = GSON.toJson(payload);

        if ("status".equals(action)) {
            player.sendMessage(ChatColor.GRAY + "查询建造任务状态 " + taskId + "...");
            doPost(playerId, player, "/director/build/status?task_id=" + taskId, "GET", null);
            return true;
        }

        player.sendMessage(ChatColor.GRAY + "正在执行建造任务 " + taskId + "...");

        doPost(playerId, player, "/director/build/apply", "POST", json);

        return true;
    }

    private void doPost(UUID playerId, Player player, String path, String method, String json) {
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            try {
                if ("GET".equals(method)) {
                    backend.getAsync(path, new Callback() {
                        @Override
                        public void onFailure(Call call, IOException e) {
                            notifyError(playerId, "后端请求失败: " + e.getMessage());
                        }

                        @Override
                        public void onResponse(Call call, Response response) throws IOException {
                            handleResponse(playerId, response, true);
                        }
                    });
                } else {
                    backend.postJsonAsync(path, json, new Callback() {
                        @Override
                        public void onFailure(Call call, IOException e) {
                            notifyError(playerId, "后端请求失败: " + e.getMessage());
                        }

                        @Override
                        public void onResponse(Call call, Response response) throws IOException {
                            handleResponse(playerId, response, false);
                        }
                    });
                }
            } catch (Exception e) {
                notifyError(playerId, "请求异常: " + e.getMessage());
            }
        });
    }

    private void handleResponse(UUID playerId, Response response, boolean isStatus) throws IOException {
        boolean ok = response.isSuccessful();
        int code = response.code();
        String body = response.body() != null ? response.body().string() : "";
        response.close();
        Bukkit.getScheduler().runTask(plugin, () -> {
            Player target = Bukkit.getPlayer(playerId);
            if (target == null) {
                return;
            }
            if (!ok) {
                target.sendMessage(ChatColor.RED + (isStatus ? "状态查询失败: " : "执行失败: ") + code + " " + body);
                return;
            }

            Map<?, ?> map = null;
            try {
                map = GSON.fromJson(body, Map.class);
            } catch (Exception ignored) {
            }
            if (map != null && !isStatus) {
                broadcastStart(target, map);
                broadcastEnd(map);
            }
            if (map != null) {
                target.sendMessage(ChatColor.GREEN + (isStatus ? "状态: " : "执行结果: ") + map.toString());
                Object stdout = map.get("stdout");
                if (stdout instanceof List) {
                    List<?> lines = (List<?>) stdout;
                    int i = 0;
                    for (Object line : lines) {
                        if (i++ >= 5)
                            break;
                        target.sendMessage(ChatColor.GRAY + String.valueOf(line));
                    }
                }
                Object stderr = map.get("stderr");
                if (stderr instanceof List) {
                    List<?> lines = (List<?>) stderr;
                    int j = 0;
                    for (Object line : lines) {
                        if (j++ >= 3)
                            break;
                        target.sendMessage(ChatColor.DARK_RED + String.valueOf(line));
                    }
                }
            } else {
                target.sendMessage(ChatColor.GREEN + (isStatus ? "状态已返回。" : "已完成。"));
            }
        });
    }

    private void broadcastStart(Player initiator, Map<?, ?> map) {
        if (map == null) {
            return;
        }
        String taskId = String.valueOf(map.getOrDefault("task_id", "?"));
        String blueprint = String.valueOf(map.getOrDefault("blueprint_id", "?"));
        Object originObj = map.get("origin");
        String origin = originObj != null ? originObj.toString() : "{}";
        String startMsg = ChatColor.AQUA + "[建造开始] task=" + taskId + " blueprint=" + blueprint + " origin=" + origin
                + " dry-run=false";
        Bukkit.getServer().broadcastMessage(startMsg);
    }

    private void broadcastEnd(Map<?, ?> map) {
        String taskId = String.valueOf(map.getOrDefault("task_id", "?"));
        boolean failed = "failed".equals(map.get("status"));
        String endMsg = (failed ? ChatColor.RED : ChatColor.GREEN) + "[建造结束] task=" + taskId + " status="
                + map.get("status") + " exit=" + map.get("exit_code");
        Bukkit.getServer().broadcastMessage(endMsg);
    }

    private void notifyError(UUID playerId, String msg) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            Player target = Bukkit.getPlayer(playerId);
            if (target != null) {
                target.sendMessage(ChatColor.RED + msg);
            }
        });
    }
}
