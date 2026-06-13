"""make_event: provenance/dataset tagging and optional geo."""

from __future__ import annotations

from app.ecs import make_event


def _base(**kw):
    defaults = dict(
        event_id="evt-1", timestamp="2026-06-14T00:00:00Z",
        category="network", action="network_connection", outcome="unknown",
        severity="low", module="netflow", message="hi",
    )
    defaults.update(kw)
    return make_event(**defaults)


def test_defaults_to_live_with_no_labels():
    evt = _base()
    assert "labels" not in evt
    assert "dataset" not in evt["event"]


def test_simulated_provenance_sets_labels():
    evt = _base(provenance="simulated", dataset="simulator.attack")
    assert evt["labels"] == {"provenance": "simulated"}
    assert evt["event"]["dataset"] == "simulator.attack"


def test_live_dataset_set_without_labels():
    evt = _base(dataset="host.network")
    assert evt["event"]["dataset"] == "host.network"
    assert "labels" not in evt


def test_geo_omitted_when_no_country():
    evt = _base(source_ip="10.0.0.5")
    assert evt["source"] == {"ip": "10.0.0.5"}


def test_geo_present_when_country_and_coords_given():
    evt = _base(source_ip="1.2.3.4", source_country="China",
                source_lat=35.0, source_lon=104.0)
    assert evt["source"]["geo"]["country_name"] == "China"
    assert evt["source"]["geo"]["location"] == {"lat": 35.0, "lon": 104.0}


def test_no_source_block_when_no_ip():
    evt = _base()
    assert "source" not in evt
