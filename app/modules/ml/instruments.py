"""
Canonical drum-instrument vocabulary and mapping.

The ML service emits a *mixed* instrument vocabulary
("kick", "snare", "tom", "hihat", "hihat_closed", "hihat_open", "crash",
"ride", ...). The notation service, the PDF generator and the frontend all
expect a single *canonical* vocabulary.

This module centralises that translation behind an OOP boundary:

* :class:`DrumInstrument` — the canonical Enum used internally.
* :class:`InstrumentMapper` — a configurable mapper (alias table + safe
  fallback) that normalises any incoming label to the canonical vocabulary.

The default mapper reproduces the historical behaviour of the previous
``_canonical_instrument`` helper exactly (so nothing downstream breaks),
while exposing a clean, testable, extensible API.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional


class DrumInstrument(str, Enum):
    """Canonical internal drum-instrument vocabulary.

    Inheriting from ``str`` keeps these values JSON-serialisable and lets them
    be compared directly against the plain strings used throughout the
    existing pipeline (``default_drum_mapping`` keys, PDF ``DRUM_MAP`` keys).
    """

    KICK = "kick"
    SNARE = "snare"
    TOM1 = "tom1"
    TOM2 = "tom2"
    FLOOR_TOM = "floor_tom"
    HIHAT = "hi-hat"            # closed / generic hi-hat
    HIHAT_OPEN = "hihat_open"
    HIHAT_CLOSED = "hihat_closed"
    CRASH = "crash"
    CRASH2 = "crash2"
    RIDE = "ride"
    RIDE_BELL = "ride_bell"
    CHINA = "china"
    FOOT_HIHAT = "foot_hihat"
    COWBELL = "cowbell"
    UNKNOWN = "unknown"


# Default alias table: any raw ML / detector label → canonical string.
# NOTE: keep this in sync with the (now thin) ``ML_INSTRUMENT_ALIASES`` in the
# ML router, which re-exports this table for backward compatibility.
DEFAULT_INSTRUMENT_ALIASES: Dict[str, str] = {
    # hi-hat variants — group closed/generic together ("if you don't
    # distinguish openness, merge hihat/hihat_closed").
    "hihat":         DrumInstrument.HIHAT.value,
    "hi_hat":        DrumInstrument.HIHAT.value,
    "hi-hat":        DrumInstrument.HIHAT.value,
    "hihat_closed":  DrumInstrument.HIHAT.value,
    "closed_hihat":  DrumInstrument.HIHAT.value,
    "hihat_open":    DrumInstrument.HIHAT_OPEN.value,
    "open_hihat":    DrumInstrument.HIHAT_OPEN.value,
    "openhihat":     DrumInstrument.HIHAT_OPEN.value,
    # kick / bass drum
    "kick":          DrumInstrument.KICK.value,
    "bass_drum":     DrumInstrument.KICK.value,
    "bassdrum":      DrumInstrument.KICK.value,
    "bd":            DrumInstrument.KICK.value,
    # snare
    "snare":         DrumInstrument.SNARE.value,
    "sd":            DrumInstrument.SNARE.value,
    # cymbals
    "crash":         DrumInstrument.CRASH.value,
    "crash_cymbal":  DrumInstrument.CRASH.value,
    "cc":            DrumInstrument.CRASH.value,
    "ride":          DrumInstrument.RIDE.value,
    "ride_cymbal":   DrumInstrument.RIDE.value,
    "rc":            DrumInstrument.RIDE.value,
    "ride_bell":     DrumInstrument.RIDE_BELL.value,
    "china":         DrumInstrument.CHINA.value,
    "china_cymbal":  DrumInstrument.CHINA.value,
    "splash":        DrumInstrument.CRASH.value,
    # toms — generic ML "tom" → mid tom (neutral middle staff)
    "tom":           DrumInstrument.TOM2.value,
    "tom1":          DrumInstrument.TOM1.value,
    "tom_high":      DrumInstrument.TOM1.value,
    "high_tom":      DrumInstrument.TOM1.value,
    "rack_tom":      DrumInstrument.TOM1.value,
    "tom2":          DrumInstrument.TOM2.value,
    "tom_mid":       DrumInstrument.TOM2.value,
    "mid_tom":       DrumInstrument.TOM2.value,
    "floor_tom":     DrumInstrument.FLOOR_TOM.value,
    "floortom":      DrumInstrument.FLOOR_TOM.value,
    "tom_low":       DrumInstrument.FLOOR_TOM.value,
    "low_tom":       DrumInstrument.FLOOR_TOM.value,
    "ft":            DrumInstrument.FLOOR_TOM.value,
    # foot hi-hat
    "foot_hihat":    DrumInstrument.FOOT_HIHAT.value,
    "foot_hi_hat":   DrumInstrument.FOOT_HIHAT.value,
    "fhh":           DrumInstrument.FOOT_HIHAT.value,
    "pedal_hihat":   DrumInstrument.FOOT_HIHAT.value,
}


class InstrumentMapper:
    """Normalise a mixed drum vocabulary to a canonical one.

    Parameters
    ----------
    aliases:
        Optional custom alias table (raw label → canonical string). Defaults to
        :data:`DEFAULT_INSTRUMENT_ALIASES`. Pass your own to extend or override
        the mapping without touching call sites (configurable, not hardcoded).
    """

    def __init__(self, aliases: Optional[Dict[str, str]] = None):
        # Copy so callers can't mutate our defaults by reference.
        self._aliases: Dict[str, str] = dict(
            aliases if aliases is not None else DEFAULT_INSTRUMENT_ALIASES
        )

    # -- public API --------------------------------------------------------

    def canonical(self, name: object) -> str:
        """Map any incoming drum-class label to a canonical string.

        Reproduces the historical normalisation rules and falls back safely to
        a lower-cased version of the original label for unknown instruments
        (never raises).
        """
        raw = (
            str(name or "unknown")
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "")
        )
        if raw in self._aliases:
            return self._aliases[raw]

        raw_dash = str(name or "unknown").strip().lower().replace("_", "-")
        if raw_dash in self._aliases:
            return self._aliases[raw_dash]

        # Safe fallback: keep the (lower-cased) original label so downstream
        # consumers can still render *something* for unknown instruments.
        return str(name or "unknown").strip().lower()

    def to_instrument(self, name: object) -> DrumInstrument:
        """Map a label to a :class:`DrumInstrument`, falling back to UNKNOWN."""
        try:
            return DrumInstrument(self.canonical(name))
        except ValueError:
            return DrumInstrument.UNKNOWN

    def register(self, raw_label: str, canonical: str) -> None:
        """Add / override a single alias at runtime."""
        self._aliases[str(raw_label).strip().lower()] = canonical

    @property
    def aliases(self) -> Dict[str, str]:
        """Read-only view of the current alias table."""
        return dict(self._aliases)


# Shared default instance — cheap, stateless, safe to reuse everywhere.
default_instrument_mapper = InstrumentMapper()
