package com.driftmc.commands;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

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
 * 导演输入框指令（v1.21 最小版）
 * 角色：仅将导演输入的结构化文本转发到后端 /director/intents，默认 dry-run。
 * 不做什么：不解析自然语言、不生成 world patch、不直接调用 Mineflayer / RCON。
 */
public class DirectorInputCommand implements CommandExecutor {

    private static final Gson GSON = new Gson();

    private final JavaPlugin plugin;
    private final BackendClient backend;

    public DirectorInputCommand(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage(ChatColor.RED + "仅玩家可使用导演输入框。");
            return true;
        }
        if (!player.hasPermission("drift.directorinput")) {
            player.sendMessage(ChatColor.RED + "仅导演可执行此指令。");
            return true;
        }
        if (args.length == 0) {
            player.sendMessage(ChatColor.YELLOW + "用法: /directorinput <结构化指令>  示例: level level_id=demo target_state=SET_DRESS");
            return true;
        }

        String raw = String.join(" ", args);
        UUID playerUuid = player.getUniqueId();

        Map<String, Object> payload = new HashMap<>();
        payload.put("player_id", playerUuid.toString());
        payload.put("raw_text", raw);
        payload.put("dry_run", true);
        String json = GSON.toJson(payload);

        player.sendMessage(ChatColor.GRAY + "已提交导演意图 (dry-run)，等待后端回应...");

        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            try {
                backend.postJsonAsync("/director/intents", json, new Callback() {
                    @Override
                    public void onFailure(Call call, IOException e) {
                        Bukkit.getScheduler().runTask(plugin, () -> {
                            Player target = Bukkit.getPlayer(playerUuid);
                            if (target != null) {
                                target.sendMessage(ChatColor.RED + "后端请求失败: " + e.getMessage());
                            }
                        });
                    }

                    @Override
                    public void onResponse(Call call, Response response) throws IOException {
                        boolean ok = response.isSuccessful();
                        int code = response.code();
                        String body = response.body() != null ? response.body().string() : "";
                        response.close();
                        Bukkit.getScheduler().runTask(plugin, () -> {
                            Player target = Bukkit.getPlayer(playerUuid);
                            if (target == null) {
                                return;
                            }
                            if (!ok) {
                                target.sendMessage(ChatColor.RED + "后端拒绝: " + code + " " + body);
                                return;
                            }
                            target.sendMessage(ChatColor.GREEN + "✔ 导演意图已登记 (dry-run)。");
                            if (!body.isEmpty()) {
                                target.sendMessage(ChatColor.GRAY + body);
                            }
                        });
                    }
                });
            } catch (Exception e) {
                Bukkit.getScheduler().runTask(plugin, () -> {
                    Player target = Bukkit.getPlayer(playerUuid);
                    if (target != null) {
                        target.sendMessage(ChatColor.RED + "请求异常: " + e.getMessage());
                    }
                });
            }
        });

        return true;
    }
}
