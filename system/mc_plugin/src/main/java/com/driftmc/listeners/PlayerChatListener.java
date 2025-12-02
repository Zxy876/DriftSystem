package com.driftmc.listeners;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentResponse2;
import com.driftmc.intent2.IntentRouter2;

import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

public class PlayerChatListener implements Listener {

    private final JavaPlugin plugin;
    private final IntentRouter2 router;
    private final IntentDispatcher2 dispatcher;

    public PlayerChatListener(JavaPlugin plugin, IntentRouter2 router, IntentDispatcher2 dispatcher) {
        this.plugin = plugin;
        this.router = router;
        this.dispatcher = dispatcher;
    }

    @EventHandler
    public void onAsyncChat(AsyncChatEvent e) {
        Player p = e.getPlayer();

        String msg = PlainTextComponentSerializer.plainText().serialize(e.message());
        e.setCancelled(true);

        p.sendMessage("§7你：" + msg);

        router.askIntent(p.getName(), msg, (IntentResponse2 intent) -> {
            Bukkit.getScheduler().runTask(plugin, () ->
                    dispatcher.dispatch(p, intent)
            );
        });
    }
}