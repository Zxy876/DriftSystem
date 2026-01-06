package com.driftmc.cityphone;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

public final class CityPhoneUi {

  private static final Component TITLE = Component.text("CityPhone · 档案终端", NamedTextColor.AQUA);
  private static final int SIZE = 27;
  private static final Map<Integer, TemplateButton> TEMPLATE_BUTTONS = new LinkedHashMap<>();

  static {
    registerTemplate(new TemplateButton(
      18,
      "logic_quick_start",
      Material.PAPER,
      Component.text("模板 · 执行逻辑", NamedTextColor.LIGHT_PURPLE),
      Arrays.asList(
        Component.text("添加：目标＋执行两步示例", NamedTextColor.WHITE),
        Component.text("左键套用模板", NamedTextColor.YELLOW))));
    registerTemplate(new TemplateButton(
      19,
      "constraint_night_quiet",
      Material.MAP,
      Component.text("模板 · 世界约束", NamedTextColor.BLUE),
      Arrays.asList(
        Component.text("添加：夜间施工需静音", NamedTextColor.WHITE),
        Component.text("左键套用模板", NamedTextColor.YELLOW))));
    registerTemplate(new TemplateButton(
      20,
      "resource_basic",
      Material.EMERALD,
      Component.text("模板 · 资源清单", NamedTextColor.GREEN),
      Arrays.asList(
        Component.text("添加：气球展台基础材料", NamedTextColor.WHITE),
        Component.text("左键套用模板", NamedTextColor.YELLOW))));
    registerTemplate(new TemplateButton(
      21,
      "risk_safety",
      Material.REDSTONE_TORCH,
      Component.text("模板 · 风险登记", NamedTextColor.RED),
      Arrays.asList(
        Component.text("添加：夜间噪音缓解措施", NamedTextColor.WHITE),
        Component.text("左键套用模板", NamedTextColor.YELLOW))));
    registerTemplate(new TemplateButton(
      24,
      "success_night_showcase",
      Material.GLOW_BERRIES,
      Component.text("模板 · 成功标准", NamedTextColor.GOLD),
      Arrays.asList(
        Component.text("添加：夜间亮度与反馈标准", NamedTextColor.WHITE),
        Component.text("左键套用模板", NamedTextColor.YELLOW))));
  }

  private CityPhoneUi() {
  }

  public static void open(Player player, CityPhoneSnapshot snapshot) {
    Inventory inventory = Bukkit.createInventory(null, SIZE, TITLE);
    inventory.setItem(10, buildVisionItem(snapshot));
    inventory.setItem(12, buildResourceItem(snapshot));
    inventory.setItem(14, buildLocationItem(snapshot));
    inventory.setItem(16, buildPlanItem(snapshot));
    inventory.setItem(22, buildStatusItem(snapshot));
    for (TemplateButton button : TEMPLATE_BUTTONS.values()) {
      inventory.setItem(button.slot(), button.createItem());
    }
    player.openInventory(inventory);
  }

  public static boolean isCityPhoneInventory(InventoryView view) {
    if (view == null) {
      return false;
    }
    Component title = view.title();
    return TITLE.equals(title);
  }

  private static ItemStack buildVisionItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.WRITABLE_BOOK);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(Component.text("阶段 · " + snapshot.phase, NamedTextColor.AQUA));
    List<Component> lore = new ArrayList<>();
    lore.add(Component.text("覆盖状态:", NamedTextColor.AQUA));
    lore.add(renderCoverage("执行逻辑", snapshot.coverage.logicOutline));
    lore.add(renderCoverage("世界约束", snapshot.coverage.worldConstraints));
    lore.add(renderCoverage("成功标准", snapshot.coverage.successCriteria));
    lore.add(Component.text("目标纲要:", NamedTextColor.GOLD));
    lore.addAll(renderList(snapshot.goals, NamedTextColor.WHITE));
    if (!snapshot.logicOutline.isEmpty()) {
      lore.add(Component.text("执行逻辑:", NamedTextColor.GOLD));
      lore.addAll(renderList(snapshot.logicOutline, NamedTextColor.WHITE));
    }
    if (!snapshot.openQuestions.isEmpty()) {
      lore.add(Component.text("待补充:", NamedTextColor.YELLOW));
      lore.addAll(renderList(snapshot.openQuestions, NamedTextColor.YELLOW));
    }
    if (!snapshot.notes.isEmpty()) {
      lore.add(Component.text("最新记录:", NamedTextColor.GRAY));
      lore.addAll(renderList(snapshot.notes, NamedTextColor.GRAY));
    }
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildResourceItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.CHEST);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(Component.text("资源备货", NamedTextColor.GREEN));
    List<Component> lore = new ArrayList<>();
    if (snapshot.resources.isEmpty()) {
      lore.add(Component.text(snapshot.resourcesPending ? "待补齐资源清单" : "暂无资源记录", NamedTextColor.GRAY));
    } else {
      lore.add(Component.text("当前清单:", NamedTextColor.GOLD));
      lore.addAll(renderList(snapshot.resources, NamedTextColor.WHITE));
    }
    if (snapshot.riskRegister.isEmpty()) {
      lore.add(Component.text(snapshot.riskPending ? "风险登记待补" : "暂无风险登记", NamedTextColor.YELLOW));
    } else {
      lore.add(Component.text("风险登记:", NamedTextColor.GOLD));
      lore.addAll(renderList(snapshot.riskRegister, NamedTextColor.WHITE));
    }
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildLocationItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.COMPASS);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(Component.text("定位追踪", NamedTextColor.BLUE));
    List<Component> lore = new ArrayList<>();
    if (snapshot.locationHint != null && !snapshot.locationHint.isEmpty()) {
      lore.add(Component.text("地点提示: " + snapshot.locationHint, NamedTextColor.WHITE));
    }
    if (snapshot.playerPose != null) {
      lore.add(Component.text(
          String.format(
              "坐标: %s (%.1f, %.1f, %.1f)",
              snapshot.playerPose.world,
              snapshot.playerPose.x,
              snapshot.playerPose.y,
              snapshot.playerPose.z),
          NamedTextColor.GREEN));
    } else {
      lore.add(Component.text("未同步玩家坐标", NamedTextColor.GRAY));
    }
    if (snapshot.locationPending) {
      lore.add(Component.text("使用 /cityphone pose 同步当前坐标", NamedTextColor.YELLOW));
    }
    if (snapshot.locationQuality != null && !snapshot.locationQuality.isEmpty()) {
      lore.add(Component.text(snapshot.locationQuality, NamedTextColor.AQUA));
    }
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildPlanItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(Material.FILLED_MAP);
    ItemMeta meta = item.getItemMeta();
    meta.displayName(Component.text("建造计划", NamedTextColor.LIGHT_PURPLE));
    List<Component> lore = new ArrayList<>();
    if (!snapshot.planAvailable) {
      lore.add(Component.text("计划尚未生成", NamedTextColor.GRAY));
      if (!snapshot.planPendingReasons.isEmpty()) {
        lore.add(Component.text("阻塞项:", NamedTextColor.YELLOW));
        lore.addAll(renderList(snapshot.planPendingReasons, NamedTextColor.YELLOW));
      } else if (!snapshot.blocking.isEmpty()) {
        lore.add(Component.text("阻塞项:", NamedTextColor.YELLOW));
        lore.addAll(renderList(snapshot.blocking, NamedTextColor.YELLOW));
      }
    } else {
      if (snapshot.planSummary != null && !snapshot.planSummary.isEmpty()) {
        lore.add(Component.text(snapshot.planSummary, NamedTextColor.WHITE));
      }
      if (!snapshot.planSteps.isEmpty()) {
        lore.add(Component.text("执行步骤:", NamedTextColor.GOLD));
        lore.addAll(renderList(snapshot.planSteps, NamedTextColor.WHITE));
      }
      if (!snapshot.modHooks.isEmpty()) {
        lore.add(Component.text("关联模组:", NamedTextColor.GREEN));
        lore.addAll(renderList(snapshot.modHooks, NamedTextColor.GREEN));
      }
      if (!snapshot.planPendingReasons.isEmpty()) {
        lore.add(Component.text("执行提示:", NamedTextColor.YELLOW));
        lore.addAll(renderList(snapshot.planPendingReasons, NamedTextColor.YELLOW));
      }
    }
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static ItemStack buildStatusItem(CityPhoneSnapshot snapshot) {
    ItemStack item = new ItemStack(snapshot.readyForBuild ? Material.EMERALD : Material.REDSTONE);
    ItemMeta meta = item.getItemMeta();
    if (snapshot.readyForBuild) {
      meta.displayName(Component.text("状态: 可执行", NamedTextColor.GREEN));
    } else {
      meta.displayName(Component.text("状态: 准备中", NamedTextColor.RED));
    }
    List<Component> lore = new ArrayList<>();
    lore.add(Component.text("建造能力: " + snapshot.buildCapability + "/200", NamedTextColor.AQUA));
    lore.add(Component.text("动机评分: " + snapshot.motivationScore, NamedTextColor.GREEN));
    lore.add(Component.text("逻辑评分: " + snapshot.logicScore, NamedTextColor.GREEN));
    lore.add(Component.text("计划状态: " + snapshot.planStatus, NamedTextColor.WHITE));
    if (!snapshot.openQuestions.isEmpty()) {
      lore.add(Component.text("剩余疑问:", NamedTextColor.YELLOW));
      lore.addAll(renderList(snapshot.openQuestions, NamedTextColor.YELLOW));
    }
    meta.lore(lore);
    item.setItemMeta(meta);
    return item;
  }

  private static List<Component> renderList(List<String> entries, NamedTextColor color) {
    List<Component> result = new ArrayList<>();
    if (entries.isEmpty()) {
      result.add(Component.text("(无)", NamedTextColor.GRAY));
      return result;
    }
    int limit = Math.min(entries.size(), 6);
    for (int i = 0; i < limit; i++) {
      String line = entries.get(i);
      result.add(Component.text("• " + line, color));
    }
    if (entries.size() > limit) {
      result.add(Component.text("• ...", NamedTextColor.DARK_GRAY));
    }
    return result;
  }

  private static Component renderCoverage(String label, boolean fulfilled) {
    return Component.text(
        label + ": " + (fulfilled ? "完成" : "缺失"),
        fulfilled ? NamedTextColor.GREEN : NamedTextColor.RED);
  }

  private static void registerTemplate(TemplateButton button) {
    TEMPLATE_BUTTONS.put(button.slot(), button);
  }

  public static TemplateButton getTemplateButton(int slot) {
    return TEMPLATE_BUTTONS.get(slot);
  }

  static final class TemplateButton {
    private final int slot;
    private final String templateKey;
    private final Material material;
    private final Component title;
    private final List<Component> lore;

    TemplateButton(int slot, String templateKey, Material material, Component title, List<Component> lore) {
      this.slot = slot;
      this.templateKey = templateKey;
      this.material = material;
      this.title = title;
      this.lore = lore;
    }

    int slot() {
      return slot;
    }

    String templateKey() {
      return templateKey;
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
}
