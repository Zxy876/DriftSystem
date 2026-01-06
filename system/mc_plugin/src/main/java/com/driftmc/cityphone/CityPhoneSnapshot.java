package com.driftmc.cityphone;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

/** Lightweight DTO parsed from the CityPhone backend state payload. */
public final class CityPhoneSnapshot {

  public final String phase;
  public final boolean readyForBuild;
  public final int buildCapability;
  public final int motivationScore;
  public final int logicScore;
  public final List<String> blocking;
  public final List<String> goals;
  public final List<String> logicOutline;
  public final List<String> openQuestions;
  public final List<String> notes;
  public final List<String> resources;
  public final boolean resourcesPending;
  public final List<String> riskRegister;
  public final boolean riskPending;
  public final String locationHint;
  public final Pose playerPose;
  public final boolean locationPending;
  public final String locationQuality;
  public final Coverage coverage;
  public final boolean planAvailable;
  public final String planSummary;
  public final List<String> planSteps;
  public final String planStatus;
  public final List<String> planPendingReasons;
  public final List<String> modHooks;

  private CityPhoneSnapshot(
      String phase,
      boolean readyForBuild,
      int buildCapability,
      int motivationScore,
      int logicScore,
      List<String> blocking,
      List<String> goals,
      List<String> logicOutline,
      List<String> openQuestions,
      List<String> notes,
      List<String> resources,
      boolean resourcesPending,
      List<String> riskRegister,
      boolean riskPending,
      String locationHint,
      Pose playerPose,
      boolean locationPending,
      String locationQuality,
      Coverage coverage,
      boolean planAvailable,
      String planSummary,
      List<String> planSteps,
      String planStatus,
      List<String> planPendingReasons,
      List<String> modHooks) {
    this.phase = phase;
    this.readyForBuild = readyForBuild;
    this.buildCapability = buildCapability;
    this.motivationScore = motivationScore;
    this.logicScore = logicScore;
    this.blocking = blocking;
    this.goals = goals;
    this.logicOutline = logicOutline;
    this.openQuestions = openQuestions;
    this.notes = notes;
    this.resources = resources;
    this.resourcesPending = resourcesPending;
    this.riskRegister = riskRegister;
    this.riskPending = riskPending;
    this.locationHint = locationHint;
    this.playerPose = playerPose;
    this.locationPending = locationPending;
    this.locationQuality = locationQuality;
    this.coverage = coverage;
    this.planAvailable = planAvailable;
    this.planSummary = planSummary;
    this.planSteps = planSteps;
    this.planStatus = planStatus;
    this.planPendingReasons = planPendingReasons;
    this.modHooks = modHooks;
  }

  public static CityPhoneSnapshot fromJson(JsonObject state) {
    String phase = asString(state.get("phase"), "unknown");
    boolean ready = asBoolean(state.get("ready_for_build"));
    int buildCapability = asInt(state.get("build_capability"), 0);
    int motivationScore = asInt(state.get("motivation_score"), 0);
    int logicScore = asInt(state.get("logic_score"), 0);
    List<String> blocking = asList(state.get("blocking"));

    JsonObject panels = asObject(state.get("panels"));
    JsonObject vision = panels != null ? asObject(panels.get("vision")) : null;
    JsonObject resources = panels != null ? asObject(panels.get("resources")) : null;
    JsonObject location = panels != null ? asObject(panels.get("location")) : null;
    JsonObject plan = panels != null ? asObject(panels.get("plan")) : null;

    List<String> goals = vision != null ? asList(vision.get("goals")) : Collections.emptyList();
    List<String> logicOutline = vision != null ? asList(vision.get("logic_outline")) : Collections.emptyList();
    List<String> openQuestions = vision != null ? asList(vision.get("open_questions")) : Collections.emptyList();
    List<String> notes = vision != null ? asList(vision.get("notes")) : Collections.emptyList();
    Coverage coverage = Coverage.fromJson(vision != null ? asObject(vision.get("coverage")) : null);

    List<String> resourceItems = resources != null ? asList(resources.get("items")) : Collections.emptyList();
    boolean resourcesPending = resources != null && asBoolean(resources.get("pending"));
    List<String> riskRegister = resources != null ? asList(resources.get("risk_register")) : Collections.emptyList();
    boolean riskPending = resources != null && asBoolean(resources.get("risk_pending"));

    String locationHint = location != null ? asString(location.get("location_hint"), null) : null;
    Pose pose = location != null ? Pose.fromJson(asObject(location.get("player_pose"))) : null;
    boolean locationPending = location != null && asBoolean(location.get("pending"));
    String locationQuality = location != null ? asString(location.get("location_quality"), null) : null;

    boolean planAvailable = plan != null && asBoolean(plan.get("available"));
    String planSummary = plan != null ? asString(plan.get("summary"), null) : null;
    List<String> planSteps = plan != null ? asList(plan.get("steps")) : Collections.emptyList();
    String planStatus = plan != null
      ? normaliseStatus(asString(plan.get("status"), "pending"))
      : normaliseStatus("pending");
    List<String> pendingReasons = plan != null ? asList(plan.get("pending_reasons")) : Collections.emptyList();
    List<String> modHooks = plan != null ? asList(plan.get("mod_hooks")) : Collections.emptyList();

    return new CityPhoneSnapshot(
        phase,
        ready,
        buildCapability,
        motivationScore,
        logicScore,
        blocking,
        goals,
        logicOutline,
        openQuestions,
        notes,
        resourceItems,
        resourcesPending,
        riskRegister,
        riskPending,
        locationHint,
        pose,
        locationPending,
        locationQuality,
        coverage,
        planAvailable,
        planSummary,
        planSteps,
        planStatus,
        pendingReasons,
        modHooks);
  }

  private static String asString(JsonElement element, String fallback) {
    if (element == null || element.isJsonNull()) {
      return fallback;
    }
    return element.getAsString();
  }

  private static boolean asBoolean(JsonElement element) {
    if (element == null || element.isJsonNull()) {
      return false;
    }
    return element.getAsBoolean();
  }

  private static int asInt(JsonElement element, int fallback) {
    if (element == null || element.isJsonNull()) {
      return fallback;
    }
    try {
      return element.getAsInt();
    } catch (Exception ex) {
      return fallback;
    }
  }

  private static List<String> asList(JsonElement element) {
    if (element == null || element.isJsonNull() || !element.isJsonArray()) {
      return Collections.emptyList();
    }
    List<String> values = new ArrayList<>();
    element.getAsJsonArray().forEach(entry -> values.add(entry.getAsString()));
    return values;
  }

  private static JsonObject asObject(JsonElement element) {
    if (element == null || element.isJsonNull()) {
      return null;
    }
    if (!element.isJsonObject()) {
      return null;
    }
    return element.getAsJsonObject();
  }

  private static String normaliseStatus(String value) {
    if (value == null) {
      return "未知";
    }
    String key = value.trim().toLowerCase();
    switch (key) {
      case "completed":
        return "已完成";
      case "running":
        return "执行中";
      case "queued":
        return "已入队";
      case "blocked":
        return "受阻";
      case "pending":
        return "待处理";
      default:
        return value;
    }
  }

  public static final class Pose {
    public final String world;
    public final double x;
    public final double y;
    public final double z;
    public final float yaw;
    public final float pitch;

    private Pose(String world, double x, double y, double z, float yaw, float pitch) {
      this.world = world;
      this.x = x;
      this.y = y;
      this.z = z;
      this.yaw = yaw;
      this.pitch = pitch;
    }

    public static Pose fromJson(JsonObject json) {
      if (json == null) {
        return null;
      }
      String world = json.has("world") && !json.get("world").isJsonNull()
          ? json.get("world").getAsString()
          : "world";
      double x = json.has("x") ? json.get("x").getAsDouble() : 0.0D;
      double y = json.has("y") ? json.get("y").getAsDouble() : 0.0D;
      double z = json.has("z") ? json.get("z").getAsDouble() : 0.0D;
      float yaw = json.has("yaw") ? json.get("yaw").getAsFloat() : 0.0F;
      float pitch = json.has("pitch") ? json.get("pitch").getAsFloat() : 0.0F;
      return new Pose(world, x, y, z, yaw, pitch);
    }
  }

  public static final class Coverage {
    public final boolean logicOutline;
    public final boolean worldConstraints;
    public final boolean resourceLedger;
    public final boolean successCriteria;
    public final boolean riskRegister;

    private Coverage(
        boolean logicOutline,
        boolean worldConstraints,
        boolean resourceLedger,
        boolean successCriteria,
        boolean riskRegister) {
      this.logicOutline = logicOutline;
      this.worldConstraints = worldConstraints;
      this.resourceLedger = resourceLedger;
      this.successCriteria = successCriteria;
      this.riskRegister = riskRegister;
    }

    public static Coverage fromJson(JsonObject json) {
      if (json == null) {
        return new Coverage(false, false, false, false, false);
      }
      return new Coverage(
          asBoolean(json.get("logic_outline")),
          asBoolean(json.get("world_constraints")),
          asBoolean(json.get("resource_ledger")),
          asBoolean(json.get("success_criteria")),
          asBoolean(json.get("risk_register")));
    }
  }
}
