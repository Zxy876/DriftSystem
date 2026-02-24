from app.core.ideal_city.narrative.factory import NarrativeEngineFactory
from app.core.ideal_city.narrative.modes import NarrativeMode


def test_narrative_factory_supports_declared_modes():
    reunion = NarrativeEngineFactory.create(NarrativeMode.REUNION)
    ideal_city = NarrativeEngineFactory.create(NarrativeMode.IDEAL_CITY)

    assert reunion.__class__.__name__ == "ReunionNarrativeEngine"
    assert ideal_city.__class__.__name__ == "IdealCityNarrativeEngine"


def test_narrative_factory_rejects_future_modes_for_now():
    for mode in (NarrativeMode.EXPERIMENTAL, NarrativeMode.CINEMATIC):
        try:
            NarrativeEngineFactory.create(mode)
        except ValueError:
            continue
        raise AssertionError(f"Mode {mode.value} should not be silently accepted")
