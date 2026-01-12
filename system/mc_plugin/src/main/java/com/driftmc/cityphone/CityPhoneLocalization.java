package com.driftmc.cityphone;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/** Loads localized strings for the CityPhone UI from bundled resource files. */
public final class CityPhoneLocalization {

  private static CityPhoneLocalization instance;

  private final Map<String, Object> zh;
  private final Map<String, Object> en;

  private CityPhoneLocalization(JavaPlugin plugin) {
    this.zh = loadBundle(plugin, "cityphone/messages_zh.yml");
    this.en = loadBundle(plugin, "cityphone/messages_en.yml");
  }

  public static void init(JavaPlugin plugin) {
    instance = new CityPhoneLocalization(plugin);
  }

  public static String text(String key) {
    return getInstance().getString(key);
  }

  public static String format(String key, Object... args) {
    return String.format(Locale.ROOT, text(key), args);
  }

  public static List<String> list(String key) {
    return getInstance().getList(key);
  }

  public static Component component(String key, NamedTextColor color) {
    return Component.text(text(key), color);
  }

  public static Component componentFormatted(String key, NamedTextColor color, Object... args) {
    return Component.text(format(key, args), color);
  }

  public static Component prefixed(String key, NamedTextColor color) {
    return prefixedFormatted(key, color);
  }

  public static Component prefixedFormatted(String key, NamedTextColor color, Object... args) {
    String message = args.length == 0 ? text(key) : format(key, args);
    return Component.text(format("message.prefix", message), color);
  }

  public static Component prefixedRaw(String raw, NamedTextColor color) {
    return Component.text(format("message.prefix", raw), color);
  }

  private String getString(String key) {
    Object value = resolve(key);
    if (value instanceof String) {
      return (String) value;
    }
    if (value instanceof List<?>) {
      List<?> list = (List<?>) value;
      if (list.isEmpty()) {
        return "";
      }
      Object first = list.get(0);
      return first != null ? first.toString() : "";
    }
    return key;
  }

  private List<String> getList(String key) {
    Object value = resolve(key);
    if (value instanceof List<?>) {
      List<String> lines = new ArrayList<>();
      for (Object entry : (List<?>) value) {
        lines.add(entry == null ? "" : entry.toString());
      }
      return Collections.unmodifiableList(lines);
    }
    if (value instanceof String) {
      return Collections.singletonList((String) value);
    }
    return Collections.emptyList();
  }

  private Object resolve(String key) {
    Object value = zh.get(key);
    if (value != null) {
      return value;
    }
    value = en.get(key);
    if (value != null) {
      return value;
    }
    return key;
  }

  private static CityPhoneLocalization getInstance() {
    if (instance == null) {
      throw new IllegalStateException("CityPhoneLocalization has not been initialised.");
    }
    return instance;
  }

  private static Map<String, Object> loadBundle(JavaPlugin plugin, String path) {
    try (InputStream stream = plugin.getResource(path)) {
      if (stream == null) {
        return Collections.emptyMap();
      }
      try (InputStreamReader reader = new InputStreamReader(stream, StandardCharsets.UTF_8)) {
        YamlConfiguration config = YamlConfiguration.loadConfiguration(reader);
        Map<String, Object> entries = new HashMap<>();
        flatten(config, "", entries);
        return entries;
      }
    } catch (IOException ex) {
      return Collections.emptyMap();
    }
  }

  private static void flatten(ConfigurationSection section, String base, Map<String, Object> target) {
    for (String key : section.getKeys(false)) {
      String fullKey = base.isEmpty() ? key : base + "." + key;
      Object value = section.get(key);
      if (value instanceof ConfigurationSection child) {
        flatten(child, fullKey, target);
      } else {
        target.put(fullKey, Objects.requireNonNullElse(value, ""));
      }
    }
  }

  private CityPhoneLocalization() {
    throw new UnsupportedOperationException();
  }
}
