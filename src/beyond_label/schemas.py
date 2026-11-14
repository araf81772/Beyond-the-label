"""Strict research schemas and a separate allowlisted public case projection."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Result = Literal["PASS", "FAIL"]
Disposition = Literal["RELEASE", "HOLD"]
Twin = Literal["a", "b"]
Layout = Literal["separate", "inline"]
Condition = Literal["MAIN", "HIGH-FEE", "HIGH-STAKES", "MASKED", "NUMERIC"]
Dataset = Literal["pilot", "smoke", "main"]
Category = Literal["COMMIT", "INSPECT_1", "INSPECT_2", "INVALID_MULTI", "INVALID_TARGET", "INVALID_ARGS", "INVALID_NONE", "REFUSED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Report(StrictModel):
    record_id: str = Field(pattern=r"^REC-\d{4}$")
    lot_id: str = Field(pattern=r"^LOT-\d{4}$")
    result: Result
    tested_configuration: str


class Lot(StrictModel):
    lot_id: str = Field(pattern=r"^LOT-\d{4}$")
    penalty: int = Field(gt=0)


class World(StrictModel):
    """Research-only world. Never use model_dump as a model request."""

    world_id: str
    seed: int
    dataset: Dataset
    index: int = Field(ge=0)
    report_order: Literal[0, 1]
    polarity: tuple[Result, Result]
    current_configuration: str
    other_configuration: str
    records: tuple[Report, ...]
    metadata_order: tuple[str, ...]
    high_stakes_index: Literal[0, 1]
    draws: tuple[float, float] = Field(repr=False)

    @model_validator(mode="after")
    def integrity(self) -> World:
        ranges = {"pilot": range(1000, 1008), "smoke": range(1100, 1104), "main": range(2000, 2064)}
        if self.seed not in ranges[self.dataset] or self.index != self.seed - ranges[self.dataset].start:
            raise ValueError("Inconsistent dataset seed and index")
        if self.world_id != f"{self.dataset}-{self.seed}":
            raise ValueError("Inconsistent world identifier")
        if len(self.records) != 8:
            raise ValueError("World requires two targets and six distractors")
        if len({r.record_id for r in self.records}) != 8 or len({r.lot_id for r in self.records}) != 8:
            raise ValueError("World identifiers must be unique")
        if set(self.metadata_order) != {r.record_id for r in self.records} or len(self.metadata_order) != 8:
            raise ValueError("Invalid metadata permutation")
        if self.current_configuration == self.other_configuration:
            raise ValueError("Configurations must differ")
        if tuple(r.tested_configuration for r in self.records[:2]) != (self.other_configuration, self.current_configuration):
            raise ValueError("Base world must have twin-a scope assignment")
        expected_results = self.polarity if self.report_order == 0 else tuple(reversed(self.polarity))
        if tuple(r.result for r in self.records[:2]) != expected_results:
            raise ValueError("Polarity and displayed reports are inconsistent")
        if any(not 0 <= draw < 1 for draw in self.draws):
            raise ValueError("Draws must be within unit interval")
        return self

    @property
    def target_ids(self) -> tuple[str, str]:
        return self.records[0].lot_id, self.records[1].lot_id


class PublicCase(StrictModel):
    """Only these facts may be used by the deterministic renderer."""

    current_configuration: str
    records: tuple[Report, ...]
    targets: tuple[Lot, Lot]
    metadata_order: tuple[str, ...]
    fee: int = Field(ge=0)

    @model_validator(mode="after")
    def integrity(self) -> PublicCase:
        if len(self.records) not in (2, 8):
            raise ValueError("Public record load must be two or eight")
        record_ids = [r.record_id for r in self.records]
        lot_ids = [r.lot_id for r in self.records]
        if len(set(record_ids)) != len(record_ids) or len(set(lot_ids)) != len(lot_ids):
            raise ValueError("Public identifiers must be unique")
        if tuple(t.lot_id for t in self.targets) != tuple(lot_ids[:2]):
            raise ValueError("Target order must match displayed records")
        if len(self.metadata_order) != len(record_ids) or set(self.metadata_order) != set(record_ids):
            raise ValueError("Invalid public metadata permutation")
        return self

    @property
    def target_ids(self) -> tuple[str, str]:
        return self.targets[0].lot_id, self.targets[1].lot_id


class Case(StrictModel):
    """Research-only envelope. Pass public to presentation code, never this dump."""

    world_id: str
    seed: int
    twin: Twin
    layout: Layout
    condition: Condition
    load: Literal[2, 8]
    public: PublicCase
    hidden_states: dict[str, Result] = Field(repr=False)

    @model_validator(mode="after")
    def integrity(self) -> Case:
        if len(self.public.records) != self.load:
            raise ValueError("Declared load differs from public records")
        if set(self.hidden_states) != set(self.public.target_ids):
            raise ValueError("Research states must cover exactly the targets")
        return self


class ToolCall(StrictModel):
    id: str = "call_1"
    name: str
    arguments: Any


class ModelReply(StrictModel):
    tool_calls: tuple[ToolCall, ...] = ()
    content: str | None = None
    refused: bool = False


class InspectArgs(StrictModel):
    lot_id: str


class CommitArgs(StrictModel):
    dispositions: dict[str, Disposition]


class Request(StrictModel):
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: str | None = "auto"
    parallel_tool_calls: bool = False


class ScoreRow(StrictModel):
    cell_id: str
    category: Category | None = None
    expected_loss: float | None = None
    oracle_loss: float | None = None
    regret: float | None = None
    regret_with_invalids: float | None = None
    realised_loss: float | None = None
    inspected_lot: str | None = None
    post_inspection_correct: bool | None = None
    missing_reason: str | None = None
