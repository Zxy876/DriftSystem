package com.driftmc.cityphone;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

/** Snapshot parsed from the curatorial CityPhone backend payload. */
public final class CityPhoneSnapshot {

  public final String phase;
  public final List<String> cityInterpretation;
  public final List<String> unknowns;
  public final List<String> historyEntries;
  public final Appendix appendix;
  public final ExhibitMode exhibitMode;
  public final Narrative narrative;

  private CityPhoneSnapshot(
      String phase,
      List<String> cityInterpretation,
      List<String> unknowns,
      List<String> historyEntries,
      Appendix appendix,
      ExhibitMode exhibitMode,
      Narrative narrative) {
    this.phase = phase;
    this.cityInterpretation = cityInterpretation;
    this.unknowns = unknowns;
    this.historyEntries = historyEntries;
    this.appendix = appendix;
    this.exhibitMode = exhibitMode;
    this.narrative = narrative;
  }

  public static CityPhoneSnapshot fromJson(JsonObject state) {
    String phase = asString(state.get("phase"), "unknown");
    List<String> interpretation = asImmutableList(state.get("city_interpretation"));
    List<String> unknowns = asImmutableList(state.get("unknowns"));
    List<String> history = asImmutableList(state.get("history_entries"));

    Appendix appendix = Appendix.fromJson(asObject(state.get("appendix")));
    ExhibitMode exhibitMode = ExhibitMode.fromJson(asObject(state.get("exhibit_mode")));
    Narrative narrative = Narrative.fromJson(asObject(state.get("narrative")));

    return new CityPhoneSnapshot(
        phase,
        interpretation,
        unknowns,
        history,
        appendix,
        exhibitMode,
        narrative);
  }

  private static List<String> asImmutableList(JsonElement element) {
    return Collections.unmodifiableList(asList(element));
  }

  private static List<String> asList(JsonElement element) {
    if (element == null || element.isJsonNull() || !element.isJsonArray()) {
      return Collections.emptyList();
    }
    List<String> values = new ArrayList<>();
    element.getAsJsonArray().forEach(item -> {
      if (item == null || item.isJsonNull()) {
        return;
      }
      String text = item.getAsString();
      if (text == null) {
        return;
      }
      text = text.trim();
      if (!text.isEmpty()) {
        values.add(text);
      }
    });
    return values;
  }

  private static boolean asBoolean(JsonElement element) {
    return element != null && !element.isJsonNull() && element.getAsBoolean();
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

  private static JsonObject asObject(JsonElement element) {
    if (element == null || element.isJsonNull()) {
      return null;
    }
    if (!element.isJsonObject()) {
      return null;
    }
    return element.getAsJsonObject();
  }

  private static String asString(JsonElement element, String fallback) {
    if (element == null || element.isJsonNull()) {
      return fallback;
    }
    String text = element.getAsString();
    if (text == null) {
      return fallback;
    }
    text = text.trim();
    return text.isEmpty() ? fallback : text;
  }

  public static final class Appendix {
    public final Vision vision;
    public final Resources resources;
    public final Location location;
    public final Plan plan;

    private Appendix(Vision vision, Resources resources, Location location, Plan plan) {
      this.vision = vision;
      this.resources = resources;
      this.location = location;
      this.plan = plan;
    }

    static Appendix fromJson(JsonObject json) {
      if (json == null) {
        return new Appendix(new Vision(), new Resources(), new Location(), new Plan());
      }
      Vision vision = Vision.fromJson(asObject(json.get("vision")));
      Resources resources = Resources.fromJson(asObject(json.get("resources")));
      Location location = Location.fromJson(asObject(json.get("location")));
      Plan plan = Plan.fromJson(asObject(json.get("plan")));
      return new Appendix(vision, resources, location, plan);
    }
  }

  public static final class Vision {
    public final List<String> goals;
    public final List<String> logicOutline;
    public final List<String> openQuestions;
    public final List<String> notes;
    public final Coverage coverage;

    private Vision() {
      this(Collections.emptyList(), Collections.emptyList(), Collections.emptyList(), Collections.emptyList(), Coverage.empty());
    }

    private Vision(
        List<String> goals,
        List<String> logicOutline,
        List<String> openQuestions,
        List<String> notes,
        Coverage coverage) {
      this.goals = goals;
      this.logicOutline = logicOutline;
      this.openQuestions = openQuestions;
      this.notes = notes;
      this.coverage = coverage;
    }

    static Vision fromJson(JsonObject json) {
      if (json == null) {
        return new Vision();
      }
      return new Vision(
          asImmutableList(json.get("goals")),
          asImmutableList(json.get("logic_outline")),
          asImmutableList(json.get("open_questions")),
          asImmutableList(json.get("notes")),
          Coverage.fromJson(asObject(json.get("coverage"))));
    }
  }

  public static final class Resources {
    public final List<String> items;
    public final boolean pending;
    public final List<String> riskRegister;
    public final boolean riskPending;

    private Resources() {
      this(Collections.emptyList(), false, Collections.emptyList(), false);
    }

    private Resources(List<String> items, boolean pending, List<String> riskRegister, boolean riskPending) {
      this.items = items;
      this.pending = pending;
      this.riskRegister = riskRegister;
      this.riskPending = riskPending;
    }

    static Resources fromJson(JsonObject json) {
      if (json == null) {
        return new Resources();
      }
      return new Resources(
          asImmutableList(json.get("items")),
          asBoolean(json.get("pending")),
          asImmutableList(json.get("risk_register")),
          asBoolean(json.get("risk_pending")));
    }
  }

  public static final class Location {
    public final String locationHint;
    public final Pose playerPose;
    public final boolean pending;
    public final String locationQuality;

    private Location() {
      this(null, null, false, null);
    }

    private Location(String locationHint, Pose playerPose, boolean pending, String locationQuality) {
      this.locationHint = locationHint;
      this.playerPose = playerPose;
      this.pending = pending;
      this.locationQuality = locationQuality;
    }

    static Location fromJson(JsonObject json) {
      if (json == null) {
        return new Location();
      }
      String hint = asString(json.get("location_hint"), null);
      Pose pose = Pose.fromJson(asObject(json.get("player_pose")));
      boolean pending = asBoolean(json.get("pending"));
      String quality = asString(json.get("location_quality"), null);
      return new Location(hint, pose, pending, quality);
    }
  }

  public static final class Plan {
    public final boolean available;
    public final String summary;
    public final List<String> steps;
    public final String status;
    public final List<String> pendingReasons;
    public final List<String> modHooks;

    private Plan() {
      this(false, null, Collections.emptyList(), "pending", Collections.emptyList(), Collections.emptyList());
    }

    private Plan(
        boolean available,
        String summary,
        List<String> steps,
        String status,
        List<String> pendingReasons,
        List<String> modHooks) {
      this.available = available;
      this.summary = summary;
      this.steps = steps;
      this.status = status;
      this.pendingReasons = pendingReasons;
      this.modHooks = modHooks;
    }

    static Plan fromJson(JsonObject json) {
      if (json == null) {
        return new Plan();
      }
      return new Plan(
          asBoolean(json.get("available")),
          asString(json.get("summary"), null),
          asImmutableList(json.get("steps")),
          asString(json.get("status"), "pending"),
          asImmutableList(json.get("pending_reasons")),
          asImmutableList(json.get("mod_hooks")));
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

    static Coverage fromJson(JsonObject json) {
      if (json == null) {
        return empty();
      }
      return new Coverage(
          asBoolean(json.get("logic_outline")),
          asBoolean(json.get("world_constraints")),
          asBoolean(json.get("resource_ledger")),
          asBoolean(json.get("success_criteria")),
          asBoolean(json.get("risk_register")));
    }

    static Coverage empty() {
      return new Coverage(false, false, false, false, false);
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

    static Pose fromJson(JsonObject json) {
      if (json == null) {
        return null;
      }
      String world = asString(json.get("world"), null);
      double x = json.has("x") ? json.get("x").getAsDouble() : 0.0D;
      double y = json.has("y") ? json.get("y").getAsDouble() : 0.0D;
      double z = json.has("z") ? json.get("z").getAsDouble() : 0.0D;
      float yaw = json.has("yaw") ? json.get("yaw").getAsFloat() : 0.0F;
      float pitch = json.has("pitch") ? json.get("pitch").getAsFloat() : 0.0F;
      return new Pose(world, x, y, z, yaw, pitch);
    }
  }

  public static final class ExhibitMode {
    public final String mode;
    public final String label;
    public final List<String> description;

    private ExhibitMode(String mode, String label, List<String> description) {
      this.mode = mode;
      this.label = label;
      this.description = description;
    }

    static ExhibitMode fromJson(JsonObject json) {
      if (json == null) {
        return new ExhibitMode("archive", "看展模式 · Archive", Collections.emptyList());
      }
      return new ExhibitMode(
          asString(json.get("mode"), "archive"),
          asString(json.get("label"), asString(json.get("mode"), "archive")),
          asImmutableList(json.get("description")));
    }
  }

  public static final class Narrative {
    public final String title;
    public final String timeframe;
    public final String mode;
    public final String lastEvent;
    public final List<Section> sections;

    private Narrative(String title, String timeframe, String mode, String lastEvent, List<Section> sections) {
      this.title = title;
      this.timeframe = timeframe;
      this.mode = mode;
      this.lastEvent = lastEvent;
      this.sections = sections;
    }

    static Narrative fromJson(JsonObject json) {
      if (json == null) {
        return new Narrative(null, null, "archive", null, Collections.emptyList());
      }
      String title = asString(json.get("title"), null);
      String timeframe = asString(json.get("timeframe"), null);
      String mode = asString(json.get("mode"), "archive");
      String lastEvent = asString(json.get("last_event"), null);
      List<Section> sections = new ArrayList<>();
      if (json.has("sections") && json.get("sections").isJsonArray()) {
        for (JsonElement element : json.get("sections").getAsJsonArray()) {
          JsonObject section = asObject(element);
          if (section == null) {
            continue;
          }
          sections.add(Section.fromJson(section));
        }
      }
      return new Narrative(title, timeframe, mode, lastEvent, Collections.unmodifiableList(sections));
    }
  }

  public static final class Section {
    public final String slot;
    public final String title;
    public final List<String> body;
    public final String accent;

    private Section(String slot, String title, List<String> body, String accent) {
      this.slot = slot;
      this.title = title;
      this.body = body;
      this.accent = accent;
    }

    static Section fromJson(JsonObject json) {
      String slot = asString(json.get("slot"), "section");
      String title = asString(json.get("title"), CityPhoneLocalization.text("ui.narrative.fallback_title"));
      List<String> body = asImmutableList(json.get("body"));
      String accent = asString(json.get("accent"), null);
      return new Section(slot, title, body, accent);
    }
  }
}
