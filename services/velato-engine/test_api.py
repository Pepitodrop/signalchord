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


def policy_inputs() -> dict[str, float]:
    return {name: 0.5 for name in module.INPUTS} | {
        "watchlist_match": 1.0,
        "novelty": 0.8,
        "entity_relevance": 0.9,
        "source_diversity": 0.4,
    }


def test_validate_and_simulate_checked_in_policy() -> None:
    policy = (
        Path(__file__).parents[2]
        / "velato"
        / "programs"
        / "default-watchlist-novelty-v1.mid"
    )
    encoded = base64.b64encode(policy.read_bytes()).decode()
    validation = client.post("/v1/validate", json={"midi_base64": encoded})
    assert validation.status_code == 200
    payload = validation.json()
    assert payload["instruction_count"] > 1
    assert payload["compiler_version"] == "signalchord-velato-1.1.0"
    assert payload["analysis"]["max_stack_depth"] == 3
    simulation = client.post(
        "/v1/simulate", json={"midi_base64": encoded, "inputs": policy_inputs()}
    )
    assert simulation.status_code == 200
    assert simulation.json()["alert_score"] == 84


def test_capabilities_expose_all_instruction_banks() -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dialect_version"] == "signalchord-velato-1.1.0"
    assert set(payload["instruction_banks"]) == {"0", "1", "2", "3"}
    assert payload["instruction_banks"]["1"]["2"] == "DIV"
    assert payload["instruction_banks"]["3"]["5"] == "STORE_LOCAL"


def test_assemble_and_simulate_extended_policy() -> None:
    assembly = """
    PUSH_CONST 9
    SQRT
    PUSH_CONST 30
    MUL
    STORE_SCORE
    PUSH_CONST 3
    STORE_SEVERITY
    PUSH_CONST 2
    STORE_ROUTE
    PUSH_CONST 0
    STORE_SUPPRESS
    HALT
    """
    assembled = client.post(
        "/v1/assemble", json={"assembly": assembly, "root_note": 60}
    )
    assert assembled.status_code == 200
    midi_base64 = assembled.json()["midi_base64"]
    validation = client.post("/v1/validate", json={"midi_base64": midi_base64})
    assert validation.status_code == 200
    simulation = client.post(
        "/v1/simulate", json={"midi_base64": midi_base64, "inputs": policy_inputs()}
    )
    assert simulation.status_code == 200
    assert simulation.json()["alert_score"] == 90
    assert simulation.json()["severity_code"] == 3


def test_simulation_rejects_multiple_sources() -> None:
    response = client.post(
        "/v1/simulate",
        json={
            "midi_base64": "AAAA",
            "assembly": "HALT",
            "inputs": policy_inputs(),
        },
    )
    assert response.status_code == 422


def test_invalid_midi_is_rejected() -> None:
    response = client.post(
        "/v1/validate", json={"midi_base64": base64.b64encode(b"bad").decode()}
    )
    assert response.status_code == 422
