import base64
import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

service_dir = Path(__file__).parent
sys.path.insert(0, str(service_dir))
spec = importlib.util.spec_from_file_location("velato_api", service_dir / "app.py")
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
client = TestClient(module.app)


def test_validate_and_simulate_checked_in_policy() -> None:
    policy = Path(__file__).parents[2] / "velato" / "programs" / "default-watchlist-novelty-v1.mid"
    encoded = base64.b64encode(policy.read_bytes()).decode()
    validation = client.post("/v1/validate", json={"midi_base64": encoded})
    assert validation.status_code == 200
    assert validation.json()["instruction_count"] > 1
    inputs = {name: 0.5 for name in module.INPUTS} | {
        "watchlist_match": 1.0,
        "novelty": 0.8,
        "entity_relevance": 0.9,
        "source_diversity": 0.4,
    }
    simulation = client.post("/v1/simulate", json={"midi_base64": encoded, "inputs": inputs})
    assert simulation.status_code == 200
    assert simulation.json()["alert_score"] == 84


def test_invalid_midi_is_rejected() -> None:
    response = client.post("/v1/validate", json={"midi_base64": base64.b64encode(b"bad").decode()})
    assert response.status_code == 422
