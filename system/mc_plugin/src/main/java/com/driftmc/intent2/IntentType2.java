package com.driftmc.intent2;

public enum IntentType2 {

    SHOW_MINIMAP,

    SET_DAY,
    SET_NIGHT,
    SET_WEATHER,
    TELEPORT,
    SPAWN_ENTITY,
    BUILD_STRUCTURE,

    CREATE_BLOCK,

    STORY_CONTINUE,
    GOTO_LEVEL,
    GOTO_NEXT_LEVEL,

    IDEAL_CITY_SUBMIT,

    CREATE_STORY, // 新增：创建剧情

    SAY_ONLY,
    UNKNOWN;

    public static IntentType2 fromString(String s) {
        if (s == null)
            return UNKNOWN;
        return switch (s.toUpperCase()) {
            case "SHOW_MINIMAP" -> SHOW_MINIMAP;

            case "SET_DAY" -> SET_DAY;
            case "SET_NIGHT" -> SET_NIGHT;
            case "SET_WEATHER" -> SET_WEATHER;
            case "TELEPORT" -> TELEPORT;
            case "SPAWN_ENTITY" -> SPAWN_ENTITY;
            case "BUILD_STRUCTURE" -> BUILD_STRUCTURE;

            case "CREATE_BLOCK" -> CREATE_BLOCK;

            case "STORY_CONTINUE" -> STORY_CONTINUE;
            case "GOTO_LEVEL" -> GOTO_LEVEL;
            case "GOTO_NEXT_LEVEL" -> GOTO_NEXT_LEVEL;

            case "IDEAL_CITY_SUBMIT" -> IDEAL_CITY_SUBMIT;

            case "CREATE_STORY" -> CREATE_STORY;

            case "SAY_ONLY" -> SAY_ONLY;
            default -> UNKNOWN;
        };
    }
}