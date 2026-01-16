package com.driftmc.intent2;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;
import java.util.regex.Pattern;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.commands.IdealCityCommand;
import com.driftmc.hud.QuestLogHud;
import com.driftmc.hud.dialogue.ChoicePanel;
import com.driftmc.hud.dialogue.DialoguePanel;
import com.driftmc.story.LevelIds;
import com.driftmc.tutorial.TutorialManager;
import com.driftmc.tutorial.TutorialState;
import com.driftmc.world.WorldPatchExecutor;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;
import okhttp3.ResponseBody;

public class IntentDispatcher2 {

    private final Plugin plugin;
    private final BackendClient backend;
    private final WorldPatchExecutor world;
    private TutorialManager tutorialManager;
    private QuestLogHud questLogHud;
    private DialoguePanel dialoguePanel;
    private ChoicePanel choicePanel;
    private final Set<UUID> tutorialReentryWarned = ConcurrentHashMap.newKeySet();
    private IdealCityCommand idealCityCommand;
    private boolean storyCreationEnabled = false;

    private static final Gson GSON = new Gson();
    private static final Type MAP_TYPE = new TypeToken<Map<String, Object>>() {
    }.getType();
    private static final String PRIMARY_LEVEL_ID = "flagship_03";
    private static final Pattern BLOCK_ID_PATTERN = Pattern.compile("minecraft:[a-z0-9_./\\-]+", Pattern.CASE_INSENSITIVE);

    public IntentDispatcher2(Plugin plugin, BackendClient backend, WorldPatchExecutor world) {
        this.plugin = plugin;
        this.backend = backend;
        this.world = world;
    }

    public void setTutorialManager(TutorialManager manager) {
        this.tutorialManager = manager;
    }

    public void setQuestLogHud(QuestLogHud questLogHud) {
        this.questLogHud = questLogHud;
    }

    public void setDialoguePanel(DialoguePanel dialoguePanel) {
        this.dialoguePanel = dialoguePanel;
    }

    public void setChoicePanel(ChoicePanel choicePanel) {
        this.choicePanel = choicePanel;
    }

    public void setIdealCityCommand(IdealCityCommand idealCityCommand) {
        this.idealCityCommand = idealCityCommand;
    }

    public void setStoryCreationEnabled(boolean enabled) {
        this.storyCreationEnabled = enabled;
    }

    private boolean ensureUnlocked(Player player, TutorialState required, String message) {
        if (tutorialManager == null || tutorialManager.isTutorialComplete(player)) {
            return true;
        }
        return tutorialManager.ensureUnlocked(player, required, message);
    }

    private void syncTutorialState(Player player, Map<String, Object> patch) {
        if (tutorialManager == null || patch == null || patch.isEmpty()) {
            return;
        }
        tutorialManager.syncWorldPatch(player, patch);
    }

    // ============================================================
    // 主入口
    // ============================================================
    public void dispatch(Player p, IntentResponse2 intent) {

        IntentResponse2 effectiveIntent = enforceCreateBlockOverride(intent);
        IntentType2 intentType = effectiveIntent.type != null ? effectiveIntent.type : IntentType2.UNKNOWN;

        switch (intentType) {

            case SHOW_MINIMAP:
                showMinimap(p, effectiveIntent);
                break;

            case GOTO_LEVEL:
            case GOTO_NEXT_LEVEL:
                gotoLevelAndLoad(p, effectiveIntent);
                break;

            case SET_DAY:
            case SET_NIGHT:
            case SET_WEATHER:
            case TELEPORT:
            case SPAWN_ENTITY:
            case BUILD_STRUCTURE:
                runWorldCommand(p, effectiveIntent);
                break;

            case CREATE_BLOCK:
                handleCreateBlock(p, effectiveIntent);
                break;

            case CREATE_STORY:
                createStory(p, effectiveIntent);
                break;

            case IDEAL_CITY_SUBMIT:
                submitIdealCity(p, effectiveIntent);
                break;

            case SAY_ONLY:
            case STORY_CONTINUE:
            case UNKNOWN:
                pushToStoryEngine(p, effectiveIntent.rawText);
                break;

            default:
                break;
        }
    }

    private IntentResponse2 enforceCreateBlockOverride(IntentResponse2 intent) {
        if (intent == null) {
            return new IntentResponse2(IntentType2.UNKNOWN, null, null, "", null);
        }

        IntentType2 originalType = intent.type != null ? intent.type : IntentType2.UNKNOWN;
        if (originalType == IntentType2.CREATE_BLOCK) {
            return intent;
        }

        if (isLikelyBlockPlacement(intent.rawText)) {
            plugin.getLogger().warning("[IntentDispatcher] Hard override to CREATE_BLOCK, rawText=" + intent.rawText);
            return new IntentResponse2(
                    IntentType2.CREATE_BLOCK,
                    intent.levelId,
                    intent.minimap,
                    intent.rawText,
                    null);
        }

        return intent;
    }

    // ============================================================
    // 创建方块 (CREATE_BLOCK)
    // ============================================================
    private void handleCreateBlock(Player p, IntentResponse2 intent) {
        if (p == null) {
            return;
        }

        String rawText = intent != null ? intent.rawText : null;
        if (rawText == null || rawText.isBlank()) {
            p.sendMessage("§c[造物] 未能解析你的请求，请描述要放置的方块和坐标。");
            plugin.getLogger().warning("[IntentDispatcher] CREATE_BLOCK 请求缺少 rawText");
            return;
        }

        final Player fp = p;
        fp.sendMessage("§b[造物] 正在解析并执行你的建造请求...");

        Map<String, Object> payload = new HashMap<>();
        payload.put("message", rawText);
        payload.put("player_id", fp.getName());
        payload.put("dry_run_only", false);

        String jsonBody = GSON.toJson(payload);

        backend.postJsonAsync("/intent/execute", jsonBody, new Callback() {

            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().log(Level.WARNING, "[IntentDispatcher] CREATE_BLOCK 执行失败: {0}", e.getMessage());
                Bukkit.getScheduler().runTask(plugin,
                        () -> fp.sendMessage("§c[造物] 自动执行失败: " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response resp) throws IOException {
                try (Response response = resp) {
                    String respStr = response.body() != null ? response.body().string() : "{}";

                    JsonObject root;
                    try {
                        root = JsonParser.parseString(respStr).getAsJsonObject();
                    } catch (Exception parseError) {
                        plugin.getLogger().log(Level.WARNING,
                                "[IntentDispatcher] CREATE_BLOCK 响应解析失败: {0}", parseError.getMessage());
                        Bukkit.getScheduler().runTask(plugin,
                                () -> fp.sendMessage("§c[造物] 服务端返回异常数据"));
                        return;
                    }

                    plugin.getLogger().info("[IntentDispatcher] CREATE_BLOCK response = "
                            + respStr.substring(0, Math.min(200, respStr.length())));

                    if (!response.isSuccessful()) {
                        String errorMessage = root.has("detail") && root.get("detail").isJsonPrimitive()
                                ? root.get("detail").getAsString()
                                : ("HTTP " + response.code());
                        Bukkit.getScheduler().runTask(plugin,
                                () -> fp.sendMessage("§c[造物] 服务端错误: " + errorMessage));
                        return;
                    }

                    Bukkit.getScheduler().runTask(plugin, () -> handleCreateBlockResponse(fp, root));
                }
            }
        });
    }

    private void handleCreateBlockResponse(Player player, JsonObject root) {
        if (player == null || root == null) {
            return;
        }

        String status = root.has("status") && root.get("status").isJsonPrimitive()
                ? root.get("status").getAsString()
                : "";

        if ("not_creation".equalsIgnoreCase(status)) {
            player.sendMessage("§c[造物] 这条消息未被识别为造物指令，请补充准确的方块与坐标。");
            plugin.getLogger().warning("[IntentDispatcher] CREATE_BLOCK returned not_creation");
            return;
        }

        JsonObject payload = new JsonObject();
        String normalizedStatus = status == null || status.isBlank() ? "unknown" : status;
        payload.addProperty("status", normalizedStatus);
        payload.addProperty("auto_execute", "ok".equalsIgnoreCase(normalizedStatus));

        if (root.has("report") && root.get("report").isJsonObject()) {
            payload.add("report", root.getAsJsonObject("report"));
        }

        if (root.has("plan") && root.get("plan").isJsonObject()) {
            payload.add("plan", root.getAsJsonObject("plan"));
        }

        if (root.has("error") && root.get("error").isJsonPrimitive()) {
            payload.add("error", root.get("error"));
        }

        displayCreationResult(player, payload);
    }

    // ============================================================
    // 理想之城规格提交 (IDEAL_CITY_SUBMIT)
    // ============================================================
    private void submitIdealCity(Player player, IntentResponse2 intent) {
        if (idealCityCommand == null) {
            plugin.getLogger().warning("[IntentDispatcher] IdealCityCommand 未绑定，忽略自然语言提交。");
            player.sendMessage("§c[IdealCity] 功能暂未启用，请联系管理员。");
            return;
        }

        String narrative = intent != null ? intent.rawText : null;
        if (!idealCityCommand.submitNarrative(player, narrative)) {
            player.sendMessage("§c[IdealCity] 我暂时听不懂，请补充具体建造想法。");
        }
    }

    // ============================================================
    // 创建剧情 (CREATE_STORY)
    // ============================================================
    private void createStory(Player p, IntentResponse2 intent) {
        if (!storyCreationEnabled) {
            p.sendMessage("§e[剧情创作] 功能已下线，当前版本仅支持既有关卡。");
            plugin.getLogger().info("[IntentDispatcher] 忽略剧情创作请求：功能已禁用");
            return;
        }
        final Player fp = p;

        if (!ensureUnlocked(fp, TutorialState.CREATE_STORY, "请继续当前教学提示后再创造剧情。")) {
            return;
        }

        // 从 rawText 中提取标题和内容
        String rawText = intent.rawText != null ? intent.rawText : "新剧情";
        String title = rawText.length() > 12 ? rawText.substring(0, 12) : rawText;

        Map<String, Object> body = new HashMap<>();
        body.put("level_id", "flagship_custom_" + System.currentTimeMillis());
        body.put("title", title);
        body.put("text", rawText);

        String jsonBody = GSON.toJson(body);

        fp.sendMessage("§e✨ 正在创建新剧情...");

        backend.postJsonAsync("/story/inject", jsonBody, new Callback() {

            @Override
            public void onFailure(Call call, IOException e) {
                Bukkit.getScheduler().runTask(plugin,
                        () -> fp.sendMessage("§c[创建剧情失败] " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response resp) throws IOException {
                try (resp) {
                    String respStr = resp.body() != null ? resp.body().string() : "{}";
                    JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

                    Bukkit.getScheduler().runTask(plugin, () -> {
                        if (root.has("status") && "ok".equals(root.get("status").getAsString())) {
                            String levelId = root.has("level_id") ? root.get("level_id").getAsString() : "未知";
                            fp.sendMessage("§a✅ 剧情创建成功！");
                            fp.sendMessage("§7关卡ID: " + levelId);

                            // 立即加载新创建的关卡（这样会应用场景和NPC）
                            loadLevelForPlayer(fp, levelId, intent);
                        } else {
                            String msg = root.has("detail") ? root.get("detail").getAsString() : "未知错误";
                            fp.sendMessage("§c创建失败: " + msg);
                        }
                    });
                }
            }
        });
    }

    // ============================================================
    // 为玩家加载关卡（应用场景和NPC）
    // ============================================================
    private void loadLevelForPlayer(Player p, String levelId, IntentResponse2 intent) {
        final Player fp = p;
        final String canonicalLevel = LevelIds.canonicalizeOrDefault(
                enforceTutorialExitRedirect(fp, levelId, intent != null ? intent.rawText : null));

        fp.sendMessage("§e🌍 正在加载关卡场景...");

        backend.postJsonAsync("/story/load/" + fp.getName() + "/" + canonicalLevel, "{}", new Callback() {

            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().warning("[加载关卡] 失败: " + e.getMessage());
                Bukkit.getScheduler().runTask(plugin, () -> {
                    fp.sendMessage("§c[加载场景失败] " + e.getMessage());

                    // 失败时使用intent中的worldPatch作为备用
                    if (intent != null && intent.worldPatch != null) {
                        plugin.getLogger().info("[加载关卡] 使用备用worldPatch");
                        Map<String, Object> patch = GSON.fromJson(intent.worldPatch, MAP_TYPE);
                        syncTutorialState(fp, patch);
                        world.execute(fp, patch);
                    }
                });
            }

            @Override
            public void onResponse(Call call, Response resp) throws IOException {
                final String respStr = resp.body() != null ? resp.body().string() : "{}";
                plugin.getLogger().info("[加载关卡] 收到响应: " + respStr.substring(0, Math.min(200, respStr.length())));

                final JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

                final JsonObject patchObj = (root.has("bootstrap_patch") && root.get("bootstrap_patch").isJsonObject())
                        ? root.getAsJsonObject("bootstrap_patch")
                        : null;

                Bukkit.getScheduler().runTask(plugin, () -> {
                    if (patchObj != null && patchObj.size() > 0) {
                        plugin.getLogger().info("[加载关卡] 应用bootstrap_patch");
                        Map<String, Object> patch = GSON.fromJson(patchObj, MAP_TYPE);
                        syncTutorialState(fp, patch);
                        world.execute(fp, patch);
                        fp.sendMessage("§a✨ 场景已加载！");
                    } else {
                        plugin.getLogger().warning("[加载关卡] bootstrap_patch为空");

                        // 如果后端没有返回patch，使用intent中的worldPatch
                        if (intent != null && intent.worldPatch != null) {
                            plugin.getLogger().info("[加载关卡] 使用intent的worldPatch");
                            Map<String, Object> patch = GSON.fromJson(intent.worldPatch, MAP_TYPE);
                            syncTutorialState(fp, patch);
                            world.execute(fp, patch);
                            fp.sendMessage("§a✨ 场景已加载！");
                        } else {
                            fp.sendMessage("§7（场景数据为空）");
                        }
                    }

                    if (questLogHud != null) {
                        questLogHud.showQuestLog(fp, QuestLogHud.Trigger.LEVEL_ENTER);
                    }
                });
            }
        });
    }

    // ============================================================
    // 世界命令
    // ============================================================
    private void runWorldCommand(Player p, IntentResponse2 intent) {

        Map<String, Object> mc = new HashMap<>();

        switch (intent.type) {
            case SET_DAY:
                mc.put("time", "day");
                break;

            case SET_NIGHT:
                mc.put("time", "night");
                break;

            case SET_WEATHER:
                String raw = intent.rawText != null ? intent.rawText : "";
                String w = raw.contains("雨") ? "rain" : raw.contains("雷") ? "thunder" : "clear";
                mc.put("weather", w);
                break;

            case TELEPORT:
                Map<String, Object> t = new HashMap<>();
                t.put("mode", "relative");
                t.put("x", 0);
                t.put("y", 0);
                t.put("z", 3);
                mc.put("teleport", t);
                break;

            case SPAWN_ENTITY:
                Map<String, Object> s = new HashMap<>();
                s.put("type", "ARMOR_STAND");
                mc.put("spawn", s);
                break;

            case BUILD_STRUCTURE:
                Map<String, Object> b = new HashMap<>();
                b.put("shape", "platform");
                b.put("size", 4);
                mc.put("build", b);
                break;

            default:
                break;
        }

        Map<String, Object> body = new HashMap<>();
        body.put("mc", mc);

        world.execute(p, body);
    }

    // ============================================================
    // 小地图展示 - 显示PNG图片
    // ============================================================
    private void showMinimap(Player p, IntentResponse2 intent) {

        if (!ensureUnlocked(p, TutorialState.VIEW_MAP, "完成小地图教学后即可使用该功能。")) {
            return;
        }

        JsonObject mm = intent.minimap;
        if (mm == null) {
            p.sendMessage("§c[小地图] 后端未返回 minimap 数据。");
            return;
        }

        // 显示当前关卡信息
        String cur = (mm.has("current_level") && !mm.get("current_level").isJsonNull())
                ? LevelIds.canonicalizeLevelId(mm.get("current_level").getAsString())
                : "未知";
        String nxt = (mm.has("recommended_next") && !mm.get("recommended_next").isJsonNull())
                ? LevelIds.canonicalizeLevelId(mm.get("recommended_next").getAsString())
                : "无";

        p.sendMessage("§b--- 心悦小地图 ---");
        p.sendMessage("当前关卡: §a" + cur);
        p.sendMessage("推荐下一关: §d" + nxt);

        // 异步获取PNG地图并给予玩家
        final Player fp = p;
        backend.getAsync("/minimap/give/" + p.getName(), new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().warning("[小地图PNG] 获取失败: " + e.getMessage());
                Bukkit.getScheduler().runTask(plugin,
                        () -> fp.sendMessage("§c[小地图] PNG生成失败"));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) {
                    plugin.getLogger().warning("[小地图PNG] HTTP " + response.code());
                    Bukkit.getScheduler().runTask(plugin,
                            () -> fp.sendMessage("§c[小地图] 服务器返回错误"));
                    return;
                }

                String json = response.body().string();
                JsonObject obj = GSON.fromJson(json, JsonObject.class);

                // 后端返回的格式: { "status": "ok", "mc": { ... } }
                JsonObject mcPayload = null;
                if (obj.has("world_patch") && obj.get("world_patch").isJsonObject()) {
                    JsonObject worldPatch = obj.getAsJsonObject("world_patch");
                    if (worldPatch.has("mc") && worldPatch.get("mc").isJsonObject()) {
                        mcPayload = worldPatch.getAsJsonObject("mc");
                    }
                }
                if (mcPayload == null && obj.has("mc") && obj.get("mc").isJsonObject()) {
                    mcPayload = obj.getAsJsonObject("mc");
                }

                if (mcPayload != null) {
                    // 在主线程执行MC命令
                    JsonObject finalMcPayload = mcPayload;
                    Bukkit.getScheduler().runTask(plugin, () -> {
                        if (finalMcPayload.has("give_item") && !finalMcPayload.get("give_item").isJsonNull()
                                && finalMcPayload.has("map_image") && !finalMcPayload.get("map_image").isJsonNull()) {
                            String itemType = finalMcPayload.get("give_item").getAsString();
                            String base64Image = finalMcPayload.get("map_image").getAsString();
                            if ("filled_map".equalsIgnoreCase(itemType)) {
                                org.bukkit.Material mapMat = org.bukkit.Material.FILLED_MAP;
                                org.bukkit.inventory.ItemStack mapItem = new org.bukkit.inventory.ItemStack(mapMat);
                                org.bukkit.inventory.meta.MapMeta mapMeta = (org.bukkit.inventory.meta.MapMeta) mapItem
                                        .getItemMeta();
                                if (mapMeta != null) {
                                    mapMeta.displayName(net.kyori.adventure.text.Component.text("心悦小地图"));
                                    try {
                                        byte[] imgBytes = java.util.Base64.getDecoder().decode(base64Image);
                                        java.awt.image.BufferedImage img = javax.imageio.ImageIO
                                                .read(new java.io.ByteArrayInputStream(imgBytes));
                                        org.bukkit.map.MapView mapView = Bukkit.createMap(fp.getWorld());
                                        mapView.getRenderers().clear();
                                        mapView.addRenderer(new com.driftmc.minimap.PNGMapRenderer(img));
                                        mapMeta.setMapView(mapView);
                                    } catch (Exception e) {
                                        plugin.getLogger().warning("[小地图PNG] 渲染失败: " + e.getMessage());
                                    }
                                    mapItem.setItemMeta(mapMeta);
                                }
                                fp.getInventory().addItem(mapItem);
                            }
                        }
                        if (finalMcPayload.has("tell")) {
                            String msg = finalMcPayload.get("tell").getAsString();
                            fp.sendMessage("§e" + msg);
                        }
                    });
                }

                plugin.getLogger().info("[小地图PNG] 已发送给玩家: " + fp.getName());
            }
        });

        p.sendMessage("§b-------------------");
    }

    // ============================================================
    // —— 修复后的剧情推进代码（最关键） ——
    // ============================================================
    private void pushToStoryEngine(Player p, String text) {

        final Player fp = p;
        final String ftext = (text == null ? "" : text); // ← 彻底防止 null

        if (isLikelyBlockPlacement(ftext)) {
            plugin.getLogger().warning("[剧情推进] 拦截造物请求，跳过故事引擎: " + ftext);
            if (p != null) {
                p.sendMessage("§c[造物] 该请求已转交造物执行器，等待执行日志。");
            }
            return;
        }

        plugin.getLogger().info("[剧情推进] 玩家: " + fp.getName() + ", 文本: " + ftext);

        forwardToNarrativeIngestion(fp, ftext);

        // 不再使用 Map.of() —— 改为 HashMap 全兼容安全版
        Map<String, Object> body = new HashMap<>();
        body.put("player_id", fp.getName());

        Map<String, Object> action = new HashMap<>();
        action.put("say", ftext);
        body.put("action", action);

        body.put("world_state", new HashMap<>()); // 空但安全的 map

        backend.postJsonAsync("/world/apply", GSON.toJson(body), new Callback() {

            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().warning("[剧情推进] 请求失败: " + e.getMessage());
                Bukkit.getScheduler().runTask(plugin,
                        () -> fp.sendMessage("§c[剧情错误] " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response resp) throws IOException {

                final String respStr = resp.body() != null ? resp.body().string() : "{}";
                plugin.getLogger().info("[剧情推进] 收到响应: " + respStr.substring(0, Math.min(200, respStr.length())));

                final JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

                final JsonObject node = (root.has("story_node") && root.get("story_node").isJsonObject())
                        ? root.get("story_node").getAsJsonObject()
                        : null;

                final JsonObject wpatch = (root.has("world_patch") && root.get("world_patch").isJsonObject())
                        ? root.get("world_patch").getAsJsonObject()
                        : null;

                final JsonObject creationPayload = (root.has("creation_result")
                    && root.get("creation_result").isJsonObject())
                        ? root.get("creation_result").getAsJsonObject()
                        : null;

                Bukkit.getScheduler().runTask(plugin, () -> {

                    if (node != null) {
                        String nodeType = node.has("type") ? node.get("type").getAsString() : "";
                        if ("npc_dialogue".equalsIgnoreCase(nodeType) && dialoguePanel != null) {
                            dialoguePanel.showDialogue(fp, node);
                        } else if ("story_choice".equalsIgnoreCase(nodeType) && choicePanel != null) {
                            choicePanel.presentChoiceNode(fp, node);
                        } else {
                            if (node.has("title")) {
                                String title = node.get("title").getAsString();
                                fp.sendMessage("§d【" + title + "】");
                                plugin.getLogger().info("[剧情推进] 显示标题: " + title);
                            }

                            if (node.has("text")) {
                                String storyText = node.get("text").getAsString();
                                fp.sendMessage("§f" + storyText);
                                plugin.getLogger()
                                        .info("[剧情推进] 显示文本: "
                                                + storyText.substring(0, Math.min(50, storyText.length())));
                            }
                        }
                    } else {
                        plugin.getLogger().warning("[剧情推进] story_node 为空");
                    }

                    if (wpatch != null && wpatch.size() > 0) {
                        plugin.getLogger().info("[剧情推进] 执行世界patch");
                        Map<String, Object> patch = GSON.fromJson(wpatch, MAP_TYPE);
                        syncTutorialState(fp, patch);
                        world.execute(fp, patch);
                    }

                    if (creationPayload != null && creationPayload.size() > 0) {
                        displayCreationResult(fp, creationPayload);
                    }
                });
            }
        });
    }

    private void forwardToNarrativeIngestion(Player player, String text) {
        if (text == null) {
            return;
        }
        String trimmed = text.trim();
        if (trimmed.isEmpty()) {
            return;
        }

        if (isLikelyBlockPlacement(trimmed)) {
            if (plugin.getLogger().isLoggable(Level.FINE)) {
                plugin.getLogger().fine("[CityPhone] 跳过方块指令采集: " + trimmed);
            }
            return;
        }

        Map<String, Object> payload = new HashMap<>();
        payload.put("player_id", player.getName());
        payload.put("message", trimmed);
        payload.put("channel", "storyline");

        String json = GSON.toJson(payload);
        UUID playerId = player.getUniqueId();

        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> backend.postJsonAsync("/ideal-city/narrative/ingest", json, new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                if (plugin.getLogger().isLoggable(Level.FINE)) {
                    plugin.getLogger().fine("[CityPhone] 叙事采集失败: " + e.getMessage());
                }
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                try (response) {
                    if (!response.isSuccessful()) {
                        if (plugin.getLogger().isLoggable(Level.FINE)) {
                            plugin.getLogger().fine("[CityPhone] 叙事采集返回 HTTP " + response.code());
                        }
                        return;
                    }
                    ResponseBody responseBody = response.body();
                    if (responseBody == null) {
                        return;
                    }
                    String body = responseBody.string();
                    if (body.isEmpty()) {
                        return;
                    }
                    JsonObject root;
                    try {
                        root = JsonParser.parseString(body).getAsJsonObject();
                    } catch (Exception parseError) {
                        if (plugin.getLogger().isLoggable(Level.FINE)) {
                            plugin.getLogger().fine("[CityPhone] 叙事采集解析失败: " + parseError.getMessage());
                        }
                        return;
                    }
                    String status = root.has("status") && !root.get("status").isJsonNull()
                            ? root.get("status").getAsString()
                            : "";
                    if (!"needs_review".equalsIgnoreCase(status) && !"accepted".equalsIgnoreCase(status)) {
                        return;
                    }

                    String serverMessage = root.has("message") && root.get("message").isJsonPrimitive()
                            ? root.get("message").getAsString()
                            : ("needs_review".equalsIgnoreCase(status) ? "解析为草稿，请在 CityPhone 补齐要素。" : "已自动提交裁决。");

                    String missingSummary = null;
                    if (root.has("missing_fields") && root.get("missing_fields").isJsonArray()) {
                        JsonArray arr = root.getAsJsonArray("missing_fields");
                        if (arr.size() > 0) {
                            StringBuilder builder = new StringBuilder();
                            int limit = Math.min(arr.size(), 3);
                            for (int i = 0; i < limit; i++) {
                                if (i > 0) {
                                    builder.append("、");
                                }
                                builder.append(arr.get(i).getAsString());
                            }
                            if (arr.size() > limit) {
                                builder.append("…");
                            }
                            missingSummary = builder.toString();
                        }
                    }

                    String display = "§b[CityPhone] " + serverMessage;
                    if (missingSummary != null && !missingSummary.isEmpty()) {
                        display += " 待补: " + missingSummary;
                    }

                    String finalDisplay = display;
                    Bukkit.getScheduler().runTask(plugin, () -> {
                        Player target = Bukkit.getPlayer(playerId);
                        if (target != null) {
                            target.sendMessage(finalDisplay);
                        }
                    });
                }
            }
        }));
    }

    private boolean isLikelyBlockPlacement(String text) {
        String lower = text.toLowerCase(Locale.ROOT);
        if (!BLOCK_ID_PATTERN.matcher(lower).find()) {
            return false;
        }
        if (lower.contains("放置") || lower.contains("生成") || lower.contains("方块") || lower.contains("方塊")
                || lower.contains("block")) {
            return true;
        }
        return false;
    }

    private void displayCreationResult(Player player, JsonObject payload) {
        if (player == null || payload == null) {
            return;
        }

        String status = payload.has("status") && payload.get("status").isJsonPrimitive()
                ? payload.get("status").getAsString()
                : "";
        boolean autoExecute = payload.has("auto_execute") && payload.get("auto_execute").isJsonPrimitive()
                ? payload.get("auto_execute").getAsBoolean()
                : true;
        JsonObject report = payload.has("report") && payload.get("report").isJsonObject()
                ? payload.getAsJsonObject("report")
                : null;
        String patchId = "-";
        if (report != null && report.has("patch_id") && !report.get("patch_id").isJsonNull()) {
            patchId = report.get("patch_id").getAsString();
        }

        if ("error".equalsIgnoreCase(status)) {
            String errorMessage = payload.has("error") && payload.get("error").isJsonPrimitive()
                    ? payload.get("error").getAsString()
                    : "未知错误";
            player.sendMessage("§c[造物] 自动执行失败: " + errorMessage);
            return;
        }

        if ("dry_run".equalsIgnoreCase(status) || !autoExecute) {
            player.sendMessage("§e[造物] Dry-run 完成，patch " + patchId + " 已记录，等待确认。");
        } else {
            int executed = 0;
            if (report != null && report.has("execution_results") && report.get("execution_results").isJsonArray()) {
                executed = report.getAsJsonArray("execution_results").size();
            }
            player.sendMessage("§a[造物] patch " + patchId + " 自动执行完成，模板数: " + executed + "。");
        }

        if (report != null) {
            emitCreationList(player, report, "warnings", "§e", "告警");
            emitCreationList(player, report, "errors", "§c", "提醒");
        }
    }

    private void emitCreationList(Player player, JsonObject report, String key, String colorCode, String label) {
        if (!report.has(key) || !report.get(key).isJsonArray()) {
            return;
        }
        JsonArray arr = report.getAsJsonArray(key);
        if (arr.size() == 0) {
            return;
        }
        StringBuilder msg = new StringBuilder(colorCode).append("[造物").append(label).append("] ");
        int limit = Math.min(arr.size(), 3);
        for (int i = 0; i < limit; i++) {
            if (i > 0) {
                msg.append("；");
            }
            msg.append(arr.get(i).getAsString());
        }
        if (arr.size() > limit) {
            msg.append(" …");
        }
        player.sendMessage(msg.toString());
    }

    // ============================================================
    // 跳关（传送 + 加载剧情）
    // ============================================================
    private void gotoLevelAndLoad(Player p, IntentResponse2 intent) {

        final Player fp = p;
        final String levelId = LevelIds.canonicalizeOrDefault(resolveRequestedLevel(fp, intent));
        final JsonObject minimap = intent.minimap;

        if (!ensureUnlocked(fp, TutorialState.JUMP_LEVEL, "完成关卡跳转教学后即可自由跳关。")) {
            return;
        }

        if (levelId == null) {
            p.sendMessage("§c跳关失败：没有 levelId");
            return;
        }

        if (minimap == null || !minimap.has("nodes")) {
            p.sendMessage("§c跳关失败：minimap 缺失");
            return;
        }

        JsonArray nodes = minimap.getAsJsonArray("nodes");

        int tx = 0, tz = 0;
        boolean found = false;

        for (int i = 0; i < nodes.size(); i++) {
            JsonObject n = nodes.get(i).getAsJsonObject();
            if (LevelIds.canonicalizeLevelId(n.get("level").getAsString()).equals(levelId)) {
                JsonObject pos = n.getAsJsonObject("pos");
                tx = pos.get("x").getAsInt();
                tz = pos.get("y").getAsInt();
                found = true;
                break;
            }
        }

        if (!found) {
            p.sendMessage("§c跳关失败：地图中不存在 " + levelId);
            return;
        }

        final int fx = tx;
        final int fy = 80;
        final int fz = tz;

        Bukkit.getScheduler().runTask(plugin, () -> fp.teleport(new Location(fp.getWorld(), fx, fy, fz)));

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

                        final JsonObject patchObj = (root.has("bootstrap_patch")
                                && root.get("bootstrap_patch").isJsonObject())
                                        ? root.getAsJsonObject("bootstrap_patch")
                                        : null;

                        if (patchObj != null) {
                            final Map<String, Object> patch = GSON.fromJson(patchObj, MAP_TYPE);

                            Bukkit.getScheduler().runTask(plugin, () -> {
                                syncTutorialState(fp, patch);
                                world.execute(fp, patch);
                                if (questLogHud != null) {
                                    questLogHud.showQuestLog(fp, QuestLogHud.Trigger.LEVEL_ENTER);
                                }
                            });
                        } else if (questLogHud != null) {
                            Bukkit.getScheduler().runTask(plugin,
                                    () -> questLogHud.showQuestLog(fp, QuestLogHud.Trigger.LEVEL_ENTER));
                        }
                    }
                });
    }

    private String resolveRequestedLevel(Player player, IntentResponse2 intent) {
        if (intent == null) {
            return null;
        }
        return enforceTutorialExitRedirect(player, intent.levelId, intent.rawText);
    }

    private String enforceTutorialExitRedirect(Player player, String requestedLevelId, String rawText) {
        String canonicalRequested = LevelIds.canonicalizeLevelId(requestedLevelId);
        if (tutorialManager == null || player == null) {
            return canonicalRequested;
        }

        if (!tutorialManager.hasExitedTutorial(player)) {
            return canonicalRequested;
        }

        boolean requestTargetsTutorial = LevelIds.isFlagshipTutorial(canonicalRequested);
        String normalizedRaw = rawText != null ? rawText.toLowerCase(Locale.ROOT) : "";
        if (!normalizedRaw.isBlank()) {
            requestTargetsTutorial = requestTargetsTutorial
                    || normalizedRaw.contains("第一关")
                    || normalizedRaw.contains("主线")
                    || normalizedRaw.contains("开始");
        }

        if (requestTargetsTutorial) {
            warnTutorialReentry(player);
            return PRIMARY_LEVEL_ID;
        }

        return canonicalRequested;
    }

    private void warnTutorialReentry(Player player) {
        if (player == null) {
            return;
        }
        UUID playerId = player.getUniqueId();
        if (tutorialReentryWarned.add(playerId)) {
            plugin.getLogger().warning("[LevelResolve] Blocked tutorial re-entry for " + player.getName());
        }
    }
}