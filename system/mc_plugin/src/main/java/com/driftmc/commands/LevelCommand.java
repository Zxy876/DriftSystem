package com.driftmc.commands;

import java.lang.reflect.Type;
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
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

/**
 * /level <level_id>
 * 调用后端：/story/load/{player}/{level_id}
 */
public class LevelCommand implements CommandExecutor {

    private static final Gson GSON = new Gson();

    private final BackendClient backend;
    @SuppressWarnings("unused")
    private final IntentRouter router;
    private final WorldPatchExecutor world;
    @SuppressWarnings("unused")
    private final PlayerSessionManager sessions;

    public LevelCommand(
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
            sender.sendMessage(ChatColor.RED + "只有玩家可以加载心悦关卡~");
            return true;
        }

        if (args.length != 1) {
            player.sendMessage(ChatColor.RED + "用法: /level <level_id>");
            return true;
        }

        String levelId = args[0];
        String playerId = player.getName();

        player.sendMessage(ChatColor.YELLOW + "📘 正在为 "
                + ChatColor.AQUA + playerId
                + ChatColor.YELLOW + " 加载关卡: "
                + ChatColor.GOLD + levelId);

        try {
            String path = "/story/load/" + playerId + "/" + levelId;
            String body = "{}";

            String resp = backend.postJson(path, body);

            // 解析 JSON，尝试执行 bootstrap_patch
            applyPatchFromResponse(player, resp, true);

            String msg = extractMsg(resp);
            if (msg == null || msg.isEmpty()) {
                msg = "关卡已加载，欢迎来到心悦宇宙的这一章。";
            }

            player.sendMessage(ChatColor.GREEN + "✔ " + msg);

        } catch (Exception e) {
            player.sendMessage(ChatColor.RED + "❌ 加载关卡失败: " + e.getMessage());
        }

        return true;
    }

    // ------------ JSON 帮助 ------------

    private String extractMsg(String resp) {
        try {
            JsonObject root = JsonParser.parseString(resp).getAsJsonObject();
            if (root.has("msg") && root.get("msg").isJsonPrimitive()) {
                return root.get("msg").getAsString();
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private void applyPatchFromResponse(Player player, String resp, boolean useBootstrap) {
        try {
            JsonElement rootEl = JsonParser.parseString(resp);
            if (!rootEl.isJsonObject()) return;

            JsonObject root = rootEl.getAsJsonObject();
            JsonObject patchObj = null;

            if (useBootstrap && root.has("bootstrap_patch") && root.get("bootstrap_patch").isJsonObject()) {
                patchObj = root.getAsJsonObject("bootstrap_patch");
            } else if (root.has("world_patch") && root.get("world_patch").isJsonObject()) {
                patchObj = root.getAsJsonObject("world_patch");
            }

            if (patchObj == null) return;

            Type type = new TypeToken<Map<String, Object>>() {}.getType();
            Map<String, Object> patch = GSON.fromJson(patchObj, type);
            if (patch == null || patch.isEmpty()) return;

            Object mcObj = patch.get("mc");
            Map<String, Object> mcPatch;
            if (mcObj instanceof Map<?, ?> m) {
                mcPatch = (Map<String, Object>) m;
            } else {
                mcPatch = patch;
            }

            world.execute(player, mcPatch);

        } catch (Exception ignored) {
        }
    }
}