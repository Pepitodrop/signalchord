from __future__ import annotations

import base64
import binascii
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine import (
    DIALECT_VERSION,
    INPUTS,
    analyze_ir,
    capabilities,
    compile_notes,
    decompile,
    default_policy_ir,
    encode_midi,
    execute,
    ir_sha256,
    parse_assembly,
    parse_midi,
    serialize_ir,
)

app = FastAPI(title="SignalChord Velato Engine", version="1.1.0")
DEFAULT_POLICY_PATH = Path("/workspace/velato/programs/default-watchlist-novelty-v1.mid")


class MidiRequest(BaseModel):
    midi_base64: str = Field(min_length=4, max_length=180_000)


class AssemblyRequest(BaseModel):
    assembly: str = Field(min_length=1, max_length=128_000)
    root_note: int = Field(default=60, ge=0, le=116)


class SimulationRequest(BaseModel):
    inputs: dict[str, float]
    midi_base64: str | None = Field(default=None, max_length=180_000)
    assembly: str | None = Field(default=None, max_length=128_000)


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


def compile_assembly(source: str):
    try:
        return parse_assembly(source)
    except ValueError as error:
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
    return {"status": "ok", "version": "1.1.0", "dialect_version": DIALECT_VERSION}


@app.get("/v1/capabilities")
def get_capabilities() -> dict[str, object]:
    return capabilities()


@app.post("/v1/validate")
def validate_program(request: MidiRequest) -> dict[str, object]:
    source = decode_midi(request.midi_base64)
    notes, ir = compile_source(source)
    analysis = analyze_ir(ir)
    return {
        "valid": True,
        "compiler_version": DIALECT_VERSION,
        "note_count": len(notes),
        "instruction_count": len(ir),
        "ir_sha256": ir_sha256(ir),
        "source_sha256": sha256(source).hexdigest(),
        "analysis": analysis.model_dump(),
        "ir": serialize_ir(ir),
        "decompiled": decompile(ir),
    }


@app.post("/v1/assemble")
def assemble_program(request: AssemblyRequest) -> dict[str, object]:
    ir = compile_assembly(request.assembly)
    try:
        midi = encode_midi(ir, root_note=request.root_note)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "valid": True,
        "compiler_version": DIALECT_VERSION,
        "midi_base64": base64.b64encode(midi).decode(),
        "midi_sha256": sha256(midi).hexdigest(),
        "ir_sha256": ir_sha256(ir),
        "analysis": analyze_ir(ir).model_dump(),
        "ir": serialize_ir(ir),
        "decompiled": decompile(ir),
    }


@app.post("/v1/simulate")
def simulate(request: SimulationRequest) -> dict[str, object]:
    if request.midi_base64 and request.assembly:
        raise HTTPException(status_code=422, detail="provide either MIDI or assembly, not both")
    if request.midi_base64:
        _, ir = compile_source(decode_midi(request.midi_base64))
        execution_engine = "velato-midi"
    elif request.assembly:
        ir = compile_assembly(request.assembly)
        execution_engine = "velato-assembly"
    elif DEFAULT_POLICY_PATH.exists():
        _, ir = compile_source(DEFAULT_POLICY_PATH.read_bytes())
        execution_engine = "velato-midi-default"
    else:
        ir = default_policy_ir()
        execution_engine = "fallback-rules"
    inputs = validate_inputs(request.inputs)
    try:
        result = execute(ir, inputs)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.model_dump() | {
        "execution_engine": execution_engine,
        "compiler_version": DIALECT_VERSION,
        "ir_sha256": ir_sha256(ir),
        "analysis": analyze_ir(ir).model_dump(),
        "decompiled": decompile(ir),
    }
