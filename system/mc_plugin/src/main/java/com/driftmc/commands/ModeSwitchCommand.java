package com.driftmc.commands;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.world.WorldPatchExecutor;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

public class ModeSwitchCommand implements CommandExecutor {

    private static final Gson GSON = new Gson();

    private final Plugin plugin;
    private final BackendClient backend;
    private final WorldPatchExecutor worldPatcher;
    private final String endpoint;
    private final String successMessage;

    public ModeSwitchCommand(
            Plugin plugin,
            BackendClient backend,
            WorldPatchExecutor worldPatcher,
            String endpoint,
            String successMessage) {
        this.plugin = plugin;
        this.backend = backend;
        this.worldPatcher = worldPatcher;
        this.endpoint = endpoint;
        this.successMessage = successMessage;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("只有玩家可以切换模式");
            return true;
        }

        Map<String, Object> body = new HashMap<>();
        body.put("player_id", player.getName());
        body.put("trigger_type", "command");

        backend.postJsonAsync(endpoint, GSON.toJson(body), new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                Bukkit.getScheduler().runTask(plugin,
                        () -> player.sendMessage("§c[模式切换失败] " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                try (response) {
                    String raw = response.body() != null ? response.body().string() : "{}";
                    JsonObject root = JsonParser.parseString(raw).getAsJsonObject();
                    JsonObject worldPatchObj = root.has("world_patch") && root.get("world_patch").isJsonObject()
                            ? root.getAsJsonObject("world_patch")
                            : null;

                    Bukkit.getScheduler().runTask(plugin, () -> {
                        player.sendMessage(successMessage);
                        if (worldPatchObj != null && worldPatchObj.size() > 0) {
                            @SuppressWarnings("unchecked")
                            Map<String, Object> patch = GSON.fromJson(worldPatchObj, Map.class);
                            worldPatcher.execute(player, patch);
                        }
                    });
                } catch (Exception ex) {
                    Bukkit.getScheduler().runTask(plugin,
                            () -> player.sendMessage("§c[模式切换失败] 响应解析异常"));
                }
            }
        });

        return true;
    }
}
