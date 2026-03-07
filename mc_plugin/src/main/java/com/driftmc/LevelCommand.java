package com.driftmc;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class LevelCommand implements CommandExecutor {
    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String lbl, String[] args) {

        if (!(sender instanceof Player)) {
            sender.sendMessage("玩家才能执行");
            return true;
        }

        if (args.length != 1) {
            sender.sendMessage("用法: /level level_1");
            return true;
        }

        Player p = (Player) sender;
        String level = args[0];

        String res = BackendClient.post("/story/load/" + p.getName() + "/" + level);
        p.sendMessage("§a加载关卡: " + level);
        p.sendMessage("§7后端响应: " + res);
        return true;
    }
}
