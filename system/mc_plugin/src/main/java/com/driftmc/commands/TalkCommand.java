package com.driftmc.commands;

import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import com.driftmc.intent.IntentRouter;

public class TalkCommand implements CommandExecutor {

    private final IntentRouter router;

    public TalkCommand(IntentRouter router) {
        this.router = router;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {

        if (!(sender instanceof Player p)) {
            sender.sendMessage("玩家才能使用此命令");
            return true;
        }

        if (args.length == 0) {
            p.sendMessage(ChatColor.RED + "用法: /talk <内容>");
            return true;
        }

        String msg = String.join(" ", args);
        p.sendMessage(ChatColor.GRAY + "你：" + msg);

        // ⭐ 统一入口：自然语言 -> IntentRouter
        router.handlePlayerSpeak(p, msg);

        return true;
    }
}