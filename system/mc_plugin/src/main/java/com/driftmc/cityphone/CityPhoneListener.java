package com.driftmc.cityphone;

import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;

public final class CityPhoneListener implements Listener {

  private final CityPhoneManager manager;

  public CityPhoneListener(CityPhoneManager manager) {
    this.manager = manager;
  }

  @EventHandler
  public void onPlayerInteract(PlayerInteractEvent event) {
    if (event.getHand() != EquipmentSlot.HAND) {
      return;
    }
    Action action = event.getAction();
    if (action != Action.RIGHT_CLICK_AIR && action != Action.RIGHT_CLICK_BLOCK) {
      return;
    }
    ItemStack item = event.getItem();
    if (!manager.isCityPhone(item)) {
      return;
    }
    event.setCancelled(true);
    Player player = event.getPlayer();
    if (item.getType() == Material.AIR) {
      return;
    }
    manager.openPhone(player);
  }
}
