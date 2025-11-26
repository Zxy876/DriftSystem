package com.driftmc.commands;

import java.lang.reflect.Type;
import java.util.HashMap;
import java.util.Map;

import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import com.driftmc.backend.BackendClient;
import com.driftmc.intent.IntentRouter;
import com.driftmc.session.PlayerSessionManager;
import com.driftmc.world.WorldPatchExecutor;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

/**
 * /saytoai <内容>
 * 和 AdvanceCommand 类似，但语义上是「显式对 AI 说话」。
 */
public class SayToAICommand implements CommandExecutor {

    private static final Gson GSON = new Gson();

    private final BackendClient backend;
    @SuppressWarnings("unused")
    private final IntentRouter router;
    private final WorldPatchExecutor world;
    @SuppressWarnings("unused")
    private final PlayerSessionManager sessions;

    public SayToAICommand(
            BackendClient backend,
            IntentRouter router,
            WorldPatchExecutor world,
            PlayerSessionManager sessions
    ) {
        this.backend = backend;
        this.router = router;
        this.world = world;
        this.sessions = sessions;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {

        if (!(sender instanceof Player player)) {
            sender.sendMessage(ChatColor.RED + "只有玩家可以对 AI 说话~");
            return true;
        }

        if (args.length == 0) {
            player.sendMessage(ChatColor.RED + "用法: /saytoai <内容>");
            return true;
        }

        String content = String.join(" ", args);

        player.sendMessage(ChatColor.LIGHT_PURPLE + "✧ 你对心悦宇宙说：「"
                + ChatColor.WHITE + content + ChatColor.LIGHT_PURPLE + "」");

        try {
            String playerId = player.getName();
            String path = "/story/advance/" + playerId;

            Map<String, Object> bodyMap = new HashMap<>();
            bodyMap.put("world_state", new HashMap<>());
            Map<String, Object> action = new HashMap<>();
            action.put("say", content);
            bodyMap.put("action", action);
            String body = GSON.toJson(bodyMap);

            String resp = backend.postJson(path, body);

            JsonObject root = JsonParser.parseString(resp).getAsJsonObject();
            if (root.has("node") && root.get("node").isJsonObject()) {
                JsonObject node = root.getAsJsonObject("node");
                String title = node.has("title") ? node.get("title").getAsString() : "";
                String text = node.has("text") ? node.get("text").getAsString() : "";

                if (!title.isEmpty()) {
                    player.sendMessage(ChatColor.AQUA + "【" + title + "】");
                }
                if (!text.isEmpty()) {
                    player.sendMessage(ChatColor.WHITE + text);
                }
            }

            // world_patch
            if (root.has("world_patch") && root.get("world_patch").isJsonObject()) {
                var patchObj = root.getAsJsonObject("world_patch");
                Type type = new TypeToken<Map<String, Object>>() {}.getType();
                Map<String, Object> patch = GSON.fromJson(patchObj, type);
                if (patch != null && !patch.isEmpty()) {
                    Object mcObj = patch.get("mc");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> mcPatch = (mcObj instanceof Map)
                            ? (Map<String, Object>) mcObj
                            : patch;
                    world.execute(player, mcPatch);
                }
            }

        } catch (Exception e) {
            player.sendMessage(ChatColor.RED + "❌ 与 AI 对话失败: " + e.getMessage());
        }

        return true;
    }
}