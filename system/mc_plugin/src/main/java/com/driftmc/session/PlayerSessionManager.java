package com.driftmc.session;

import org.bukkit.entity.Player;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public class PlayerSessionManager {

    public enum Mode {
        NORMAL,
        AI_CHAT
    }

    private final Map<UUID, Mode> modeMap = new ConcurrentHashMap<>();

    public PlayerSessionManager() {
    }

    public Mode getMode(Player player) {
        return modeMap.getOrDefault(player.getUniqueId(), Mode.NORMAL);
    }

    public void setMode(Player player, Mode mode) {
        modeMap.put(player.getUniqueId(), mode);
    }

    public boolean isAiChat(Player player) {
        return getMode(player) == Mode.AI_CHAT;
    }
}
