"""Websocket API tests (the data source of the sidebar panel and the card)."""

from __future__ import annotations

import base64
import os

from custom_components.curing_chamber.const import DOMAIN
from homeassistant.core import HomeAssistant

MANUAL_WEIGHT = "number.test_chamber_manual_weight"
PHOTO = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xd9").decode()


async def _setup(hass, config_entry, seed_states):
    seed_states()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][config_entry.entry_id]


async def _call(client, msg_type: str, **data):
    """Send a command and return its result, stashing subscription events aside.

    A mutation refreshes the coordinator *before* answering, so with an active
    subscription the pushed event arrives ahead of the result message.
    """
    await client.send_json_auto_id({"type": f"{DOMAIN}/{msg_type}", **data})
    while True:
        msg = await client.receive_json()
        if msg.get("type") == "event":
            client.events = [*getattr(client, "events", []), msg["event"]]
            continue
        return msg


async def _create_batch(client, entry_id: str, **data):
    payload = {"name": "Coppa #1", "reference_weight": 1000.0, "target_loss_pct": 30.0}
    payload.update(data)
    msg = await _call(client, "batch/create", entry_id=entry_id, **payload)
    assert msg["success"], msg
    return msg["result"]


async def test_chambers_and_state(
    hass: HomeAssistant, config_entry, seed_states, hass_ws_client
) -> None:
    await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)

    msg = await _call(client, "chambers")
    assert msg["success"]
    assert msg["result"] == [
        {
            "entry_id": config_entry.entry_id,
            "name": "Test Chamber",
            "device_id": msg["result"][0]["device_id"],
            "has_scale": False,
        }
    ]
    assert msg["result"][0]["device_id"]

    msg = await _call(client, "state", entry_id=config_entry.entry_id)
    assert msg["success"]
    state = msg["result"]
    assert state["name"] == "Test Chamber"
    assert state["temp"] == 13.0
    assert state["program"]["status"] == "idle"
    assert state["program"]["phases"] == []
    assert state["kind"] == "charcuterie"
    assert state["program"]["ramp_remaining"] is None
    assert state["batches"] == []
    assert state["entities"]["manual_weight"] == MANUAL_WEIGHT
    assert state["entities"]["regulation_switch"] == "switch.test_chamber_regulation"
    assert state["actuators"] == {"cool": False}

    msg = await _call(client, "state", entry_id="nope")
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def test_subscribe_pushes_live_state(
    hass: HomeAssistant, config_entry, seed_states, hass_ws_client
) -> None:
    await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)
    entry_id = config_entry.entry_id

    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe", "entry_id": entry_id})
    msg = await client.receive_json()
    assert msg["success"]
    sub_id = msg["id"]
    first = await client.receive_json()
    assert first["type"] == "event" and first["id"] == sub_id
    assert first["event"]["active_batch_count"] == 0

    # A websocket weigh-in refreshes the coordinator, which pushes a new state
    # to every subscriber before the command's own result is sent.
    batch = await _create_batch(client, entry_id)
    assert any(e["active_batch_count"] == 1 for e in client.events)
    msg = await _call(client, "weigh_in", entry_id=entry_id, batch_id=batch["id"], weight=900.0)
    assert msg["success"]
    assert msg["result"]["last_weight"] == 900.0
    assert msg["result"]["samples"][0]["weight"] == 900.0
    pushed = [e for e in client.events if e["batches"] and e["batches"][0]["last_weight"] == 900.0]
    assert pushed
    assert pushed[-1]["reference_batch_id"] == batch["id"]
    assert "samples" not in pushed[-1]["batches"][0]


async def test_subscribe_chambers_pushes_on_load_and_unload(
    hass: HomeAssistant, config_entry, seed_states, hass_ws_client
) -> None:
    await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe_chambers"})
    msg = await client.receive_json()
    assert msg["success"]
    sub_id = msg["id"]
    first = await client.receive_json()
    assert first["type"] == "event" and first["id"] == sub_id
    assert [c["entry_id"] for c in first["event"]] == [config_entry.entry_id]
    assert first["event"][0]["name"] == "Test Chamber"

    # Unloading the last chamber pushes an empty list...
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    gone = await client.receive_json()
    assert gone["type"] == "event" and gone["event"] == []

    # ...and loading it again pushes it back (same path as adding a chamber).
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    back = await client.receive_json()
    assert back["type"] == "event"
    assert [c["entry_id"] for c in back["event"]] == [config_entry.entry_id]


async def test_batch_listing_and_sensor_attributes(
    hass: HomeAssistant, config_entry, seed_states, hass_ws_client
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)
    entry_id = config_entry.entry_id
    first = await _create_batch(client, entry_id, name="A")
    second = await _create_batch(client, entry_id, name="B")
    await _call(client, "weigh_in", entry_id=entry_id, batch_id=first["id"], weight=950.0)

    msg = await _call(
        client, "batch/set_status", entry_id=entry_id, batch_id=second["id"], status="archived"
    )
    assert msg["success"] and msg["result"]["status"] == "archived"

    msg = await _call(client, "batches", entry_id=entry_id)
    assert [b["id"] for b in msg["result"]] == [first["id"]]
    assert "samples" not in msg["result"][0]
    assert msg["result"][0]["sample_count"] == 1

    msg = await _call(
        client, "batches", entry_id=entry_id, include_archived=True, with_samples=True
    )
    assert [b["id"] for b in msg["result"]] == [first["id"], second["id"]]
    assert msg["result"][0]["samples"][0]["weight"] == 950.0

    msg = await _call(client, "batch", entry_id=entry_id, batch_id=first["id"])
    assert msg["success"] and len(msg["result"]["samples"]) == 1
    msg = await _call(client, "batch", entry_id=entry_id, batch_id="ghost")
    assert msg["error"]["code"] == "not_found"

    # The sensor attribute stays light: no weigh-in history, no archived batches,
    # and it carries the entry_id the card needs to query the websocket API.
    state = hass.states.get("sensor.test_chamber_active_batches")
    assert state is not None
    assert state.attributes["entry_id"] == entry_id
    assert [b["id"] for b in state.attributes["batches"]] == [first["id"]]
    assert "samples" not in state.attributes["batches"][0]
    assert (
        "batches"
        in type(
            hass.data["entity_components"]["sensor"].get_entity(
                "sensor.test_chamber_active_batches"
            )
        )._unrecorded_attributes
    )

    # Re-activating an archived batch brings it back.
    msg = await _call(
        client, "batch/set_status", entry_id=entry_id, batch_id=second["id"], status="active"
    )
    assert msg["success"]
    assert coordinator.batches[second["id"]].status.value == "active"

    msg = await _call(client, "batch/set_reference", entry_id=entry_id, batch_id=second["id"])
    assert msg["success"]
    assert coordinator.store.reference_batch_id == second["id"]

    msg = await _call(client, "batch/delete", entry_id=entry_id, batch_id=second["id"])
    assert msg["result"] == {"deleted": True}
    assert second["id"] not in coordinator.batches


async def test_weigh_in_photo_lifecycle(
    hass: HomeAssistant, config_entry, seed_states, hass_ws_client
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)
    entry_id = config_entry.entry_id
    batch = await _create_batch(client, entry_id)

    msg = await _call(
        client,
        "weigh_in",
        entry_id=entry_id,
        batch_id=batch["id"],
        weight=980.0,
        timestamp=1_700_000_000.0,
        note="day 3",
        photo=PHOTO,
    )
    assert msg["success"], msg
    sample = msg["result"]["samples"][0]
    assert sample["note"] == "day 3"
    assert sample["photo_url"] == (
        f"/api/curing_chamber/photo/{entry_id}/{batch['id']}/1700000000.jpg"
    )
    path = coordinator.photo_path(batch["id"], "1700000000.jpg")
    assert os.path.isfile(path)
    assert ".storage" in path and "www" not in path
    assert msg["result"]["last_photo_url"] == sample["photo_url"]

    msg = await _call(
        client,
        "weigh_in/delete",
        entry_id=entry_id,
        batch_id=batch["id"],
        timestamp=1_700_000_000.0,
    )
    assert msg["success"], msg
    assert msg["result"]["samples"] == []
    assert not os.path.exists(path)

    msg = await _call(
        client, "weigh_in/delete", entry_id=entry_id, batch_id=batch["id"], timestamp=1.0
    )
    assert msg["error"]["code"] == "not_found"


async def test_program_editor_commands(
    hass: HomeAssistant, config_entry, seed_states, hass_ws_client
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)
    entry_id = config_entry.entry_id

    msg = await _call(client, "programs", entry_id=entry_id)
    presets = msg["result"]
    assert presets and all(p["builtin"] for p in presets)
    preset_id = presets[0]["id"]

    program = {
        "id": "my_coppa",
        "name": "My coppa",
        "phases": [
            {
                "name": "Drip",
                "target_temp": 20,
                "target_humidity": 75,
                "end_kind": "duration",
                "duration_hours": 24,
            },
            {
                "name": "Dry",
                "target_temp": 13,
                "target_humidity": 78,
                "end_kind": "weight_loss",
                "weight_loss_pct": 35,
                "duration_hours": 24 * 60,
            },
        ],
    }
    msg = await _call(client, "program/validate", entry_id=entry_id, program=program)
    assert msg["result"]["valid"] is True
    assert msg["result"]["errors"] == []

    msg = await _call(
        client,
        "program/validate",
        entry_id=entry_id,
        program={"id": "x", "name": "x", "phases": []},
    )
    assert msg["result"]["valid"] is False
    assert msg["result"]["errors"]

    msg = await _call(
        client, "program/save", entry_id=entry_id, program={**program, "id": preset_id}
    )
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"

    msg = await _call(client, "program/save", entry_id=entry_id, program=program)
    assert msg["success"], msg
    assert msg["result"]["program"]["id"] == "my_coppa"
    assert msg["result"]["program"]["builtin"] is False
    assert "my_coppa" in coordinator.store.programs

    msg = await _call(client, "programs", entry_id=entry_id)
    assert any(p["id"] == "my_coppa" and not p["builtin"] for p in msg["result"])

    msg = await _call(client, "program/delete", entry_id=entry_id, program_id="my_coppa")
    assert msg["result"] == {"deleted": True}
    msg = await _call(client, "program/delete", entry_id=entry_id, program_id=preset_id)
    assert msg["result"] == {"deleted": False}


async def test_program_import_command(
    hass: HomeAssistant, hass_ws_client, config_entry, seed_states
) -> None:
    coordinator = await _setup(hass, config_entry, seed_states)
    client = await hass_ws_client(hass)
    entry_id = config_entry.entry_id
    program = {
        "id": "ramped",
        "name": "Ramped",
        "category": "cheese",
        "phases": [
            {
                "name": "ripening",
                "target_temp": 12,
                "target_humidity": 90,
                "start_temp": 16,
                "ramp_hours": 24,
                "duration_hours": 200,
            },
        ],
    }
    payload = {"format": "curing_chamber/programs", "version": 1, "programs": [program]}

    msg = await _call(client, "program/import", entry_id=entry_id, programs=payload)
    assert msg["success"], msg
    assert msg["result"]["imported"] == ["ramped"]
    assert msg["result"]["skipped"] == []
    stored = coordinator.store.programs["ramped"]
    assert stored["category"] == "cheese"
    assert stored["phases"][0]["ramp_hours"] == 24.0

    msg = await _call(client, "program/import", entry_id=entry_id, programs=[program])
    assert msg["result"] == {"imported": [], "skipped": ["ramped"], "warnings": []}
    msg = await _call(
        client, "program/import", entry_id=entry_id, programs=[program], overwrite=True
    )
    assert msg["result"]["imported"] == ["ramped"]

    msg = await _call(client, "program/import", entry_id=entry_id, programs={"programs": []})
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"

    # The listing carries the category and ramp fields the panel editor needs.
    msg = await _call(client, "programs", entry_id=entry_id)
    mine = next(p for p in msg["result"] if p["id"] == "ramped")
    assert mine["category"] == "cheese"
    assert mine["phases"][0]["start_temp"] == 16.0
