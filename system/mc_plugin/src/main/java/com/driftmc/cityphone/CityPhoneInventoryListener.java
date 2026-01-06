package com.driftmc.cityphone;

import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;

public final class CityPhoneInventoryListener implements Listener {

  private final CityPhoneManager manager;

  public CityPhoneInventoryListener(CityPhoneManager manager) {
    this.manager = manager;
  }

  @EventHandler
  public void onInventoryClick(InventoryClickEvent event) {
    if (!CityPhoneUi.isCityPhoneInventory(event.getView())) {
      return;
    }
    event.setCancelled(true);
    if (event.getRawSlot() < 0) {
      return;
    }
    int topSize = event.getView().getTopInventory().getSize();
    if (event.getRawSlot() >= topSize) {
      return;
    }
    CityPhoneUi.TemplateButton button = CityPhoneUi.getTemplateButton(event.getRawSlot());
    if (button == null) {
      return;
    }
    if (event.getWhoClicked() instanceof Player player) {
      manager.applyTemplate(player, button.templateKey());
    }
  }

  @EventHandler
  public void onInventoryDrag(InventoryDragEvent event) {
    if (!CityPhoneUi.isCityPhoneInventory(event.getView())) {
      return;
    }
    event.setCancelled(true);
  }

  @EventHandler
  public void onInventoryClose(InventoryCloseEvent event) {
    if (!CityPhoneUi.isCityPhoneInventory(event.getView())) {
      return;
    }
    // 无状态界面，无需额外处理，保留事件占位便于未来扩展。
  }
}
