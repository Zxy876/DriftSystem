package com.driftmc.cityphone;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * Renders the full narrative text in a dedicated inventory panel so the main CityPhone view can stay collapsed.
 */
final class CityPhoneNarrativePanel {

  private static final Component TITLE = CityPhoneLocalization.component("title.narrative_panel", NamedTextColor.AQUA);
  private static final int SIZE = 54;
  private static final int HEADER_SLOT = 4;
  private static final int SECTION_START_SLOT = 10;
  private static final int SECTION_COLUMNS = 7;
  private static final int ROW_STRIDE = 9;
  private static final int MAX_SECTION_ITEMS = 28;

  private CityPhoneNarrativePanel() {
  }

  static void open(Player player, CityPhoneSnapshot snapshot) {
    CityPhoneUi.CityPhoneInventoryHolder holder = new CityPhoneUi.CityPhoneInventoryHolder(CityPhoneUi.ViewKind.NARRATIVE);
    Inventory inventory = Bukkit.createInventory(holder, SIZE, TITLE);
    holder.bind(inventory);

    inventory.setItem(HEADER_SLOT, buildHeaderItem(snapshot));

    List<CityPhoneSnapshot.Section> sections = snapshot != null && snapshot.narrative != null
        ? snapshot.narrative.sections
        : Collections.emptyList();

    if (sections.isEmpty()) {
      inventory.setItem(22, buildEmptyItem());
    } else {
      for (int index = 0; index < sections.size() && index < MAX_SECTION_ITEMS; index++) {
        int slot = slotForIndex(index);
        inventory.setItem(slot, buildSectionItem(sections.get(index)));
      }
    }

    CityPhoneUi.populateActionButtons(inventory, CityPhoneUi.ViewKind.NARRATIVE);
    player.openInventory(inventory);
  }

  private static int slotForIndex(int index) {
    int row = index / SECTION_COLUMNS;
    int column = index % SECTION_COLUMNS;
    return SECTION_START_SLOT + column + (ROW_STRIDE * row);
  }

  private static ItemStack buildHeaderItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.FILLED_MAP);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.narrative_panel.header_title", NamedTextColor.AQUA));
    List<Component> lore = new ArrayList<>();

    if (snapshot != null && snapshot.narrative != null) {
      CityPhoneSnapshot.Narrative narrative = snapshot.narrative;
      if (narrative.title != null && !narrative.title.isEmpty()) {
        lore.add(Component.text(narrative.title, NamedTextColor.WHITE));
      }
      if (narrative.timeframe != null && !narrative.timeframe.isEmpty()) {
        lore.add(CityPhoneLocalization.componentFormatted("ui.anchor.timeframe", NamedTextColor.GRAY, narrative.timeframe));
      }
      String modeLabel = CityPhoneUi.resolveModeLabel(snapshot);
      if (modeLabel != null && !modeLabel.isEmpty()) {
        lore.add(CityPhoneLocalization.componentFormatted("ui.anchor.mode", NamedTextColor.GOLD, modeLabel));
      }
      if (narrative.lastEvent != null && !narrative.lastEvent.isEmpty()) {
        lore.add(CityPhoneLocalization.componentFormatted("ui.anchor.last_event", NamedTextColor.DARK_AQUA, narrative.lastEvent));
      }
    }

    if (lore.isEmpty()) {
      lore.add(CityPhoneLocalization.component("ui.narrative_panel.header_empty", NamedTextColor.GRAY));
    }

    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildEmptyItem() {
    ItemStack item = new ItemStack(Material.MAP);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(CityPhoneLocalization.component("ui.narrative_panel.empty_title", NamedTextColor.GRAY));
    List<Component> lore = new ArrayList<>();
    lore.add(CityPhoneLocalization.component("ui.narrative_panel.empty_body", NamedTextColor.GRAY));
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildSectionItem(CityPhoneSnapshot.Section section) {
    ItemStack item = new ItemStack(Material.WRITTEN_BOOK);
    ItemMeta meta = item.getItemMeta();
    NamedTextColor accent = CityPhoneUi.colorForAccent(section.accent);
    String title = section.title != null && !section.title.isEmpty()
        ? section.title
        : CityPhoneLocalization.text("ui.narrative.fallback_title");
    meta.displayName(Component.text(title, accent));
    List<Component> lore = new ArrayList<>();
    lore.addAll(CityPhoneUi.renderNarrativeBody(section.body, accent, 14));
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }
}
