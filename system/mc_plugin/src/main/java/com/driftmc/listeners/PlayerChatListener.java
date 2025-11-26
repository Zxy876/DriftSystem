package com.driftmc.listeners;

import org.bukkit.ChatColor;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerChatEvent;

import com.driftmc.backend.BackendClient;
import com.driftmc.intent.IntentRouter;
import com.driftmc.session.PlayerSessionManager;

public class PlayerChatListener implements Listener {

    private final BackendClient backend;
    private final IntentRouter router;
    private final PlayerSessionManager sessions;

    public PlayerChatListener(
            BackendClient backend,
            IntentRouter router,
            PlayerSessionManager sessions
    ) {
        this.backend = backend;
        this.router = router;
        this.sessions = sessions;
    }

    @EventHandler
    public void onChat(AsyncPlayerChatEvent event) {
        Player player = event.getPlayer();
        String msg = event.getMessage();

        // 取消原版聊天广播，只走 AI
        event.setCancelled(true);

        player.sendMessage(ChatColor.GRAY + "你：" + msg);

        // 进入意图路由
        router.handlePlayerSpeak(player, msg);
    }
}