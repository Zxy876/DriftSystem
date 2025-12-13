package com.driftmc.tutorial;

import java.io.IOException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.boss.BarColor;
import org.bukkit.boss.BarStyle;
import org.bukkit.boss.BossBar;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.session.PlayerSessionManager;
import com.driftmc.session.PlayerSessionManager.Mode;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

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

  // 追踪正在教学中的玩家
  private final Set<UUID> playersInTutorial;

  // Boss Bar 进度显示
  private final Map<UUID, BossBar> tutorialBossBars;

  // 教学步骤名称映射
  private static final Map<String, String> STEP_NAMES = new HashMap<>();
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
    this.playersInTutorial = new HashSet<>();
    this.tutorialBossBars = new HashMap<>();
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
    } else {
      // 教学完成
      completeTutorial(player);
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
   * 完成教学
   */
  private void completeTutorial(Player player) {
    UUID uuid = player.getUniqueId();
    playersInTutorial.remove(uuid);

    // 移除Boss Bar
    BossBar bar = tutorialBossBars.remove(uuid);
    if (bar != null) {
      bar.removePlayer(player);
    }

    // 显示完成消息
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
    player.sendMessage("§f开始你的心悦之旅吧！");
    player.sendMessage("§6§l━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    plugin.getLogger().info("[教学] 玩家 " + player.getName() + " 完成教学");

    if (sessions != null) {
      sessions.markTutorialComplete(player);
      player.sendActionBar(net.kyori.adventure.text.Component.text("教程完成，已进入正式剧情", net.kyori.adventure.text.format.NamedTextColor.GOLD));
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
            completeTutorial(player);
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

    if (sessions != null && !sessions.hasCompletedTutorial(player)) {
      sessions.setMode(player, Mode.NORMAL);
    }
  }
}
