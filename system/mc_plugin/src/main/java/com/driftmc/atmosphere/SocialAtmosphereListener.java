package com.driftmc.atmosphere;

import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;

/**
 * Triggers social atmosphere playback when a player joins the server.
 */
public final class SocialAtmosphereListener implements Listener {

    private final SocialAtmosphereManager manager;

    public SocialAtmosphereListener(SocialAtmosphereManager manager) {
        this.manager = manager;
    }

    @EventHandler
    public void onPlayerJoin(PlayerJoinEvent event) {
        manager.scheduleFor(event.getPlayer());
    }
}
