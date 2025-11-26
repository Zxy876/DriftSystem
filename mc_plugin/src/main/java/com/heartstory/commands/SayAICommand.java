package com.heartstory.commands;

import com.heartstory.http.BackendClient;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class SayAICommand implements CommandExecutor {

    private final BackendClient backend = new BackendClient();

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String lbl, String[] args) {

        if (!(sender instanceof Player player)) {
            sender.sendMessage("玩家才能使用！");
            return true;
        }

        if (args.length < 1) {
            player.sendMessage("用法: /sayai <文本>");
            return true;
        }

        String text = String.join(" ", args);

        try {
            String resp = backend.sayToAI(player.getName(), text);
            player.sendMessage("§aAI回应: §f" + resp);
        } catch (Exception e) {
            player.sendMessage("§c后端连接失败：" + e.getMessage());
        }

        return true;
    }
}
