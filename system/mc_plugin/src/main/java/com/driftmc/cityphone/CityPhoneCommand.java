package com.driftmc.cityphone;

import java.util.Arrays;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public final class CityPhoneCommand implements CommandExecutor {

  private final CityPhoneManager manager;

  public CityPhoneCommand(CityPhoneManager manager) {
    this.manager = manager;
  }

  @Override
  public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
    if (!(sender instanceof Player player)) {
      sender.sendMessage(Component.text("仅限玩家使用 CityPhone。", NamedTextColor.RED));
      return true;
    }
    if (args.length == 0) {
      sendUsage(player);
      return true;
    }
    String sub = args[0].toLowerCase();
    switch (sub) {
      case "give":
        manager.givePhone(player);
        return true;
      case "open":
        manager.openPhone(player);
        return true;
      case "say":
        if (args.length < 2) {
          player.sendMessage(Component.text("请提供叙述内容，如 /cityphone say 我想建造展台。", NamedTextColor.RED));
          return true;
        }
        String narrative = String.join(" ", Arrays.copyOfRange(args, 1, args.length));
        manager.submitNarrative(player, narrative);
        return true;
      case "pose":
        manager.submitPose(player);
        return true;
      default:
        sendUsage(player);
        return true;
    }
  }

  private void sendUsage(Player player) {
    player.sendMessage(Component.text("CityPhone 命令:", NamedTextColor.AQUA));
    player.sendMessage(Component.text("/cityphone give 领取终端", NamedTextColor.WHITE));
    player.sendMessage(Component.text("/cityphone open 打开界面", NamedTextColor.WHITE));
    player.sendMessage(Component.text("/cityphone say <内容> 提交叙述", NamedTextColor.WHITE));
    player.sendMessage(Component.text("/cityphone pose 同步当前位置", NamedTextColor.WHITE));
  }
}
