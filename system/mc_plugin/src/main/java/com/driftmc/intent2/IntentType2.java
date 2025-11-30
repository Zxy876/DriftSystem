package com.driftmc.intent2;

public enum IntentType2 {
    SHOW_MINIMAP,
    GOTO_NEXT_LEVEL,
    GOTO_LEVEL,
    SAY_ONLY,
    UNKNOWN;

    public static IntentType2 fromString(String s) {
        if (s == null) return UNKNOWN;
        return switch (s.toLowerCase()) {
            case "show_minimap"     -> SHOW_MINIMAP;
            case "goto_next_level"  -> GOTO_NEXT_LEVEL;
            case "goto_level"       -> GOTO_LEVEL;
            case "say_only"         -> SAY_ONLY;
            default                  -> UNKNOWN;
        };
    }
}