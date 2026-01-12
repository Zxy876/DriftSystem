package com.driftmc.cityphone;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

public final class CityPhoneUi {

  private static final Component TITLE = CityPhoneLocalization.component("title.main", NamedTextColor.AQUA);
  private static final Component HISTORY_TITLE = CityPhoneLocalization.component("title.history", NamedTextColor.AQUA);
  private static final int SIZE = 27;
  static final int NARRATIVE_SLOT = 13;
  private static final EnumMap<ViewKind, Map<Integer, ActionButton>> ACTION_BUTTONS = new EnumMap<>(ViewKind.class);

  static {
    ACTION_BUTTONS.put(ViewKind.MAIN, new LinkedHashMap<>());
    ACTION_BUTTONS.put(ViewKind.HISTORY, new LinkedHashMap<>());
    ACTION_BUTTONS.put(ViewKind.NARRATIVE, new LinkedHashMap<>());

    registerAction(ViewKind.MAIN, new ActionButton(
        18,
        "history_view",
        Material.BOOKSHELF,
        CityPhoneLocalization.component("button.history_view.title", NamedTextColor.GOLD),
        colorizeLore(
            CityPhoneLocalization.list("button.history_view.lore"),
            NamedTextColor.WHITE,
            NamedTextColor.YELLOW)));

    registerAction(ViewKind.HISTORY, new ActionButton(
        22,
        "history_back",
        Material.ARROW,
        CityPhoneLocalization.component("button.history_back.title", NamedTextColor.AQUA),
        colorizeLore(
            CityPhoneLocalization.list("button.history_back.lore"),
            NamedTextColor.WHITE,
            NamedTextColor.YELLOW)));

    registerAction(ViewKind.NARRATIVE, new ActionButton(
      49,
      "narrative_back",
      Material.ARROW,
      CityPhoneLocalization.component("button.narrative_back.title", NamedTextColor.AQUA),
      colorizeLore(
        CityPhoneLocalization.list("button.narrative_back.lore"),
        NamedTextColor.WHITE,
        NamedTextColor.YELLOW)));
  }

  private CityPhoneUi() {
  }

  public static void open(Player player, CityPhoneSnapshot snapshot) {
    CityPhoneInventoryHolder holder = new CityPhoneInventoryHolder(ViewKind.MAIN);
    Inventory inventory = Bukkit.createInventory(holder, SIZE, TITLE);
    holder.bind(inventory);

    inventory.setItem(10, buildExhibitStatusItem(snapshot));
    inventory.setItem(12, buildInterpretationPreviewItem(snapshot));
    inventory.setItem(NARRATIVE_SLOT, buildNarrativePreviewItem(snapshot));
    inventory.setItem(16, buildUnknownsPreviewItem(snapshot));
    inventory.setItem(22, buildHistoryDigestItem(snapshot));
    populateActionButtons(inventory, ViewKind.MAIN);
    player.openInventory(inventory);
  }

  public static void openHistory(Player player, CityPhoneSnapshot snapshot) {
    CityPhoneInventoryHolder holder = new CityPhoneInventoryHolder(ViewKind.HISTORY);
    Inventory inventory = Bukkit.createInventory(holder, SIZE, HISTORY_TITLE);
    holder.bind(inventory);
    List<CityPhoneSnapshot.Section> sections = snapshot.narrative != null
        ? snapshot.narrative.sections
        : Collections.emptyList();
    if (sections.isEmpty()) {
      inventory.setItem(13, buildEmptyNarrativeItem());
    } else {
      int[] sectionSlots = new int[] {10, 11, 12, 13, 19, 20, 21, 23};
      for (int index = 0; index < sections.size() && index < sectionSlots.length; index++) {
        inventory.setItem(sectionSlots[index], buildNarrativeHistoryItem(sections.get(index)));
      }
      if (sections.size() > sectionSlots.length) {
        inventory.setItem(24, buildNarrativeOverflowItem(snapshot));
      }
    }
    populateActionButtons(inventory, ViewKind.HISTORY);
    player.openInventory(inventory);
  }

  public static boolean isCityPhoneInventory(InventoryView view) {
    if (view == null) {
      return false;
    }
    InventoryHolder holder = view.getTopInventory().getHolder();
    return holder instanceof CityPhoneInventoryHolder;
  }

  public static ViewKind getViewKind(InventoryView view) {
    if (view == null) {
      return null;
    }
    InventoryHolder holder = view.getTopInventory().getHolder();
    if (holder instanceof CityPhoneInventoryHolder cityPhoneHolder) {
      return cityPhoneHolder.kind();
    }
    return null;
  }

  private static ItemStack buildExhibitStatusItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.LODESTONE);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.anchor.title", NamedTextColor.AQUA));
    List<Component> lore = new ArrayList<>();

    if (snapshot.narrative != null) {
      CityPhoneSnapshot.Narrative narrative = snapshot.narrative;
      if (narrative.title != null && !narrative.title.isEmpty()) {
        lore.add(Component.text(narrative.title, NamedTextColor.WHITE));
      }
      if (narrative.timeframe != null && !narrative.timeframe.isEmpty()) {
        lore.add(CityPhoneLocalization.componentFormatted("ui.anchor.timeframe", NamedTextColor.GRAY, narrative.timeframe));
      }
      String modeLabel = resolveModeLabel(snapshot);
      if (modeLabel != null && !modeLabel.isEmpty()) {
        lore.add(CityPhoneLocalization.componentFormatted("ui.anchor.mode", NamedTextColor.GOLD, modeLabel));
        if (snapshot.exhibitMode != null && !snapshot.exhibitMode.description.isEmpty()) {
          lore.addAll(renderNarrativeBody(snapshot.exhibitMode.description, NamedTextColor.GOLD, 3));
        }
      }
      if (narrative.lastEvent != null && !narrative.lastEvent.isEmpty()) {
        lore.add(CityPhoneLocalization.componentFormatted("ui.anchor.last_event", NamedTextColor.DARK_AQUA, narrative.lastEvent));
      }
    }

    if (lore.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.anchor.empty", NamedTextColor.GRAY));
    }

    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildInterpretationPreviewItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.WRITTEN_BOOK);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.sources.title", NamedTextColor.AQUA));
    List<Component> lore = new ArrayList<>();

    if (snapshot.cityInterpretation.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.sources.empty", NamedTextColor.GRAY));
    } else {
      lore.addAll(renderListLimited(snapshot.cityInterpretation, NamedTextColor.WHITE, 4));
    }

    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildNarrativePreviewItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.PAPER);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.narrative_preview.title", NamedTextColor.GOLD));
    List<Component> lore = new ArrayList<>();

    CityPhoneSnapshot.Narrative narrative = snapshot.narrative;
    if (narrative == null || narrative.sections.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.narrative_preview.empty", NamedTextColor.GRAY));
    } else {
      if (narrative.title != null && !narrative.title.isEmpty()) {
        lore.add(Component.text(narrative.title, NamedTextColor.AQUA));
      }
      CityPhoneSnapshot.Section first = narrative.sections.get(0);
      lore.addAll(renderNarrativeBody(first.body, colorForAccent(first.accent), 4));
    }
    lore.add(Component.text("", NamedTextColor.DARK_GRAY));
    lore.add(CityPhoneLocalization.component("ui.narrative_preview.open_hint", NamedTextColor.GRAY));

    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildUnknownsPreviewItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.SPYGLASS);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.unknowns.title", NamedTextColor.YELLOW));
    List<Component> lore = new ArrayList<>();

    if (snapshot.unknowns.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.unknowns.empty", NamedTextColor.GRAY));
    } else {
      lore.addAll(renderListLimited(snapshot.unknowns, NamedTextColor.YELLOW, 4));
    }

    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildHistoryDigestItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.BOOKSHELF);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("title.history", NamedTextColor.AQUA));
    List<Component> lore = new ArrayList<>();

    if (snapshot.historyEntries.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.history.empty", NamedTextColor.GRAY));
    } else {
      lore.addAll(renderListLimited(snapshot.historyEntries, NamedTextColor.WHITE, 4));
    }
    lore.add(Component.text("", NamedTextColor.DARK_GRAY));
    lore.add(CityPhoneLocalization.component("ui.history.digest_hint", NamedTextColor.GRAY));

    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildNarrativeOverflowItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.PAPER);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.narrative.index_title", NamedTextColor.LIGHT_PURPLE));
    List<Component> lore = new ArrayList<>();
    lore.add(CityPhoneLocalization.component("ui.narrative.index_heading", NamedTextColor.AQUA));
    int totalSections = snapshot.narrative != null ? snapshot.narrative.sections.size() : 0;
    for (int index = 0; index < totalSections; index++) {
      CityPhoneSnapshot.Section section = snapshot.narrative.sections.get(index);
      String label = section.title != null ? section.title : CityPhoneLocalization.text("ui.narrative.fallback_title");
      lore.add(Component.text("• " + label, NamedTextColor.WHITE));
    }
    if (totalSections == 0) {
      lore.add(CityPhoneLocalization.component("ui.narrative.index_empty", NamedTextColor.GRAY));
    }
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildNarrativeHistoryItem(CityPhoneSnapshot.Section section) {
    ItemStack item = new ItemStack(Material.WRITTEN_BOOK);
    ItemMeta meta = item.getItemMeta();
    NamedTextColor accent = colorForAccent(section.accent);
    String title = section.title != null ? section.title : CityPhoneLocalization.text("ui.narrative.fallback_title");
    meta.displayName(Component.text(title, accent));
    List<Component> lore = new ArrayList<>();
    lore.addAll(renderNarrativeBody(section.body, accent, 14));
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildEmptyNarrativeItem() {
    ItemStack item = new ItemStack(Material.MAP);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.narrative.history_empty_title", NamedTextColor.GRAY));
    List<Component> lore = new ArrayList<>();
    lore.add(CityPhoneLocalization.component("ui.narrative.history_empty_1", NamedTextColor.GRAY));
    lore.add(CityPhoneLocalization.component("ui.narrative.history_empty_2", NamedTextColor.DARK_GRAY));
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  static NamedTextColor colorForAccent(String accent) {
    if (accent == null) {
      return NamedTextColor.WHITE;
    }
    switch (accent) {
      case "ready":
        return NamedTextColor.GREEN;
      case "collecting":
        return NamedTextColor.GOLD;
      case "alert":
        return NamedTextColor.RED;
      default:
        return NamedTextColor.WHITE;
    }
  }

  static String resolveModeLabel(CityPhoneSnapshot snapshot) {
    if (snapshot.exhibitMode != null) {
      String modeKey = snapshot.exhibitMode.mode;
      if (modeKey != null && !modeKey.isEmpty()) {
        String lookup = "mode.label." + modeKey.toLowerCase(Locale.ROOT);
        String localized = CityPhoneLocalization.text(lookup);
        if (localized != null && !localized.equals(lookup)) {
          return localized;
        }
      }
      if (snapshot.exhibitMode.label != null && !snapshot.exhibitMode.label.isEmpty()) {
        return snapshot.exhibitMode.label;
      }
    }
    if (snapshot.narrative != null && snapshot.narrative.mode != null && !snapshot.narrative.mode.isEmpty()) {
      return snapshot.narrative.mode;
    }
    return null;
  }

  static List<Component> renderNarrativeBody(List<String> lines, NamedTextColor color, int lineLimit) {
    List<Component> lore = new ArrayList<>();
    if (lines == null || lines.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.narrative.body_empty", NamedTextColor.GRAY));
      return lore;
    }
    int limit = lineLimit <= 0 ? lines.size() : Math.min(lines.size(), lineLimit);
    for (int i = 0; i < limit; i++) {
      String line = lines.get(i);
      lore.add(Component.text("• " + line, color));
    }
    if (lines.size() > limit) {
      lore.add(Component.text("• ...", NamedTextColor.DARK_GRAY));
    }
    return lore;
  }

  private static List<Component> renderList(List<String> entries, NamedTextColor color) {
    return renderListLimited(entries, color, 6);
  }

  static List<Component> renderListLimited(List<String> entries, NamedTextColor color, int limit) {
    List<Component> result = new ArrayList<>();
    if (entries == null || entries.isEmpty()) {
      result.add(CityPhoneLocalization.component("list.empty", NamedTextColor.GRAY));
      return result;
    }
    int effectiveLimit = limit <= 0 ? entries.size() : Math.min(entries.size(), limit);
    for (int i = 0; i < effectiveLimit; i++) {
      String line = entries.get(i);
      result.add(Component.text("• " + line, color));
    }
    if (entries.size() > effectiveLimit) {
      result.add(Component.text("• ...", NamedTextColor.DARK_GRAY));
    }
    return result;
  }

  private static List<Component> colorizeLore(List<String> lines, NamedTextColor... palette) {
    List<Component> components = new ArrayList<>();
    if (lines.isEmpty()) {
      return components;
    }
    for (int index = 0; index < lines.size(); index++) {
      NamedTextColor color = palette.length == 0 ? NamedTextColor.WHITE : palette[Math.min(index, palette.length - 1)];
      components.add(Component.text(lines.get(index), color));
    }
    return components;
  }

  static void populateActionButtons(Inventory inventory, ViewKind kind) {
    Map<Integer, ActionButton> buttons = ACTION_BUTTONS.get(kind);
    if (buttons == null) {
      return;
    }
    for (ActionButton button : buttons.values()) {
      inventory.setItem(button.slot(), button.createItem());
    }
  }

  private static void registerAction(ViewKind kind, ActionButton button) {
    Map<Integer, ActionButton> buttons = ACTION_BUTTONS.get(kind);
    if (buttons != null) {
      buttons.put(button.slot(), button);
    }
  }

  public static ActionButton getActionButton(ViewKind kind, int slot) {
    Map<Integer, ActionButton> buttons = ACTION_BUTTONS.get(kind);
    if (buttons == null) {
      return null;
    }
    return buttons.get(slot);
  }

  static final class ActionButton {
    private final int slot;
    private final String actionKey;
    private final Material material;
    private final Component title;
    private final List<Component> lore;

    ActionButton(int slot, String actionKey, Material material, Component title, List<Component> lore) {
      this.slot = slot;
      this.actionKey = actionKey;
      this.material = material;
      this.title = title;
      this.lore = lore;
    }

    int slot() {
      return slot;
    }

    String actionKey() {
      return actionKey;
    }

    ItemStack createItem() {
      ItemStack item = new ItemStack(material);
      ItemMeta meta = item.getItemMeta();
      if (meta != null) {
        meta.displayName(title);
        List<Component> copy = new ArrayList<>(lore);
        meta.lore(copy);
        item.setItemMeta(meta);
      }
      return item;
    }
  }

  enum ViewKind {
    MAIN,
    HISTORY,
    NARRATIVE
  }

  static final class CityPhoneInventoryHolder implements InventoryHolder {
    private final ViewKind kind;
    private Inventory inventory;

    CityPhoneInventoryHolder(ViewKind kind) {
      this.kind = kind;
    }

    void bind(Inventory inventory) {
      this.inventory = inventory;
    }

    ViewKind kind() {
      return kind;
    }

    @Override
    public Inventory getInventory() {
      return inventory;
    }
  }
}
