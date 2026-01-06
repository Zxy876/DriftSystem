package com.driftmc.commands.custom;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

/**
 * Teleport command that jumps to the recorded location of an executed Ideal City build plan.
 */
public class CmdPlanJump implements CommandExecutor {

    private final JavaPlugin plugin;
    private final BackendClient backend;

    public CmdPlanJump(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }

        if (args.length == 0) {
            player.sendMessage("§c用法: /planjump <执行日志ID或文件名>");
            return true;
        }

        String requestedId = args[0].trim();
        if (requestedId.isEmpty()) {
            player.sendMessage("§c请提供执行日志文件名。");
            return true;
        }

        String normalizedId = normalizePlanId(requestedId);
        if (normalizedId == null) {
            player.sendMessage("§c提供的文件名不合法。");
            return true;
        }

        player.sendMessage("§7[PlanJump] 正在查询 " + normalizedId + " …");

        String encoded = URLEncoder.encode(normalizedId, StandardCharsets.UTF_8);
        String path = "/ideal-city/build-plans/executed/" + encoded;

        backend.getAsync(path, new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().log(Level.WARNING, "[PlanJump] backend error", e);
                Bukkit.getScheduler().runTask(plugin, () -> player.sendMessage("§c[PlanJump] 后端暂时不可用。"));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                try (response) {
                    String body = response.body() != null ? response.body().string() : "{}";
                    if (!response.isSuccessful()) {
                        plugin.getLogger().log(Level.WARNING,
                                "[PlanJump] backend replied HTTP {0} payload {1}",
                                new Object[] { response.code(), body });
                        Bukkit.getScheduler().runTask(plugin,
                                () -> player.sendMessage("§c[PlanJump] 未找到执行日志或后端出错。"));
                        return;
                    }

                    JsonObject root;
                    try {
                        JsonElement parsed = JsonParser.parseString(body);
                        if (!parsed.isJsonObject()) {
                            throw new IllegalStateException("Payload is not a JSON object");
                        }
                        root = parsed.getAsJsonObject();
                    } catch (Exception ex) {
                        plugin.getLogger().log(Level.WARNING, "[PlanJump] invalid JSON payload", ex);
                        Bukkit.getScheduler().runTask(plugin,
                                () -> player.sendMessage("§c[PlanJump] 无法解析后端返回的数据。"));
                        return;
                    }

                    if (!root.has("status") || !"ok".equalsIgnoreCase(root.get("status").getAsString())) {
                        Bukkit.getScheduler().runTask(plugin,
                                () -> player.sendMessage("§c[PlanJump] 后端返回失败: " + root));
                        return;
                    }

                    JsonObject plan = root.has("plan") && root.get("plan").isJsonObject()
                            ? root.getAsJsonObject("plan")
                            : null;
                    if (plan == null) {
                        Bukkit.getScheduler().runTask(plugin,
                                () -> player.sendMessage("§c[PlanJump] 未找到执行日志详情。"));
                        return;
                    }

                    TeleportTarget target = extractTarget(plan);
                    if (target == null) {
                        Bukkit.getScheduler().runTask(plugin,
                                () -> player.sendMessage("§e[PlanJump] 该记录缺少有效坐标。"));
                        return;
                    }

                    Bukkit.getScheduler().runTask(plugin, () -> {
                        World world = Bukkit.getWorld(target.world);
                        if (world == null) {
                            player.sendMessage("§c[PlanJump] 世界 " + target.world + " 未加载。");
                            return;
                        }
                        Location location = new Location(world, target.x, target.y, target.z, player.getLocation().getYaw(), player.getLocation().getPitch());
                        player.teleport(location);
                        if (target.summary != null && !target.summary.isBlank()) {
                            player.sendMessage("§a[PlanJump] 已跳转到: " + target.summary);
                        } else {
                            player.sendMessage("§a[PlanJump] 已跳转。");
                        }
                        player.sendMessage(String.format("§7定位: %s (%.1f, %.1f, %.1f)", target.world, target.x, target.y, target.z));
                    });
                }
            }
        });

        return true;
    }

    private String normalizePlanId(String input) {
        String cleaned = input.trim();
        if (cleaned.isEmpty()) {
            return null;
        }
        if (cleaned.toLowerCase().endsWith(".json")) {
            cleaned = cleaned.substring(0, cleaned.length() - 5);
        }
        return cleaned.isEmpty() ? null : cleaned;
    }

    private TeleportTarget extractTarget(JsonObject plan) {
        JsonObject location = plan.has("location") && plan.get("location").isJsonObject()
                ? plan.getAsJsonObject("location")
                : null;
        if (location == null) {
            location = plan.has("player_pose") && plan.get("player_pose").isJsonObject()
                    ? plan.getAsJsonObject("player_pose")
                    : null;
        }
        if (location == null) {
            return null;
        }

        String world = location.has("world") ? location.get("world").getAsString() : "world";
        double x = location.has("x") ? location.get("x").getAsDouble()
                : (location.has("x_f") ? location.get("x_f").getAsDouble() : 0.0);
        double y = location.has("y") ? location.get("y").getAsDouble() : 64.0;
        double z = location.has("z") ? location.get("z").getAsDouble()
                : (location.has("z_f") ? location.get("z_f").getAsDouble() : 0.0);

        String summary = plan.has("summary") ? plan.get("summary").getAsString() : null;

        return new TeleportTarget(world, x, y, z, summary);
    }

    private static class TeleportTarget {
        final String world;
        final double x;
        final double y;
        final double z;
        final String summary;

        TeleportTarget(String world, double x, double y, double z, String summary) {
            this.world = world;
            this.x = x;
            this.y = y;
            this.z = z;
            this.summary = summary;
        }
    }
}
