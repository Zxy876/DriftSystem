package com.driftmc;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class NextCommand implements CommandExecutor {

    @Override
    public boolean onCommand(CommandSender cs, Command cmd, String lbl, String[] args) {

        if (!(cs instanceof Player)) {
            cs.sendMessage("玩家才能执行");
            return true;
        }

        Player p = (Player) cs;
        String res = BackendClient.post("/story/advance/" + p.getName());
        p.sendMessage("§b剧情推进！");
        p.sendMessage("§7后端响应: " + res);
        return true;
    }
}
