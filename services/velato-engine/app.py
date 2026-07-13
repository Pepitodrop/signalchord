from __future__ import annotations

import base64
import binascii
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine import (
    INPUTS,
    compile_notes,
    decompile,
    default_policy_ir,
    execute,
    ir_sha256,
    parse_midi,
    serialize_ir,
)

app = FastAPI(title="SignalChord Velato Engine", version="1.0.0")
DEFAULT_POLICY_PATH = Path("/workspace/velato/programs/default-watchlist-novelty-v1.mid")


class MidiRequest(BaseModel):
    midi_base64: str = Field(min_length=4, max_length=180_000)


class SimulationRequest(BaseModel):
    inputs: dict[str, float]
    midi_base64: str | None = Field(default=None, max_length=180_000)


def decode_midi(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="invalid MIDI base64") from error


def compile_source(source: bytes):
    try:
        notes = parse_midi(source)
        ir = compile_notes(notes)
        return notes, ir
    except (ValueError, OSError, EOFError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def validate_inputs(inputs: dict[str, float]) -> dict[str, float]:
    missing = [name for name in INPUTS if name not in inputs]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing inputs: {', '.join(missing)}")
    normalized: dict[str, float] = {}
    for name in INPUTS:
        value = float(inputs[name])
        if value < 0 or value > 10_000:
            raise HTTPException(status_code=422, detail=f"input {name} is outside allowed range")
        normalized[name] = value
    return normalized


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/v1/validate")
def validate_program(request: MidiRequest) -> dict[str, object]:
    source = decode_midi(request.midi_base64)
    notes, ir = compile_source(source)
    return {
        "valid": True,
        "compiler_version": "signalchord-velato-1.0.0",
        "note_count": len(notes),
        "instruction_count": len(ir),
        "ir_sha256": ir_sha256(ir),
        "ir": serialize_ir(ir),
        "decompiled": decompile(ir),
    }


@app.post("/v1/simulate")
def simulate(request: SimulationRequest) -> dict[str, object]:
    if request.midi_base64:
        _, ir = compile_source(decode_midi(request.midi_base64))
        execution_engine = "velato-midi"
    elif DEFAULT_POLICY_PATH.exists():
        _, ir = compile_source(DEFAULT_POLICY_PATH.read_bytes())
        execution_engine = "velato-midi-default"
    else:
        ir = default_policy_ir()
        execution_engine = "fallback-rules"
    inputs = validate_inputs(request.inputs)
    result = execute(ir, inputs)
    return result.model_dump() | {
        "execution_engine": execution_engine,
        "ir_sha256": ir_sha256(ir),
        "decompiled": decompile(ir),
    }
