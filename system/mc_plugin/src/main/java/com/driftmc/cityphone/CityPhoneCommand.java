package com.driftmc.cityphone;

import java.util.Arrays;

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
      sender.sendMessage(CityPhoneLocalization.component("command.player_only", NamedTextColor.RED));
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
          player.sendMessage(CityPhoneLocalization.component("command.say_missing", NamedTextColor.RED));
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
    player.sendMessage(CityPhoneLocalization.component("command.header", NamedTextColor.AQUA));
    player.sendMessage(CityPhoneLocalization.component("command.give", NamedTextColor.WHITE));
    player.sendMessage(CityPhoneLocalization.component("command.open", NamedTextColor.WHITE));
    player.sendMessage(CityPhoneLocalization.component("command.say", NamedTextColor.WHITE));
    player.sendMessage(CityPhoneLocalization.component("command.pose", NamedTextColor.WHITE));
    player.sendMessage(CityPhoneLocalization.component("command.history_hint", NamedTextColor.GRAY));
  }
}
