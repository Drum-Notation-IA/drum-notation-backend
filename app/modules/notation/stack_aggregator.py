"""
Rhythmic stack aggregation for the dense ML transcription.

The enriched ML service can emit *thousands* of events per video and, crucially,
**polyphony**: several events sharing the exact same rhythmic position
(``measure`` / ``beat`` / ``subdivision_index`` / ``grid_type``) but different
instruments — e.g. a kick+snare+hi-hat stack. This is intentional: it is a drum
"chord" and must NOT be de-duplicated by time.

:class:`StackAggregator` groups events into :class:`DrumStack` objects, one per
rhythmic position, preserving per-stroke ``velocity`` and ``confidence``. It:

* runs in a single ``O(n)`` pass (no ``O(n^2)`` measure scans);
* keeps ``straight`` and ``triplet`` grids as *distinct* positions, so the two
  grids are never mixed inside a measure;
* applies a configurable confidence / velocity filter (clean vs. complete
  transcription) instead of hardcoded thresholds;
* derives dynamics (accent / ghost) from MIDI velocity.

The aggregator is deliberately tolerant about field names so it works both on
raw ML events (``measure``/``beat``/``subdivision_index``/``velocity``) and on
the backend's normalised ``drum_event`` dicts
(``ml_measure``/``ml_beat``/``ml_subdivision``/``velocity_midi``).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

GRID_STRAIGHT = "straight"
GRID_TRIPLET = "triplet"


@dataclass(frozen=True)
class RhythmicPosition:
    """A unique rhythmic slot inside the piece.

    ``grid_type`` is part of the identity on purpose: a straight 16th and a
    triplet that round to the same beat are different musical positions and
    must never be merged.
    """

    measure: int
    beat: int
    subdivision_index: int
    grid_type: str = GRID_STRAIGHT

    def sort_key(self, subdivisions_per_beat_straight: int = 4,
                 subdivisions_per_beat_triplet: int = 3) -> Tuple[int, float, int]:
        """Chronological-ish ordering key (straight before triplet on ties)."""
        spb = (subdivisions_per_beat_triplet
               if self.grid_type == GRID_TRIPLET
               else subdivisions_per_beat_straight)
        spb = spb or 4
        offset = (self.subdivision_index - 1) / spb
        return (self.measure, self.beat + offset, 0 if self.grid_type == GRID_STRAIGHT else 1)


@dataclass
class StrokeHit:
    """A single drum stroke within a :class:`DrumStack`."""

    instrument: str
    velocity: float = 0.5                 # normalised 0..1
    velocity_midi: Optional[int] = None   # raw MIDI 1..127 when available
    confidence: float = 0.0
    dominant_band: Optional[str] = None
    timestamp_seconds: Optional[float] = None
    accent: bool = False
    ghost_note: bool = False


@dataclass
class DrumStack:
    """All simultaneous strokes at one :class:`RhythmicPosition`."""

    position: RhythmicPosition
    hits: List[StrokeHit] = field(default_factory=list)

    @property
    def instruments(self) -> List[str]:
        return [h.instrument for h in self.hits]

    @property
    def is_chord(self) -> bool:
        """True when more than one instrument sounds at this position."""
        return len({h.instrument for h in self.hits}) > 1


@dataclass
class AggregatorConfig:
    """Configurable thresholds (nothing hardcoded at call sites).

    ``min_confidence`` / ``min_velocity_midi`` drive the "clean vs complete"
    transcription trade-off; the accent / ghost thresholds drive dynamics.
    """

    min_confidence: float = 0.0
    min_velocity_midi: int = 0
    accent_velocity_midi: int = 100
    ghost_velocity_midi: int = 35
    # Grid resolution used to compute fractional beat positions.
    subdivisions_per_beat_straight: int = 4
    subdivisions_per_beat_triplet: int = 3
    # Hard cap to keep the pipeline bounded on pathological inputs.
    max_events: int = 100_000


def _first(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``keys``."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class StackAggregator:
    """Aggregate flat drum events into per-position :class:`DrumStack` objects."""

    def __init__(self, config: Optional[AggregatorConfig] = None):
        self.config = config or AggregatorConfig()

    # -- core --------------------------------------------------------------

    def aggregate(self, events: List[Dict[str, Any]]) -> List[DrumStack]:
        """Group ``events`` by rhythmic position.

        Single pass, insertion-ordered. Events that lack rhythmic-grid
        metadata are skipped here (the caller falls back to time-based
        quantisation for those). Polyphony is preserved: a kick+snare+hi-hat
        sharing one position yields a single stack with three hits.
        """
        cfg = self.config
        stacks: "OrderedDict[RhythmicPosition, DrumStack]" = OrderedDict()

        for i, ev in enumerate(events):
            if i >= cfg.max_events:
                break
            if not isinstance(ev, dict):
                continue

            measure = _coerce_int(_first(ev, "measure", "ml_measure"))
            beat = _coerce_int(_first(ev, "beat", "ml_beat"))
            sub = _coerce_int(_first(ev, "subdivision_index", "ml_subdivision"))
            if measure is None or beat is None or sub is None:
                # No ML grid → not aggregatable on the rhythmic grid.
                continue

            grid_type = str(_first(ev, "grid_type", default=GRID_STRAIGHT)).lower()
            if grid_type not in (GRID_STRAIGHT, GRID_TRIPLET):
                grid_type = GRID_STRAIGHT

            confidence = _coerce_float(
                _first(ev, "confidence", "model_confidence", default=0.0)
            )
            velocity_midi = _coerce_int(_first(ev, "velocity_midi", "velocity"))
            velocity_norm = self._velocity_to_norm(ev, velocity_midi)

            # --- confidence / velocity filter (clean vs complete) ---------
            if confidence < cfg.min_confidence:
                continue
            if velocity_midi is not None and velocity_midi < cfg.min_velocity_midi:
                continue

            hit = StrokeHit(
                instrument=str(_first(ev, "instrument", "drum_type", default="unknown")),
                velocity=round(velocity_norm, 4),
                velocity_midi=velocity_midi,
                confidence=round(confidence, 4),
                dominant_band=_first(ev, "dominant_band"),
                timestamp_seconds=_first(ev, "time_seconds", "quantized_time", "time"),
                accent=self._is_accent(velocity_midi, velocity_norm),
                ghost_note=self._is_ghost(velocity_midi, velocity_norm),
            )

            pos = RhythmicPosition(measure, beat, sub, grid_type)
            stack = stacks.get(pos)
            if stack is None:
                stack = DrumStack(position=pos)
                stacks[pos] = stack
            self._merge_hit(stack, hit)

        return list(stacks.values())

    # -- helpers -----------------------------------------------------------

    def _velocity_to_norm(self, ev: Dict[str, Any], velocity_midi: Optional[int]) -> float:
        """Best-effort normalised (0..1) velocity."""
        raw = _first(ev, "velocity_norm")
        if raw is not None:
            return max(0.0, min(1.0, _coerce_float(raw, 0.5)))
        # Backend events store normalised velocity under "velocity"; ML events
        # store MIDI under "velocity". Disambiguate by magnitude.
        v = _first(ev, "velocity")
        if v is not None:
            vf = _coerce_float(v, 0.5)
            if vf <= 1.0:
                return max(0.0, min(1.0, vf))
        if velocity_midi is not None:
            return max(0.0, min(1.0, velocity_midi / 127.0))
        return 0.5

    def _is_accent(self, velocity_midi: Optional[int], velocity_norm: float) -> bool:
        if velocity_midi is not None:
            return velocity_midi >= self.config.accent_velocity_midi
        return velocity_norm >= (self.config.accent_velocity_midi / 127.0)

    def _is_ghost(self, velocity_midi: Optional[int], velocity_norm: float) -> bool:
        if velocity_midi is not None:
            return velocity_midi <= self.config.ghost_velocity_midi
        return velocity_norm <= (self.config.ghost_velocity_midi / 127.0)

    @staticmethod
    def _merge_hit(stack: DrumStack, hit: StrokeHit) -> None:
        """Add ``hit`` to ``stack``.

        Different instruments coexist (chord). The same instrument hitting the
        exact same position twice is collapsed to the louder/more-confident
        stroke — this is *not* time de-duplication, just sane chord building.
        """
        for existing in stack.hits:
            if existing.instrument == hit.instrument:
                if (hit.velocity, hit.confidence) > (existing.velocity, existing.confidence):
                    existing.velocity = hit.velocity
                    existing.velocity_midi = hit.velocity_midi
                    existing.confidence = hit.confidence
                    existing.dominant_band = hit.dominant_band
                    existing.accent = hit.accent
                    existing.ghost_note = hit.ghost_note
                return
        stack.hits.append(hit)

    # -- notation_json conversion -----------------------------------------

    def beat_number_for(self, pos: RhythmicPosition) -> float:
        """Fractional, measure-local beat number for a position.

        Straight 16ths land on ``1.0, 1.25, 1.5, 1.75, 2.0 …`` (what the PDF
        generator and existing frontend already expect); triplets land on their
        own (1/3) grid so they are not snapped onto the straight grid.
        """
        spb = (self.config.subdivisions_per_beat_triplet
               if pos.grid_type == GRID_TRIPLET
               else self.config.subdivisions_per_beat_straight) or 4
        return round(pos.beat + (pos.subdivision_index - 1) / spb, 4)

    def to_measures(
        self,
        stacks: List[DrumStack],
        tempo_bpm: float,
        time_signature: str,
        beats_per_measure: int,
        drum_mapping: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Render stacks into the existing ``measures`` notation_json shape.

        Backward compatible: each note keeps the legacy keys
        (``drum_type``/``velocity``/``beat_number`` …) and gains additive ML
        keys (``grid_type``/``dominant_band``/``velocity_midi``).
        """
        if not stacks:
            return []

        # Bucket stacks by measure in one pass (O(n)).
        by_measure: "OrderedDict[int, List[DrumStack]]" = OrderedDict()
        max_measure = 0
        for st in stacks:
            m = st.position.measure
            max_measure = max(max_measure, m)
            by_measure.setdefault(m, []).append(st)

        seconds_per_beat = 60.0 / tempo_bpm if tempo_bpm else 0.5
        seconds_per_measure = seconds_per_beat * beats_per_measure

        measures: List[Dict[str, Any]] = []
        for measure_num in range(1, max_measure + 1):
            measure_start = (measure_num - 1) * seconds_per_measure
            measure_stacks = sorted(
                by_measure.get(measure_num, []),
                key=lambda s: s.position.sort_key(
                    self.config.subdivisions_per_beat_straight,
                    self.config.subdivisions_per_beat_triplet,
                ),
            )

            beats: List[Dict[str, Any]] = []
            for st in measure_stacks:
                beat_number = self.beat_number_for(st.position)
                notes = [
                    self._hit_to_note(h, st.position, beat_number, drum_mapping)
                    for h in st.hits
                ]
                beats.append({
                    "beat_number": beat_number,
                    "grid_type": st.position.grid_type,
                    "subdivision_index": st.position.subdivision_index,
                    "notes": notes,
                    "note_count": len(notes),
                })

            measures.append({
                "measure_number": measure_num,
                "start_time_seconds": round(measure_start, 4),
                "end_time_seconds": round(measure_start + seconds_per_measure, 4),
                "time_signature": time_signature,
                "tempo_bpm": tempo_bpm,
                "beats": beats,
                "complexity_score": self._measure_complexity(measure_stacks),
            })

        return measures

    @staticmethod
    def _hit_to_note(
        hit: StrokeHit,
        pos: RhythmicPosition,
        beat_number: float,
        drum_mapping: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        mapping = drum_mapping.get(
            hit.instrument,
            {"staff_position": "C5", "note_head": "normal", "line": 3},
        )
        note: Dict[str, Any] = {
            "drum_type": hit.instrument,
            "staff_position": mapping.get("staff_position", "C5"),
            "note_head_type": mapping.get("note_head", "normal"),
            "velocity": hit.velocity,
            "accent": hit.accent,
            "ghost_note": hit.ghost_note,
            "confidence_score": hit.confidence,
            "timestamp_seconds": hit.timestamp_seconds,
            "beat_number": beat_number,
            # --- additive ML metadata ---
            "grid_type": pos.grid_type,
            "subdivision_index": pos.subdivision_index,
        }
        if hit.velocity_midi is not None:
            note["velocity_midi"] = hit.velocity_midi
        if hit.dominant_band is not None:
            note["dominant_band"] = hit.dominant_band
        return note

    @staticmethod
    def _measure_complexity(stacks: List[DrumStack]) -> float:
        if not stacks:
            return 0.0
        note_count = sum(len(s.hits) for s in stacks)
        instruments = {h.instrument for s in stacks for h in s.hits}
        density = min(note_count / 16.0, 1.0)
        variety = min(len(instruments) / 5.0, 1.0)
        return round((density + variety) / 2.0, 3)
