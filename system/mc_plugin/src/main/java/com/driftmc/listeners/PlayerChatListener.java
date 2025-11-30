package com.driftmc.listeners;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.intent.IntentRouter;
import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentResponse2;
import com.driftmc.intent2.IntentRouter2;
import com.driftmc.session.PlayerSessionManager;

public class PlayerChatListener implements Listener {

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final IntentRouter storyRouter;
    private final PlayerSessionManager sessions;
    private final IntentRouter2 intentRouter2;
    private final IntentDispatcher2 dispatcher2;

    public PlayerChatListener(
            JavaPlugin plugin,
            BackendClient backend,
            IntentRouter storyRouter,
            PlayerSessionManager sessions,
            IntentRouter2 intentRouter2,
            IntentDispatcher2 dispatcher2
    ) {
        this.plugin = plugin;
        this.backend = backend;
        this.storyRouter = storyRouter;
        this.sessions = sessions;
        this.intentRouter2 = intentRouter2;
        this.dispatcher2 = dispatcher2;
    }

    @EventHandler
    public void onChat(AsyncPlayerChatEvent event) {
        Player player = event.getPlayer();
        String msg = event.getMessage();

        event.setCancelled(true);
        player.sendMessage(ChatColor.GRAY + "你：" + msg);

        // 异步 → Intent 判断
        intentRouter2.askIntent(player.getName(), msg, (IntentResponse2 intent) -> {

            // 有意图 → 主线程执行
            if (intent.type != com.driftmc.intent2.IntentType2.UNKNOWN) {
                Bukkit.getScheduler().runTask(plugin, () -> {
                    dispatcher2.dispatch(player, intent);
                });
                return;
            }

            // 没意图 → 交给故事引擎（主线程）
            Bukkit.getScheduler().runTask(plugin, () -> {
                storyRouter.handlePlayerSpeak(player, msg);
            });
        });
    }
}