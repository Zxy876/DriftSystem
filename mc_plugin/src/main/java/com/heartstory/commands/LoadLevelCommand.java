package com.heartstory.commands;

import com.heartstory.http.BackendClient;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class LoadLevelCommand implements CommandExecutor {

    private final BackendClient backend = new BackendClient();

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {

        if (!(sender instanceof Player player)) {
            sender.sendMessage("玩家才能使用！");
            return true;
        }

        if (args.length < 1) {
            player.sendMessage("用法: /loadlevel <level_id>");
            return true;
        }

        String levelId = args[0];

        player.sendMessage("§e正在加载关卡：" + levelId);

        try {
            String resp = backend.loadLevel(player.getName(), levelId);
            player.sendMessage("§a后端响应: §f" + resp);
        } catch (Exception e) {
            player.sendMessage("§c连接后端失败：" + e.getMessage());
        }

        return true;
    }
}
