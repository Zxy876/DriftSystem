package com.driftmc.tutorial;

import java.io.IOException;
import java.lang.reflect.Type;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.boss.BarColor;
import org.bukkit.boss.BarStyle;
import org.bukkit.boss.BossBar;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.scene.RuleEventBridge;
import com.driftmc.scene.SceneAwareWorldPatchExecutor;
import com.driftmc.scene.SceneLoader;
import com.driftmc.session.PlayerSessionManager;
import com.driftmc.session.PlayerSessionManager.Mode;
import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

/**
 * 教学系统管理器 - 与后端 /tutorial API 交互
 */
public class TutorialManager {

  private final Plugin plugin;
  private final BackendClient backend;
  private final Gson gson;
  private final PlayerSessionManager sessions;
  private final TutorialStateMachine stateMachine;

  // 追踪正在教学中的玩家
  private final Set<UUID> playersInTutorial;
  private final Set<UUID> completionEmittedPlayers;
  private final Set<UUID> finalizedPlayers;
  private final Set<UUID> tutorialExitPlayers;

  // Boss Bar 进度显示
  private final Map<UUID, BossBar> tutorialBossBars;

  // 教学步骤名称映射
  private static final Map<String, String> STEP_NAMES = new HashMap<>();
  private static final String TUTORIAL_LEVEL_ID = "flagship_tutorial";
  private static final String FIRST_PRIMARY_LEVEL_ID = "flagship_03";
  private static final Type MAP_TYPE = new TypeToken<Map<String, Object>>() {
  }.getType();
  static {
    STEP_NAMES.put("WELCOME", "欢迎");
    STEP_NAMES.put("DIALOGUE", "对话交流");
    STEP_NAMES.put("CREATE_STORY", "创造剧情");
    STEP_NAMES.put("CONTINUE_STORY", "推进剧情");
    STEP_NAMES.put("JUMP_LEVEL", "关卡跳转");
    STEP_NAMES.put("NPC_INTERACT", "NPC互动");
    STEP_NAMES.put("VIEW_MAP", "查看地图");
    STEP_NAMES.put("COMPLETE", "完成");
  }

  public TutorialManager(Plugin plugin, BackendClient backend, PlayerSessionManager sessions) {
    this.plugin = plugin;
    this.backend = backend;
    this.gson = new Gson();
    this.sessions = sessions;
    this.stateMachine = new TutorialStateMachine(plugin, sessions);
    this.completionEmittedPlayers = ConcurrentHashMap.newKeySet();
    this.finalizedPlayers = ConcurrentHashMap.newKeySet();
    this.playersInTutorial = ConcurrentHashMap.newKeySet();
    this.tutorialExitPlayers = ConcurrentHashMap.newKeySet();
    this.tutorialBossBars = new HashMap<>();
  }

  private SceneLoader sceneLoader;
  private SceneAwareWorldPatchExecutor worldPatcher;
  private RuleEventBridge ruleEventBridge;

  public void attachSceneLoader(SceneLoader loader) {
    this.sceneLoader = loader;
  }

  public void attachWorldPatcher(SceneAwareWorldPatchExecutor patcher) {
    this.worldPatcher = patcher;
  }

  public void attachRuleEventBridge(RuleEventBridge bridge) {
    this.ruleEventBridge = bridge;
  }

  public TutorialStateMachine getStateMachine() {
    return stateMachine;
  }

  public boolean isTutorialComplete(Player player) {
    return isTutorialFinalized(player);
  }

  public boolean isTutorialFinalized(Player player) {
    if (player == null) {
      return false;
    }
    UUID playerId = player.getUniqueId();
    if (finalizedPlayers.contains(playerId)) {
      return true;
    }
    return sessions != null && sessions.hasCompletedTutorial(player);
  }

  public boolean hasExitedTutorialPhase(Player player) {
    if (player == null) {
      return false;
    }
    UUID playerId = player.getUniqueId();
    if (tutorialExitPlayers.contains(playerId)) {
      return true;
    }
    if (sessions != null && sessions.hasExitedTutorial(player)) {
      tutorialExitPlayers.add(playerId);
      return true;
    }
    return false;
  }

  public boolean hasExitedTutorial(Player player) {
    return hasExitedTutorialPhase(player);
  }

  public boolean hasExitedTutorial(UUID playerId) {
    if (playerId == null) {
      return false;
    }
    if (tutorialExitPlayers.contains(playerId)) {
      return true;
    }
    if (sessions != null && sessions.hasExitedTutorial(playerId)) {
      tutorialExitPlayers.add(playerId);
      return true;
    }
    return false;
  }

  public boolean hasCompletionEmitted(Player player) {
    if (player == null) {
      return false;
    }
    UUID playerId = player.getUniqueId();
    if (completionEmittedPlayers.contains(playerId)) {
      return true;
    }
    return sessions != null && sessions.hasTutorialCompletionSignal(player);
  }

  public boolean isInTutorial(Player player) {
    if (player == null) {
      return false;
    }
    if (hasExitedTutorialPhase(player)) {
      return false;
    }
    if (isTutorialFinalized(player)) {
      return false;
    }
    UUID playerId = player.getUniqueId();
    if (playersInTutorial.contains(playerId)) {
      return true;
    }
    if (sessions != null && sessions.isTutorial(player)) {
      return true;
    }
    TutorialState state = stateMachine.getState(player);
    return state != null && state != TutorialState.INACTIVE && state != TutorialState.COMPLETE;
  }

  public boolean markCompletionEmitted(Player player) {
    if (player == null) {
      return false;
    }
    UUID playerId = player.getUniqueId();
    boolean firstEmission = completionEmittedPlayers.add(playerId);
    if (sessions != null) {
      sessions.markTutorialCompletionSignal(player);
    }
    if (firstEmission) {
      plugin.getLogger().log(Level.INFO, "[TutorialComplete] emitted for {0}", player.getName());
    }
    return firstEmission;
  }

  private void markTutorialExit(Player player) {
    if (player == null) {
      return;
    }
    UUID playerId = player.getUniqueId();
    tutorialExitPlayers.add(playerId);
    if (sessions != null) {
      sessions.markTutorialExited(player);
    }
  }

  /**
   * 检查玩家是否是新玩家（从未玩过）
   */
  public boolean isNewPlayer(Player player) {
    // 检查玩家的统计数据 - 如果游戏时间为0则是新玩家
    return player.getStatistic(org.bukkit.Statistic.PLAY_ONE_MINUTE) < 1200; // 小于1分钟
  }

  /**
   * 为新玩家启动教学
   */
  public void startTutorial(Player player) {
    final UUID uuid = player.getUniqueId();

    if (playersInTutorial.contains(uuid)) {
      plugin.getLogger().info("[教学] 玩家 " + player.getName() + " 已在教学中");
      return;
    }

    completionEmittedPlayers.remove(uuid);
    finalizedPlayers.remove(uuid);
    tutorialExitPlayers.remove(uuid);
    if (sessions != null) {
      sessions.clearTutorialCompletionSignal(player);
      sessions.clearTutorialExit(player);
    }

    if (sessions != null && sessions.hasCompletedTutorial(player)) {
      player.sendMessage("§e你已经完成教程，正在为你保持主线入口开启。");
      return;
    }

    plugin.getLogger().info("[教学] 为玩家 " + player.getName() + " 启动新手教学");

    if (sessions != null) {
      sessions.markTutorialStarted(player);
    }

    backend.postJsonAsync("/tutorial/start/" + player.getName(), "{}", new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        plugin.getLogger().warning("[教学启动失败] " + e.getMessage());
      }

      @Override
      public void onResponse(Call call, Response resp) throws IOException {
        try (resp) {
          String respStr = resp.body() != null ? resp.body().string() : "{}";
          JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

          Bukkit.getScheduler().runTask(plugin, () -> {
            if (root.has("status") && "started".equals(root.get("status").getAsString())) {
              playersInTutorial.add(uuid);

              // 显示欢迎消息
              JsonObject tutorial = root.has("tutorial") ? root.getAsJsonObject("tutorial") : null;

              if (tutorial != null) {
                String title = tutorial.has("title") ? tutorial.get("title").getAsString() : "新手教学";
                String instruction = tutorial.has("instruction") ? tutorial.get("instruction").getAsString() : "";

                player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                player.sendMessage("§e✨ §6§l" + title);
                player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                player.sendMessage("");
                player.sendMessage("§f" + instruction);
                player.sendMessage("");
                player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");

                // 创建进度条
                createBossBar(player, "WELCOME", 0, 7);
              }

              plugin.getLogger().info("[教学] 玩家 " + player.getName() + " 教学已启动");
              stateMachine.start(player);
            }
          });
        }
      }
    });
  }

  /**
   * 检查玩家的消息是否推进了教学
   */
  public void checkProgress(Player player, String message) {
    final UUID uuid = player.getUniqueId();

    if (isTutorialComplete(player)) {
      return;
    }

    if (!playersInTutorial.contains(uuid)) {
      return; // 不在教学中
    }

    Map<String, Object> body = new HashMap<>();
    body.put("player_id", player.getName());
    body.put("message", message);

    String jsonBody = gson.toJson(body);

    backend.postJsonAsync("/tutorial/check", jsonBody, new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        plugin.getLogger().warning("[教学检查失败] " + e.getMessage());
      }

      @Override
      public void onResponse(Call call, Response resp) throws IOException {
        try (resp) {
          String respStr = resp.body() != null ? resp.body().string() : "{}";
          JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

          Bukkit.getScheduler().runTask(plugin, () -> {
            if (root.has("completed") && root.get("completed").getAsBoolean()) {
              JsonObject result = root.has("result") ? root.getAsJsonObject("result") : null;

              if (result != null) {
                handleStepCompletion(player, result);
              }
            }
          });
        }
      }
    });
  }

  /**
   * 处理教学步骤完成
   */
  private void handleStepCompletion(Player player, JsonObject result) {
    String successMsg = result.has("success_message") ? result.get("success_message").getAsString() : "完成！";

    // 显示成功消息
    player.sendMessage("");
    player.sendMessage("§a§l✔ " + successMsg);

    // 执行奖励命令
    if (result.has("mc_commands")) {
      JsonObject commands = result.getAsJsonObject("mc_commands");
      executeRewardCommands(player, commands);
    }

    // 检查下一步
    if (result.has("next_step")) {
      JsonObject nextStep = result.getAsJsonObject("next_step");
      String stepName = nextStep.has("step") ? nextStep.get("step").getAsString() : "";
      String title = nextStep.has("title") ? nextStep.get("title").getAsString() : "";
      String instruction = nextStep.has("instruction") ? nextStep.get("instruction").getAsString() : "";
      int stepNum = nextStep.has("step_number") ? nextStep.get("step_number").getAsInt() : 0;

      // 更新Boss Bar
      updateBossBar(player, stepName, stepNum, 7);

      // 显示下一步指引
      player.sendMessage("");
      player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      player.sendMessage("§e✨ §6§l" + title);
      player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      player.sendMessage("");
      player.sendMessage("§f" + instruction);
      player.sendMessage("");
      player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");

      TutorialState completedState = extractState(result.get("step"));
      TutorialState nextState = extractState(nextStep.get("step"));
      if (nextState == null) {
        nextState = extractState(nextStep.get("id"));
      }
      if (nextState == null) {
        nextState = extractState(nextStep.get("name"));
      }
      stateMachine.handleStepResult(player, completedState, nextState);
    } else {
      // 教学完成
      TutorialState completedState = extractState(result.get("step"));
      stateMachine.handleStepResult(player, completedState, null);
      markCompletionEmitted(player);
    }
  }

  /**
   * 执行奖励命令
   */
  private void executeRewardCommands(Player player, JsonObject commands) {
    if (commands.has("experience")) {
      int exp = commands.get("experience").getAsInt();
      player.giveExp(exp);
      player.sendMessage("§a  + " + exp + " 经验值");
    }

    if (commands.has("effects")) {
      for (var effect : commands.getAsJsonArray("effects")) {
        String effectCmd = effect.getAsString();
        Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
            effectCmd.replace("{player}", player.getName()));
      }
    }

    if (commands.has("items")) {
      for (var item : commands.getAsJsonArray("items")) {
        String itemCmd = item.getAsString();
        Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
            itemCmd.replace("{player}", player.getName()));

        // 解析物品名称显示
        String itemName = parseItemName(itemCmd);
        player.sendMessage("§a  + " + itemName);
      }
    }
  }

  /**
   * 解析物品命令获取物品名称
   */
  private String parseItemName(String command) {
    if (command.contains("diamond"))
      return "钻石";
    if (command.contains("golden_apple"))
      return "金苹果";
    if (command.contains("book"))
      return "书";
    return "物品";
  }

  /**
   * 创建教学进度 Boss Bar
   */
  private void createBossBar(Player player, String stepName, int current, int total) {
    UUID uuid = player.getUniqueId();

    // 移除旧的
    BossBar oldBar = tutorialBossBars.remove(uuid);
    if (oldBar != null) {
      oldBar.removePlayer(player);
    }

    // 创建新的
    String displayName = STEP_NAMES.getOrDefault(stepName, stepName);
    String title = String.format("§6新手教学 §f[%d/7] §e%s", current + 1, displayName);

    BossBar bar = Bukkit.createBossBar(
        title,
        BarColor.YELLOW,
        BarStyle.SEGMENTED_10);

    bar.setProgress(Math.min(1.0, (current + 1) / 7.0));
    bar.addPlayer(player);

    tutorialBossBars.put(uuid, bar);
  }

  /**
   * 更新教学进度 Boss Bar
   */
  private void updateBossBar(Player player, String stepName, int current, int total) {
    UUID uuid = player.getUniqueId();
    BossBar bar = tutorialBossBars.get(uuid);

    if (bar != null) {
      String displayName = STEP_NAMES.getOrDefault(stepName, stepName);
      String title = String.format("§6新手教学 §f[%d/7] §e%s", current + 1, displayName);
      bar.setTitle(title);
      bar.setProgress(Math.min(1.0, (current + 1) / 7.0));
    } else {
      createBossBar(player, stepName, current, total);
    }
  }

  /**
   * 获取教学提示
   */
  public void getHint(Player player) {
    UUID uuid = player.getUniqueId();

    if (!playersInTutorial.contains(uuid)) {
      player.sendMessage("§c你当前不在教学中");
      return;
    }

    backend.postJsonAsync("/tutorial/hint/" + player.getName(), "{}", new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        player.sendMessage("§c获取提示失败");
      }

      @Override
      public void onResponse(Call call, Response resp) throws IOException {
        try (resp) {
          String respStr = resp.body() != null ? resp.body().string() : "{}";
          JsonObject root = JsonParser.parseString(respStr).getAsJsonObject();

          Bukkit.getScheduler().runTask(plugin, () -> {
            if (root.has("hint")) {
              String hint = root.get("hint").getAsString();
              player.sendMessage("§e💡 提示：§f" + hint);
            }
          });
        }
      }
    });
  }

  /**
   * 跳过教学
   */
  public void skipTutorial(Player player) {
    UUID uuid = player.getUniqueId();

    if (!playersInTutorial.contains(uuid)) {
      player.sendMessage("§c你当前不在教学中");
      return;
    }

    backend.postJsonAsync("/tutorial/skip/" + player.getName(), "{}", new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        player.sendMessage("§c跳过教学失败");
      }

      @Override
      public void onResponse(Call call, Response resp) throws IOException {
        try (resp) {
          Bukkit.getScheduler().runTask(plugin, () -> {
            markCompletionEmitted(player);
            finalizeTutorial(player);
            player.sendMessage("§e已跳过教学");
          });
        }
      }
    });
  }

  /**
   * 玩家离开时清理
   */
  public void cleanupPlayer(Player player) {
    UUID uuid = player.getUniqueId();
    playersInTutorial.remove(uuid);

    BossBar bar = tutorialBossBars.remove(uuid);
    if (bar != null) {
      bar.removePlayer(player);
    }

    if (!isTutorialFinalized(player)) {
      completionEmittedPlayers.remove(uuid);
      if (sessions != null) {
        sessions.clearTutorialCompletionSignal(player);
      }
    }

    if (sessions != null && !sessions.hasCompletedTutorial(player)) {
      sessions.setMode(player, Mode.NORMAL);
    }
    stateMachine.reset(player);
  }

  public boolean ensureUnlocked(Player player, TutorialState required, String message) {
    return stateMachine.ensureUnlocked(player, required, message);
  }

  public boolean ensureUnlocked(Player player, TutorialState required) {
    return stateMachine.ensureUnlocked(player, required, null);
  }

  public void syncWorldPatch(Player player, Map<String, Object> patch) {
    if (player == null || patch == null || patch.isEmpty()) {
      return;
    }
    if (isTutorialFinalized(player)) {
      return;
    }
    stateMachine.syncFromPatch(player, patch);
    if (stateMachine.getState(player) == TutorialState.COMPLETE) {
      markCompletionEmitted(player);
    }
  }

  private TutorialState extractState(JsonElement element) {
    if (element == null || element.isJsonNull()) {
      return null;
    }
    if (element.isJsonPrimitive()) {
      if (element.getAsJsonPrimitive().isNumber()) {
        return TutorialState.fromObject(element.getAsNumber());
      }
      if (element.getAsJsonPrimitive().isString()) {
        return TutorialState.fromString(element.getAsString());
      }
    }
    if (element.isJsonObject()) {
      JsonObject obj = element.getAsJsonObject();
      if (obj.has("step")) {
        TutorialState state = extractState(obj.get("step"));
        if (state != null) {
          return state;
        }
      }
      if (obj.has("id")) {
        TutorialState state = extractState(obj.get("id"));
        if (state != null) {
          return state;
        }
      }
      if (obj.has("name")) {
        TutorialState state = extractState(obj.get("name"));
        if (state != null) {
          return state;
        }
      }
      if (obj.has("state")) {
        TutorialState state = extractState(obj.get("state"));
        if (state != null) {
          return state;
        }
      }
    }
    return null;
  }

  public boolean finalizeTutorial(Player player) {
    if (player == null) {
      return false;
    }
    markCompletionEmitted(player);
    UUID playerId = player.getUniqueId();
    if (isTutorialFinalized(player)) {
      finalizedPlayers.add(playerId);
      playersInTutorial.remove(playerId);
      BossBar existing = tutorialBossBars.remove(playerId);
      if (existing != null) {
        existing.removePlayer(player);
      }
      markTutorialExit(player);
      return false;
    }
    if (!finalizedPlayers.add(playerId)) {
      return false;
    }

    boolean success = false;
    try {
      playersInTutorial.remove(playerId);
      BossBar bar = tutorialBossBars.remove(playerId);
      if (bar != null) {
        bar.removePlayer(player);
      }

      // 1. 持久化标记教程完成
      if (sessions != null) {
        sessions.setTutorial(player, false);
        sessions.markTutorialComplete(player);
      }
      stateMachine.markCompleted(player);

      // 3. 结束教学场景
      if (sceneLoader != null) {
        String activeScene = sceneLoader.getActiveSceneId(player);
        if (activeScene != null && activeScene.equalsIgnoreCase(TUTORIAL_LEVEL_ID)) {
          sceneLoader.endSession(player, "tutorial_complete");
        }
      }

      if (worldPatcher != null) {
        worldPatcher.execute(player, buildTutorialCleanupPatch());
      }

      if (ruleEventBridge != null) {
        ruleEventBridge.handleTutorialFinalize(player);
      }

      announceTutorialCompletion(player);

      plugin.getLogger().log(Level.INFO, "[TutorialExit] finalized for {0}", player.getName());

      success = true;
      markTutorialExit(player);
      return true;
    } finally {
      launchPrimaryStory(player);
      if (!success) {
        finalizedPlayers.remove(playerId);
      }
    }
  }

  private Map<String, Object> buildTutorialCleanupPatch() {
    Map<String, Object> cleanup = new LinkedHashMap<>();
    cleanup.put("id", "tutorial_finalize_cleanup");
    cleanup.put("scene_id", TUTORIAL_LEVEL_ID);

    Map<String, Object> mcPayload = new LinkedHashMap<>();
    mcPayload.put("_scene_cleanup", cleanup);

    Map<String, Object> patch = new LinkedHashMap<>();
    patch.put("mc", mcPayload);
    return patch;
  }

  private void launchPrimaryStory(Player player) {
    if (player == null || backend == null) {
      return;
    }

    if (worldPatcher == null) {
      return;
    }

    String playerName = player.getName();
    plugin.getLogger().log(Level.INFO, "[TutorialExit] loading flagship_03 for {0}", playerName);
    backend.postJsonAsync("/story/load/" + playerName + "/" + FIRST_PRIMARY_LEVEL_ID, "{}", new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        plugin.getLogger()
            .warning("[TutorialExit] Failed to load first storyline for " + playerName + ": " + e.getMessage());
      }

      @Override
      public void onResponse(Call call, Response response) throws IOException {
        try (response) {
          String body = response.body() != null ? response.body().string() : "{}";
          JsonObject root = JsonParser.parseString(body).getAsJsonObject();

          JsonObject patchObj = null;
          if (root.has("bootstrap_patch") && root.get("bootstrap_patch").isJsonObject()) {
            patchObj = root.getAsJsonObject("bootstrap_patch");
          } else if (root.has("world_patch") && root.get("world_patch").isJsonObject()) {
            patchObj = root.getAsJsonObject("world_patch");
          }

          Map<String, Object> patch = null;
          if (patchObj != null && patchObj.size() > 0) {
            patch = gson.fromJson(patchObj, MAP_TYPE);
          }

          Map<String, Object> finalPatch = patch;
          Bukkit.getScheduler().runTask(plugin, () -> {
            if (!player.isOnline()) {
              return;
            }
            markTutorialExit(player);
            if (finalPatch != null && !finalPatch.isEmpty()) {
              worldPatcher.execute(player, finalPatch);
            }
          });
        } catch (Exception ex) {
          plugin.getLogger().warning(
              "[TutorialExit] Unable to parse flagship load response for " + playerName + ": " + ex.getMessage());
        }
      }
    });
  }

  private void announceTutorialCompletion(Player player) {
    if (player == null) {
      return;
    }

    player.sendMessage("");
    player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    player.sendMessage("§e✨ §6§l恭喜完成新手教学！");
    player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    player.sendMessage("");
    player.sendMessage("§f现在你已经掌握了所有核心功能：");
    player.sendMessage("§a  ✓ 与NPC对话");
    player.sendMessage("§a  ✓ 创造和推进剧情");
    player.sendMessage("§a  ✓ 在关卡间跳转");
    player.sendMessage("§a  ✓ 查看地图导航");
    player.sendMessage("");
    player.sendMessage("§e教程完成，已进入正式剧情。");
    player.sendMessage("§f开始你的心悦之旅吧！");
    player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    if (sessions != null) {
      player.sendActionBar(
          net.kyori.adventure.text.Component.text("教程完成，已进入正式剧情", net.kyori.adventure.text.format.NamedTextColor.GOLD));
    }
  }
}
