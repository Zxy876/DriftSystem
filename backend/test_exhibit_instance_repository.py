from pathlib import Path

from app.core.story.exhibit_instance_repository import ExhibitInstance, ExhibitInstanceRepository


def test_save_and_list_instances(tmp_path: Path) -> None:
    repo = ExhibitInstanceRepository(tmp_path / "instances")
    instance = ExhibitInstance(
        scenario_id="CrystalTech",
        exhibit_id="amethyst",
        level_id="Crystal_Level_01",
        snapshot_type="world_patch",
        payload={"mc": {"fill": "0 0 0 1 1 1 stone"}},
        created_by="archivist",
        title="紫水晶展台",
    )

    repo.save_instance(instance)

    stored = repo.list_instances(scenario_id="CrystalTech")
    assert len(stored) == 1
    assert stored[0].instance_id == instance.instance_id
    assert stored[0].payload.get("mc") == {"fill": "0 0 0 1 1 1 stone"}

    level_instances = repo.get_instances_for_level(
        "Crystal_Level_01",
        scenario_id="CrystalTech",
        exhibit_id="amethyst",
    )
    assert len(level_instances) == 1
    assert level_instances[0].instance_id == instance.instance_id

    index_file = tmp_path / "instances" / "CrystalTech" / "index.json"
    assert index_file.exists()
