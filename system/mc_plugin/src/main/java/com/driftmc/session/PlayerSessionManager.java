package com.driftmc.session;

import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.bukkit.entity.Player;

public class PlayerSessionManager {

    public enum Mode {
        NORMAL,
        TUTORIAL,
        AI_CHAT
    }

    private final Map<UUID, Mode> modeMap = new ConcurrentHashMap<>();
    private final Set<UUID> completedTutorial = ConcurrentHashMap.newKeySet();

    public PlayerSessionManager() {
    }

    public Mode getMode(Player player) {
        return modeMap.getOrDefault(player.getUniqueId(), Mode.NORMAL);
    }

    public void setMode(Player player, Mode mode) {
        if (player == null || mode == null) {
            return;
        }
        if (mode == Mode.NORMAL) {
            modeMap.remove(player.getUniqueId());
        } else {
            modeMap.put(player.getUniqueId(), mode);
        }
    }

    public boolean isAiChat(Player player) {
        return getMode(player) == Mode.AI_CHAT;
    }

    public boolean isTutorial(Player player) {
        return getMode(player) == Mode.TUTORIAL;
    }

    public void markTutorialStarted(Player player) {
        if (player == null) {
            return;
        }
        setMode(player, Mode.TUTORIAL);
    }

    public void markTutorialComplete(Player player) {
        if (player == null) {
            return;
        }
        completedTutorial.add(player.getUniqueId());
        setMode(player, Mode.NORMAL);
    }

    public boolean hasCompletedTutorial(Player player) {
        if (player == null) {
            return false;
        }
        return completedTutorial.contains(player.getUniqueId());
    }

    public boolean hasCompletedTutorial(UUID playerId) {
        if (playerId == null) {
            return false;
        }
        return completedTutorial.contains(playerId);
    }

    public void reset(Player player) {
        if (player == null) {
            return;
        }
        UUID id = player.getUniqueId();
        modeMap.remove(id);
        completedTutorial.remove(id);
    }
}
