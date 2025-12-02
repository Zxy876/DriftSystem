package com.driftmc.intent2;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.HashMap;
import java.util.Map;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.world.WorldPatchExecutor;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

public class IntentDispatcher2 {

    private final Plugin plugin;
    private final BackendClient backend;
    private final WorldPatchExecutor world;

    private static final Gson GSON = new Gson();
    private static final Type MAP_TYPE = new TypeToken<Map<String, Object>>() {}.getType();

    public IntentDispatcher2(Plugin plugin, BackendClient backend, WorldPatchExecutor world) {
        this.plugin = plugin;
        this.backend = backend;
        this.world = world;
    }


    // ============================================================
    // 主入口
    // ============================================================
    public void dispatch(Player p, IntentResponse2 intent) {

        switch (intent.type) {

            case SHOW_MINIMAP -> showMinimap(p, intent);

            case GOTO_LEVEL, GOTO_NEXT_LEVEL ->
                gotoLevelAndLoad(p, intent);

            case SET_DAY, SET_NIGHT, SET_WEATHER,
                 TELEPORT, SPAWN_ENTITY, BUILD_STRUCTURE ->
                runWorldCommand(p, intent);

            case SAY_ONLY, STORY_CONTINUE, UNKNOWN ->
                pushToStoryEngine(p, intent.rawText);

            default -> {}
        }
    }


    // ============================================================
    // 世界命令
    // ============================================================
    private void runWorldCommand(Player p, IntentResponse2 intent) {

        final Player fp = p;
        final IntentResponse2 fintent = intent;

        Map<String, Object> mc = new HashMap<>();

        switch (fintent.type) {
            case SET_DAY -> mc.put("time", "day");
            case SET_NIGHT -> mc.put("time", "night");
            case SET_WEATHER -> {
                String raw = fintent.rawText != null ? fintent.rawText : "";
                String w = raw.contains("雨") ? "rain" :
                           raw.contains("雷") ? "thunder" : "clear";
                mc.put("weather", w);
            }
            case TELEPORT ->
                mc.put("teleport", Map.of("mode", "relative", "x", 0, "y", 0, "z", 3));
            case SPAWN_ENTITY ->
                mc.put("spawn", Map.of("type", "ARMOR_STAND"));
            case BUILD_STRUCTURE ->
                mc.put("build", Map.of("shape", "platform", "size", 4));
            default -> {}
        }

        world.execute(fp, Map.of("mc", mc));
    }


    // ============================================================
    // 小地图展示
    // ============================================================
    private void showMinimap(Player p, IntentResponse2 intent) {

        final Player fp = p;
        final IntentResponse2 fintent = intent;

        JsonObject mm = fintent.minimap;
        if (mm == null) {
            fp.sendMessage("§c[小地图] 后端未返回 minimap 数据。");
            return;
        }

        String cur = mm.has("current_level") ? mm.get("current_level").getAsString() : "未知";
        String nxt = mm.has("recommended_next") ? mm.get("recommended_next").getAsString() : "无";

        fp.sendMessage("§b--- 心悦小地图 ---");
        fp.sendMessage("当前关卡: §a" + cur);
        fp.sendMessage("推荐下一关: §d" + nxt);
        fp.sendMessage("§b-------------------");
    }


    // ============================================================
    // 表达类 → 推进剧情
    // ============================================================
    private void pushToStoryEngine(Player p, String text) {

        final Player fp = p;
        final String ftext = text;

        Map<String, Object> body = Map.of(
                "player_id", fp.getName(),
                "action", Map.of("say", ftext),
                "world_state", Map.of()
        );

        backend.postJsonAsync("/world/apply", GSON.toJson(body), new Callback() {

            @Override
            public void onFailure(Call call, IOException e) {
                Bukkit.getScheduler().runTask(plugin,
                        () -> fp.sendMessage("§c[剧情错误] " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response resp) throws IOException {

                final String respStr = resp.body() != null ? resp.body().string() : "{}";
                final JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

                // 安全解析 story_node
                final JsonObject node =
                        (root.has("story_node") && root.get("story_node").isJsonObject())
                                ? root.get("story_node").getAsJsonObject()
                                : null;

                // 安全解析 world_patch
                final JsonObject wpatch =
                        (root.has("world_patch") && root.get("world_patch").isJsonObject())
                                ? root.get("world_patch").getAsJsonObject()
                                : null;

                Bukkit.getScheduler().runTask(plugin, () -> {

                    // 打印剧情文本
                    if (node != null) {
                        if (node.has("title"))
                            fp.sendMessage("§d【" + node.get("title").getAsString() + "】");
                        if (node.has("text"))
                            fp.sendMessage("§f" + node.get("text").getAsString());
                    }

                    // 执行世界 patch
                    if (wpatch != null && wpatch.size() > 0) {
                        Map<String, Object> patch = GSON.fromJson(wpatch, MAP_TYPE);
                        world.execute(fp, patch);
                    }
                });
            }
        });
    }


    // ============================================================
    // 跳关（传送 + 加载剧情）
    // ============================================================
    private void gotoLevelAndLoad(Player p, IntentResponse2 intent) {

        final Player fp = p;
        final String levelId = intent.levelId;
        final JsonObject minimap = intent.minimap;

        if (levelId == null) {
            fp.sendMessage("§c跳关失败：没有 levelId");
            return;
        }

        if (minimap == null || !minimap.has("nodes")) {
            fp.sendMessage("§c跳关失败：minimap 缺失");
            return;
        }

        final JsonArray nodes = minimap.getAsJsonArray("nodes");

        int tx = 0, tz = 0;
        boolean found = false;

        for (int i = 0; i < nodes.size(); i++) {
            JsonObject n = nodes.get(i).getAsJsonObject();
            if (n.get("level").getAsString().equals(levelId)) {
                JsonObject pos = n.getAsJsonObject("pos");
                tx = pos.get("x").getAsInt();
                tz = pos.get("y").getAsInt();
                found = true;
                break;
            }
        }

        if (!found) {
            fp.sendMessage("§c跳关失败：地图中不存在 " + levelId);
            return;
        }

        final int ftx = tx;
        final int ftz = tz;
        final int fty = 80;

        // --- 执行传送（主线程） ---
        Bukkit.getScheduler().runTask(plugin, () -> {
            fp.teleport(new Location(fp.getWorld(), ftx, fty, ftz));
            fp.sendMessage("§a已跳转到 " + levelId);
        });

        // --- 加载剧情（异步 → 应用到主线程） ---
        backend.postJsonAsync("/story/load/" + fp.getName() + "/" + levelId,
                "{}",
                new Callback() {

                    @Override
                    public void onFailure(Call call, IOException e) {
                        Bukkit.getScheduler().runTask(plugin,
                                () -> fp.sendMessage("§c[剧情加载失败] " + e.getMessage()));
                    }

                    @Override
                    public void onResponse(Call call, Response resp) throws IOException {

                        final String respStr = resp.body() != null ? resp.body().string() : "{}";
                        final JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

                        final JsonObject patchObj =
                                (root.has("bootstrap_patch") && root.get("bootstrap_patch").isJsonObject())
                                        ? root.getAsJsonObject("bootstrap_patch")
                                        : null;

                        if (patchObj != null) {
                            final Map<String, Object> patch = GSON.fromJson(patchObj, MAP_TYPE);

                            Bukkit.getScheduler().runTask(plugin,
                                    () -> world.execute(fp, patch));
                        }
                    }
                }
        );
    }
}