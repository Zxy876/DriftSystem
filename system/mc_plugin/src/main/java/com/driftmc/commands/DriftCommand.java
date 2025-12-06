package com.driftmc.commands;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import com.driftmc.backend.BackendClient;
import com.driftmc.story.StoryManager;
import com.driftmc.tutorial.TutorialManager;
import com.driftmc.world.WorldPatchExecutor;

/**
 * DriftCommand - 主命令处理器
 * 
 * 提供手动命令接口（虽然主要是自然语言驱动）
 * 
 * 命令:
 * /drift status - 查看当前状态
 * /drift sync - 同步剧情状态
 * /drift debug - 调试信息
 * /drift tutorial - 教学系统相关命令
 */
public class DriftCommand implements CommandExecutor {

  private final BackendClient backend;
  private final StoryManager storyManager;
  private final WorldPatchExecutor worldPatcher;
  private final TutorialManager tutorialManager;

  public DriftCommand(
      BackendClient backend,
      StoryManager storyManager,
      WorldPatchExecutor worldPatcher,
      TutorialManager tutorialManager) {
    this.backend = backend;
    this.storyManager = storyManager;
    this.worldPatcher = worldPatcher;
    this.tutorialManager = tutorialManager;
  }

  @Override
  public boolean onCommand(
      CommandSender sender,
      Command command,
      String label,
      String[] args) {
    if (!(sender instanceof Player)) {
      sender.sendMessage("§c只有玩家可以使用此命令");
      return true;
    }

    Player player = (Player) sender;

    if (args.length == 0) {
      showHelp(player);
      return true;
    }

    switch (args[0].toLowerCase()) {
      case "status":
        showStatus(player);
        break;

      case "sync":
        syncState(player);
        break;

      case "debug":
        showDebug(player);
        break;

      case "tutorial":
        handleTutorial(player, args);
        break;

      default:
        showHelp(player);
    }

    return true;
  }

  private void showHelp(Player player) {
    player.sendMessage("§b========== Drift System ==========");
    player.sendMessage("§7直接在聊天中说话即可与系统交互！");
    player.sendMessage("");
    player.sendMessage("§e手动命令:");
    player.sendMessage("  §f/drift status §7- 查看当前状态");
    player.sendMessage("  §f/drift sync §7- 同步剧情状态");
    player.sendMessage("  §f/drift debug §7- 显示调试信息");
    player.sendMessage("  §f/drift tutorial §7- 教学系统");
    player.sendMessage("    §f/drift tutorial start §7- 开始教学");
    player.sendMessage("    §f/drift tutorial hint §7- 获取提示");
    player.sendMessage("    §f/drift tutorial skip §7- 跳过教学");
    player.sendMessage("§b================================");
  }

  private void handleTutorial(Player player, String[] args) {
    if (args.length < 2) {
      player.sendMessage("§e教学命令:");
      player.sendMessage("  §f/drift tutorial start §7- 开始/重新开始教学");
      player.sendMessage("  §f/drift tutorial hint §7- 获取当前步骤提示");
      player.sendMessage("  §f/drift tutorial skip §7- 跳过教学");
      return;
    }

    switch (args[1].toLowerCase()) {
      case "start":
        tutorialManager.startTutorial(player);
        break;

      case "hint":
        tutorialManager.getHint(player);
        break;

      case "skip":
        player.sendMessage("§e确定要跳过教学吗？(输入 /drift tutorial skip confirm)");
        if (args.length >= 3 && "confirm".equalsIgnoreCase(args[2])) {
          tutorialManager.skipTutorial(player);
        }
        break;

      default:
        player.sendMessage("§c未知的教学命令");
    }
  }

  private void showStatus(Player player) {
    String level = storyManager.getCurrentLevel(player);
    StoryManager.StoryState state = storyManager.getState(player);

    player.sendMessage("§b========== 你的状态 ==========");
    player.sendMessage("§7当前关卡: §a" + level);
    player.sendMessage("§7节点索引: §e" + state.getNodeIndex());
    player.sendMessage("§7可推进: §" +
        (state.canAdvance() ? "a是" : "c否"));
    if (state.getLastChoice() != null) {
      player.sendMessage("§7上次选择: §d" + state.getLastChoice());
    }
    player.sendMessage("§b============================");
  }

  private void syncState(Player player) {
    player.sendMessage("§e正在同步剧情状态...");
    storyManager.syncState(player, () -> {
      player.sendMessage("§a同步完成！");
      showStatus(player);
    });
  }

  private void showDebug(Player player) {
    player.sendMessage("§b========== 调试信息 ==========");
    player.sendMessage("§7玩家: §f" + player.getName());
    player.sendMessage("§7UUID: §f" + player.getUniqueId());
    player.sendMessage("§7位置: §f" +
        String.format("%.1f, %.1f, %.1f",
            player.getLocation().getX(),
            player.getLocation().getY(),
            player.getLocation().getZ()));
    player.sendMessage("§7世界: §f" + player.getWorld().getName());
    player.sendMessage("§b============================");
  }
}
