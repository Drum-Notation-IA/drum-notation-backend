"""
Notation Service
Business logic for drum notation generation, processing, and AI enhancement
Updated to work with simplified JSON-based database schema
"""

import asyncio
import hashlib
import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.openai_service import OpenAIService
from app.modules.notation.models import DrumNotation
from app.modules.notation.stack_aggregator import (
    AggregatorConfig,
    StackAggregator,
)
from app.modules.notation.repository import (
    DrumKitMappingRepository,
    DrumNotationRepository,
    NotationExportRepository,
    NotationMeasureRepository,
    OpenAIEnrichmentRepository,
    StrokeEventRepository,
)


class NotationService:
    """Service for drum notation operations"""

    def __init__(self):
        # Initialize repositories
        self.notation_repo = DrumNotationRepository()
        self.enrichment_repo = OpenAIEnrichmentRepository()
        self.export_repo = NotationExportRepository()
        self.measure_repo = NotationMeasureRepository()
        self.stroke_repo = StrokeEventRepository()
        self.kit_mapping_repo = DrumKitMappingRepository()

        # Initialize AI service
        self.openai_service = OpenAIService()

        # Default drum kit mapping (standard percussion staff)
        self.default_drum_mapping = {
            "kick": {"staff_position": "F4", "note_head": "normal", "line": 1},
            "snare": {"staff_position": "D5", "note_head": "normal", "line": 3},
            "hihat_closed": {"staff_position": "F#5", "note_head": "x", "line": 4},
            "hihat_open": {"staff_position": "A5", "note_head": "o", "line": 5},
            "crash": {"staff_position": "A5", "note_head": "x", "line": 5},
            "ride": {"staff_position": "F#5", "note_head": "x", "line": 4},
            "tom1": {"staff_position": "B4", "note_head": "normal", "line": 2},
            "tom2": {"staff_position": "G4", "note_head": "normal", "line": 2},
            "floor_tom": {"staff_position": "D4", "note_head": "normal", "line": 0},
            "cowbell": {"staff_position": "G5", "note_head": "triangle", "line": 4},
            # Canonical "hi-hat" alias (the ML pipeline normalises hihat/
            # hihat_closed → "hi-hat"); mirrors hihat_closed staff position.
            "hi-hat": {"staff_position": "F#5", "note_head": "x", "line": 4},
        }

    async def generate_notation_from_drum_detection(
        self,
        db: AsyncSession,
        video_id: UUID,
        drum_events: List[Dict[str, Any]],
        tempo_bpm: Optional[float] = None,
        time_signature: str = "4/4",
        quantization_level: str = "sixteenth",
        apply_ai_analysis: bool = True,
        ml_provenance: Optional[Dict[str, Any]] = None,
        min_confidence: Optional[float] = None,
    ) -> DrumNotation:
        """
        Generate complete musical notation from drum detection results.

        ``ml_provenance`` (when supplied by the ML pipeline) is persisted in
        ``notation_json["ml_provenance"]`` so the frontend can show whether
        the notation was produced by the upstream ML service or by the local
        fallback, plus model confidence and quantization metadata.

        ``min_confidence`` (0..1) filters out low-confidence strokes so callers
        can request a clean chart (strong hits only) instead of the full
        transcription (ghost notes / rolls included). Defaults to the
        configured ``DEFAULT_MIN_CONFIDENCE`` when not provided.
        """
        try:
            from app.core.config import settings as _cfg
            if min_confidence is None:
                min_confidence = float(getattr(_cfg, "DEFAULT_MIN_CONFIDENCE", 0.0))

            # Calculate basic metrics; allow 0 events (generates empty/minimal notation)
            estimated_tempo = tempo_bpm or (self._estimate_tempo_from_events(drum_events) if drum_events else 120.0)

            # ML quantization metadata (subdivision/grid steps) drives triplet
            # placement; pulled from provenance when the ML pipeline supplied it.
            ml_quantization = (
                (ml_provenance or {}).get("ml_metadata", {}).get("quantization", {})
                if ml_provenance else {}
            )

            # Generate the complete notation structure
            notation_json = await self._generate_complete_notation(
                drum_events, estimated_tempo, time_signature, quantization_level,
                min_confidence=min_confidence, ml_quantization=ml_quantization,
            )

            # Persist ML provenance + analysis stats so the frontend has them
            if ml_provenance is not None:
                notation_json["ml_provenance"] = ml_provenance

            # Create the main notation record with all data
            notation = await self.notation_repo.create_notation(
                db=db,
                video_id=video_id,
                tempo=int(estimated_tempo) if estimated_tempo else None,
                time_signature=time_signature,
                notation_json=notation_json,
            )

            # Process AI analysis in background if requested
            if apply_ai_analysis and self.openai_service.is_enabled():
                asyncio.create_task(
                    self._apply_ai_analysis_async(db, UUID(str(notation.id)))
                )

            return notation

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to generate notation: {str(e)}"
            )

    async def _generate_complete_notation(
        self,
        drum_events: List[Dict[str, Any]],
        tempo_bpm: float,
        time_signature: str,
        quantization_level: str,
        min_confidence: float = 0.0,
        ml_quantization: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete notation structure as JSON.

        When the events carry the ML rhythmic grid (measure / beat /
        subdivision_index / grid_type) we group them with :class:`StackAggregator`
        — preserving polyphonic stacks and keeping straight vs. triplet grids
        separate — in a single O(n) pass. Otherwise we fall back to the legacy
        time-based quantisation (used by the fully local detector path).
        """
        ml_quantization = ml_quantization or {}

        # Confidence filter (clean vs complete transcription). Single O(n) pass
        # shared by the timeline and the measure builder.
        if min_confidence and min_confidence > 0.0:
            filtered_events = [
                e for e in drum_events
                if float(e.get("confidence") or 0.0) >= min_confidence
            ]
        else:
            filtered_events = drum_events

        use_ml_grid = any(
            e.get("ml_measure") is not None and e.get("ml_subdivision") is not None
            for e in filtered_events
        )

        # Generate musical structure
        musical_structure = self._generate_musical_structure(
            filtered_events, tempo_bpm, time_signature, quantization_level
        )

        # Generate stroke timeline (forwards the new ML fields too)
        timeline = self._generate_stroke_timeline(filtered_events, musical_structure)

        # Generate measures with beats and notes
        if use_ml_grid:
            measures = self._build_measures_from_ml_grid(
                filtered_events, tempo_bpm, time_signature,
                min_confidence=0.0,  # already filtered above
                ml_quantization=ml_quantization,
            )
        else:
            measures = self._generate_measures_from_events(
                filtered_events, tempo_bpm, time_signature, quantization_level
            )

        # Build complete notation JSON
        notation_json = {
            "musical_structure": musical_structure,
            "timeline": timeline,
            "measures": measures,
            "drum_mapping": self.default_drum_mapping,
            "metadata": {
                "total_duration_seconds": max(
                    event.get("time_seconds", 0) for event in filtered_events
                )
                if filtered_events
                else 0,
                "total_measures": len(measures),
                "total_events": len(filtered_events),
                "quantization_level": quantization_level,
                "min_confidence": min_confidence,
                "grid_aware": use_ml_grid,
                "generated_at": datetime.utcnow().isoformat(),
            },
            "exports": [],  # Will be populated when exports are generated
        }

        return notation_json

    def _build_measures_from_ml_grid(
        self,
        drum_events: List[Dict[str, Any]],
        tempo_bpm: float,
        time_signature: str,
        min_confidence: float = 0.0,
        ml_quantization: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Build measures by grouping events on the ML rhythmic grid.

        Uses :class:`StackAggregator` so simultaneous strokes (kick+snare+hihat)
        become a single chord at one rhythmic position, and triplet events are
        placed on their own subdivision grid instead of being snapped onto the
        straight 16th grid.
        """
        ml_quantization = ml_quantization or {}
        beats_per_measure = self._get_beats_per_measure(time_signature)
        denom = self._get_time_signature_denominator(time_signature)

        # Derive grid resolution from the ML quantization block when present.
        subdivision = ml_quantization.get("subdivision")
        if subdivision:
            spb_straight = max(1, round(float(subdivision) / float(denom)))
        else:
            spb_straight = 4  # 16th notes in x/4

        grid_step = ml_quantization.get("grid_step_seconds")
        triplet_step = ml_quantization.get("triplet_step_seconds")
        if grid_step and triplet_step:
            spb_triplet = max(1, round(spb_straight * (float(grid_step) / float(triplet_step))))
        else:
            spb_triplet = max(1, round(spb_straight * 3 / 4))

        config = AggregatorConfig(
            min_confidence=min_confidence,
            subdivisions_per_beat_straight=spb_straight,
            subdivisions_per_beat_triplet=spb_triplet,
        )
        aggregator = StackAggregator(config)
        stacks = aggregator.aggregate(drum_events)
        return aggregator.to_measures(
            stacks,
            tempo_bpm=tempo_bpm,
            time_signature=time_signature,
            beats_per_measure=beats_per_measure,
            drum_mapping=self.default_drum_mapping,
        )

    def _generate_musical_structure(
        self,
        drum_events: List[Dict[str, Any]],
        tempo_bpm: float,
        time_signature: str,
        quantization_level: str,
    ) -> Dict[str, Any]:
        """
        Generate musical structure metadata
        """
        if not drum_events:
            return {}

        duration_seconds = max(event.get("time_seconds", 0) for event in drum_events)
        beats_per_measure = self._get_beats_per_measure(time_signature)

        # Calculate measures
        seconds_per_beat = 60.0 / tempo_bpm
        seconds_per_measure = seconds_per_beat * beats_per_measure
        total_measures = math.ceil(duration_seconds / seconds_per_measure)

        # Analyze complexity
        complexity_indicators = self._calculate_complexity_indicators(drum_events)

        return {
            "tempo_bpm": tempo_bpm,
            "time_signature": time_signature,
            "beats_per_measure": beats_per_measure,
            "total_measures": total_measures,
            "duration_seconds": duration_seconds,
            "quantization": {
                "level": quantization_level,
                "grid": self._get_quantization_grid(quantization_level),
            },
            "complexity": complexity_indicators,
            "instruments_detected": list(
                set(event.get("instrument", "unknown") for event in drum_events)
            ),
        }

    def _generate_stroke_timeline(
        self, drum_events: List[Dict[str, Any]], musical_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate stroke-by-stroke timeline for real-time playback
        """
        timeline = []
        tempo_bpm = musical_structure.get("tempo_bpm", 120)
        beats_per_measure = musical_structure.get("beats_per_measure", 4)
        seconds_per_beat = 60.0 / tempo_bpm
        seconds_per_measure = seconds_per_beat * beats_per_measure

        for event in sorted(drum_events, key=lambda x: x.get("time_seconds", 0)):
            time_seconds = event.get("time_seconds", 0)
            instrument = event.get("instrument", "unknown")
            velocity = event.get("velocity", 0.5)

            # Calculate measure and beat
            measure_number = int(time_seconds // seconds_per_measure) + 1
            time_in_measure = time_seconds % seconds_per_measure
            beat_number = (time_in_measure / seconds_per_beat) + 1

            # Get drum mapping
            drum_mapping = self.default_drum_mapping.get(
                instrument, {"staff_position": "C5", "note_head": "normal", "line": 3}
            )

            stroke_event = {
                "timestamp_seconds": time_seconds,
                "drum_type": instrument,
                "velocity": velocity,
                "measure_number": measure_number,
                "beat_number": round(beat_number, 3),
                "staff_position": drum_mapping["staff_position"],
                "note_head_type": drum_mapping["note_head"],
                "accent": "accent" if velocity > 0.8 else None,
                "ghost_note": velocity < 0.3,
                "confidence_score": event.get("confidence", None),
            }

            # Forward ML metadata when available
            for extra_key in (
                "model_confidence", "max_probability", "heuristic",
                "ml_measure", "ml_beat", "ml_subdivision",
                "ml_grid_index", "quant_error_ms", "raw_time",
                # NEW additive ML fields
                "dominant_band", "grid_type", "velocity_midi",
                "strength", "peak_rel", "quantized_time",
            ):
                if extra_key in event and event[extra_key] is not None:
                    stroke_event[extra_key] = event[extra_key]

            timeline.append(stroke_event)

        return timeline

    def _generate_measures_from_events(
        self,
        drum_events: List[Dict[str, Any]],
        tempo_bpm: float,
        time_signature: str,
        quantization_level: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate measures with beats and notes from drum events
        """
        if not drum_events:
            return []

        beats_per_measure = self._get_beats_per_measure(time_signature)
        seconds_per_beat = 60.0 / tempo_bpm
        seconds_per_measure = seconds_per_beat * beats_per_measure

        duration_seconds = max(event.get("time_seconds", 0) for event in drum_events)
        total_measures = math.ceil(duration_seconds / seconds_per_measure)

        measures = []

        for measure_num in range(1, total_measures + 1):
            measure_start = (measure_num - 1) * seconds_per_measure
            measure_end = measure_num * seconds_per_measure

            # Get events in this measure
            measure_events = [
                event
                for event in drum_events
                if measure_start <= event.get("time_seconds", 0) < measure_end
            ]

            # Organize events into beats
            beats = self._organize_events_into_beats(
                measure_events, measure_start, beats_per_measure, seconds_per_beat
            )

            measure_data = {
                "measure_number": measure_num,
                "start_time_seconds": measure_start,
                "end_time_seconds": measure_end,
                "time_signature": time_signature,
                "tempo_bpm": tempo_bpm,
                "beats": beats,
                "complexity_score": self._calculate_measure_complexity(measure_events),
            }

            measures.append(measure_data)

        return measures

    def _organize_events_into_beats(
        self,
        events: List[Dict[str, Any]],
        measure_start_time: float,
        beats_per_measure: int,
        seconds_per_beat: float,
    ) -> List[Dict[str, Any]]:
        """
        Organize events into a 16th-note grid within a measure.
        Each event is quantized to the nearest 16th-note slot and
        assigned a fractional beat_number (e.g. 1.0, 1.25, 1.5, 1.75, 2.0 …).
        """
        SUBDIVISION = 4  # 16th notes per beat
        total_slots = beats_per_measure * SUBDIVISION
        slot_duration = seconds_per_beat / SUBDIVISION

        # Map slot_index → list of notes
        slots: Dict[int, List[Dict[str, Any]]] = {}

        for event in events:
            time_seconds = float(event.get("time_seconds", 0))
            instrument = str(event.get("instrument", "unknown"))
            velocity = float(event.get("velocity", 0.5))

            # Quantize to nearest 16th-note slot
            time_in_measure = time_seconds - measure_start_time
            slot_index = int(round(time_in_measure / slot_duration))
            slot_index = max(0, min(total_slots - 1, slot_index))

            # Fractional beat position: 1.0, 1.25, 1.5 … beats_per_measure.75
            beat_number = 1.0 + slot_index / SUBDIVISION

            # Note duration based on subdivision level
            slot_in_beat = slot_index % SUBDIVISION
            if slot_in_beat == 0:
                note_duration = "quarter"
            elif slot_in_beat % 2 == 0:
                note_duration = "eighth"
            else:
                note_duration = "sixteenth"

            drum_mapping = self.default_drum_mapping.get(
                instrument,
                {"staff_position": "C5", "note_head": "normal", "line": 3},
            )

            note = {
                "drum_type": instrument,
                "staff_position": drum_mapping["staff_position"],
                "note_duration": note_duration,
                "note_head_type": drum_mapping["note_head"],
                "velocity": velocity,
                "accent": velocity > 0.8,
                "ghost_note": velocity < 0.3,
                "confidence_score": event.get("confidence"),
                "timestamp_seconds": time_seconds,
                "beat_number": round(beat_number, 4),
            }

            # Preserve ML metadata if the upstream pipeline supplied it
            for extra_key in (
                "model_confidence", "max_probability", "heuristic",
                "ml_measure", "ml_beat", "ml_subdivision",
                "ml_grid_index", "quant_error_ms", "raw_time",
                # NEW additive ML fields
                "dominant_band", "grid_type", "velocity_midi",
                "strength", "peak_rel", "quantized_time",
            ):
                if extra_key in event and event[extra_key] is not None:
                    note[extra_key] = event[extra_key]

            slots.setdefault(slot_index, []).append(note)

        # Build beats list — one entry per occupied 16th-note slot
        beats = []
        for slot_idx in range(total_slots):
            notes = slots.get(slot_idx)
            if notes:
                beat_number = round(1.0 + slot_idx / SUBDIVISION, 4)
                beats.append({
                    "beat_number": beat_number,
                    "slot_index": slot_idx,
                    "notes": notes,
                    "note_count": len(notes),
                })

        return beats

    async def _apply_ai_analysis_async(self, db: AsyncSession, notation_id: UUID):
        """
        Apply AI analysis to notation in background
        """
        try:
            notation = await self.notation_repo.get_by_id(db, notation_id)
            if not notation:
                return

            # Generate analysis prompt
            analysis_input = {
                "notation_data": notation.notation_json,
                "tempo": notation.tempo,
                "time_signature": notation.time_signature,
            }

            # Calculate prompt hash for caching
            prompt_hash = self._calculate_prompt_hash(analysis_input)

            # Check for existing analysis
            existing = await self.enrichment_repo.get_by_prompt_hash(
                db, notation_id, prompt_hash
            )
            if existing:
                return  # Already analyzed

            # Call OpenAI for analysis
            ai_response = await self.openai_service.analyze_drum_pattern(
                drum_events=analysis_input.get("notation_data", {}).get("timeline", []),
                tempo=analysis_input.get("tempo", 120),
                time_signature=analysis_input.get("time_signature", "4/4"),
                duration=analysis_input.get("notation_data", {})
                .get("metadata", {})
                .get("total_duration_seconds", 0),
            )

            # Store enrichment
            await self.enrichment_repo.create_enrichment(
                db=db,
                notation_id=notation_id,
                prompt_hash=prompt_hash,
                model="gpt-4",  # Default model name
                input_json=analysis_input,
                output_json=ai_response,
            )

        except Exception as e:
            # Log error but don't fail the notation
            print(f"AI analysis failed for notation {notation_id}: {str(e)}")
            # Could add proper logging here

    async def get_notation_with_details(
        self, db: AsyncSession, notation_id: UUID
    ) -> Optional[DrumNotation]:
        """Get notation with all details loaded"""
        return await self.notation_repo.get_with_enrichments(db, notation_id)

    async def get_notation_timeline(
        self,
        db: AsyncSession,
        notation_id: UUID,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get stroke timeline for a notation, optionally filtered by time range
        """
        notation = await self.notation_repo.get_by_id(db, notation_id)
        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        timeline = notation.get_timeline()

        # Filter by time range if provided
        if start_time is not None or end_time is not None:
            filtered_timeline = []
            for event in timeline:
                timestamp = event.get("timestamp_seconds", 0)
                if start_time is not None and timestamp < start_time:
                    continue
                if end_time is not None and timestamp > end_time:
                    continue
                filtered_timeline.append(event)
            return filtered_timeline

        return timeline

    async def export_notation(
        self,
        db: AsyncSession,
        notation_id: UUID,
        export_format: str,
        **export_options,
    ) -> Dict[str, Any]:
        """
        Export notation to various formats
        """
        notation = await self.notation_repo.get_by_id(db, notation_id)
        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Check if export already exists
        exports = NotationExportRepository.get_exports(notation)
        existing_export = next(
            (exp for exp in exports if exp.get("export_format") == export_format), None
        )

        if existing_export and existing_export.get("status") == "completed":
            return existing_export

        # Process export asynchronously
        asyncio.create_task(
            self._process_export_async(db, notation, export_format, export_options)
        )

        # Return export metadata immediately
        export_metadata = {
            "export_format": export_format,
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Add export to notation JSON
        NotationExportRepository.add_export(notation, export_metadata)
        await self.notation_repo.update_notation_json(
            db, notation_id, notation.notation_json
        )

        return export_metadata

    async def _process_export_async(
        self,
        db: AsyncSession,
        notation: DrumNotation,
        export_format: str,
        export_options: Dict[str, Any],
    ):
        """
        Process export generation asynchronously
        """
        try:
            export_data = None
            file_path = None

            if export_format == "musicxml":
                export_data = await self._export_to_musicxml(notation, export_options)
                file_path = f"exports/{notation.id}_notation.xml"
            elif export_format == "midi":
                export_data = await self._export_to_midi(notation, export_options)
                file_path = f"exports/{notation.id}_notation.mid"
            elif export_format == "json":
                export_data = await self._export_to_json(notation, export_options)
                file_path = f"exports/{notation.id}_notation.json"
            elif export_format == "svg":
                export_data = await self._export_to_svg(notation, export_options)
                file_path = f"exports/{notation.id}_notation.svg"
            else:
                raise ValueError(f"Unsupported export format: {export_format}")

            # Update export status in notation JSON
            exports = NotationExportRepository.get_exports(notation)
            for export in exports:
                if export.get("export_format") == export_format:
                    export.update(
                        {
                            "status": "completed",
                            "file_path": file_path,
                            "completed_at": datetime.utcnow().isoformat(),
                            "file_size_bytes": len(str(export_data))
                            if export_data
                            else 0,
                        }
                    )
                    break

            NotationExportRepository.set_exports(notation, exports)
            # Ensure we have a proper dict for the JSON data
            current_json = notation.notation_json
            if isinstance(current_json, dict):
                notation_json_data = current_json
            else:
                notation_json_data = {}
            await self.notation_repo.update_notation_json(
                db, UUID(str(notation.id)), notation_json_data
            )

        except Exception as e:
            # Update export status to failed
            exports = NotationExportRepository.get_exports(notation)
            for export in exports:
                if export.get("export_format") == export_format:
                    export.update(
                        {
                            "status": "failed",
                            "error_message": str(e),
                            "failed_at": datetime.utcnow().isoformat(),
                        }
                    )
                    break

            NotationExportRepository.set_exports(notation, exports)
            # Ensure we have a proper dict for the JSON data
            current_json = notation.notation_json
            if isinstance(current_json, dict):
                notation_json_data = current_json
            else:
                notation_json_data = {}
            await self.notation_repo.update_notation_json(
                db, UUID(str(notation.id)), notation_json_data
            )

    # Helper methods for tempo and musical analysis
    def _estimate_tempo_from_events(self, drum_events: List[Dict[str, Any]]) -> float:
        """
        Estimate tempo from drum events using kick/snare IOI (beat-level),
        not hi-hat/cymbal IOI which would give 4× the true tempo.
        Falls back to global average if no kick/snare events are present.
        """
        if len(drum_events) < 2:
            return 120.0

        # Prefer beat-indicator instruments for IOI calculation
        BEAT_INSTRUMENTS = {"kick", "snare", "bass_drum", "floor_tom"}
        beat_times = sorted(
            e.get("time_seconds", 0)
            for e in drum_events
            if e.get("instrument", "").lower() in BEAT_INSTRUMENTS
        )

        if len(beat_times) < 2:
            # Fall back to all onsets but filter to intervals that look like beats
            all_times = sorted(e.get("time_seconds", 0) for e in drum_events)
            intervals = [
                all_times[i + 1] - all_times[i]
                for i in range(len(all_times) - 1)
                if 0.2 < (all_times[i + 1] - all_times[i]) < 2.0  # 30–300 BPM
            ]
        else:
            intervals = [
                beat_times[i + 1] - beat_times[i]
                for i in range(len(beat_times) - 1)
                if 0.2 < (beat_times[i + 1] - beat_times[i]) < 2.0
            ]

        if not intervals:
            return 120.0

        # Use median to be robust against occasional double-strokes or gaps
        intervals_sorted = sorted(intervals)
        mid = len(intervals_sorted) // 2
        median_interval = intervals_sorted[mid]

        estimated_bpm = 60.0 / median_interval
        return max(60.0, min(220.0, estimated_bpm))

    def _get_beats_per_measure(self, time_signature: str) -> int:
        """Get beats per measure from time signature"""
        try:
            numerator = int(time_signature.split("/")[0])
            return numerator
        except Exception:
            return 4

    def _get_time_signature_denominator(self, time_signature: str) -> int:
        """Get the beat unit (denominator) from a time signature like 4/4."""
        try:
            return int(time_signature.split("/")[1])
        except Exception:
            return 4

    def _get_staff_position(self, instrument: str) -> str:
        """Get staff position for instrument"""
        mapping = self.default_drum_mapping.get(instrument, {})
        return mapping.get("staff_position", "C5")

    def _get_note_head_type(self, instrument: str) -> str:
        """Get note head type for instrument"""
        mapping = self.default_drum_mapping.get(instrument, {})
        return mapping.get("note_head", "normal")

    def _get_quantization_grid(self, quantization_level: str) -> float:
        """Get quantization grid size in beats"""
        grids = {
            "whole": 4.0,
            "half": 2.0,
            "quarter": 1.0,
            "eighth": 0.5,
            "sixteenth": 0.25,
            "thirty_second": 0.125,
        }
        return grids.get(quantization_level, 0.25)

    def _get_subdivision_name(self, beat_position: float) -> str:
        """Get subdivision name from beat position"""
        if beat_position % 1.0 == 0:
            return "quarter"
        elif beat_position % 0.5 == 0:
            return "eighth"
        elif beat_position % 0.25 == 0:
            return "sixteenth"
        else:
            return "thirty_second"

    def _get_note_duration(self, subdivision: str) -> str:
        """Convert subdivision to note duration"""
        return subdivision  # For now, same mapping

    def _calculate_measure_complexity(self, events: List[Dict[str, Any]]) -> float:
        """Calculate complexity score for a measure (0.0-1.0)"""
        if not events:
            return 0.0

        # Factors: number of events, velocity variations, instrument variety
        event_count_factor = min(len(events) / 16.0, 1.0)  # Normalize to 16 events max

        velocities = [event.get("velocity", 0.5) for event in events]
        velocity_variance = (
            sum((v - 0.5) ** 2 for v in velocities) / len(velocities)
            if velocities
            else 0
        )
        velocity_factor = min(velocity_variance * 4, 1.0)  # Normalize variance

        instruments = set(event.get("instrument", "unknown") for event in events)
        instrument_factor = min(
            len(instruments) / 5.0, 1.0
        )  # Normalize to 5 instruments max

        return (event_count_factor + velocity_factor + instrument_factor) / 3.0

    def _calculate_complexity_indicators(
        self, drum_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate overall complexity indicators for the notation"""
        if not drum_events:
            return {
                "overall_complexity": 0.0,
                "note_density": 0.0,
                "instrument_variety": 0,
            }

        duration = max(event.get("time_seconds", 0) for event in drum_events)
        note_density = len(drum_events) / duration if duration > 0 else 0

        instruments = set(event.get("instrument", "unknown") for event in drum_events)
        instrument_variety = len(instruments)

        velocities = [event.get("velocity", 0.5) for event in drum_events]
        velocity_variance = (
            sum((v - 0.5) ** 2 for v in velocities) / len(velocities)
            if velocities
            else 0
        )

        # Calculate overall complexity (0.0-1.0)
        complexity_factors = [
            min(note_density / 10.0, 1.0),  # Normalize to 10 notes per second max
            min(instrument_variety / 8.0, 1.0),  # Normalize to 8 instruments max
            min(velocity_variance * 4, 1.0),  # Normalize variance
        ]
        overall_complexity = sum(complexity_factors) / len(complexity_factors)

        return {
            "overall_complexity": round(overall_complexity, 3),
            "note_density": round(note_density, 3),
            "instrument_variety": instrument_variety,
            "velocity_variance": round(velocity_variance, 3),
        }

    def _calculate_prompt_hash(self, input_data: Dict[str, Any]) -> str:
        """Calculate hash for AI prompt caching"""
        prompt_str = json.dumps(input_data, sort_keys=True)
        return hashlib.md5(prompt_str.encode()).hexdigest()

    async def _export_to_musicxml(
        self, notation: DrumNotation, options: Dict[str, Any]
    ) -> str:
        """Export notation to MusicXML format"""
        # Placeholder - would implement actual MusicXML generation
        return f"<musicxml>Placeholder for notation {notation.id}</musicxml>"

    async def _export_to_midi(
        self, notation: DrumNotation, options: Dict[str, Any]
    ) -> bytes:
        """Export notation to MIDI format"""
        # Placeholder - would implement actual MIDI generation
        return b"MIDI data placeholder"

    async def _export_to_json(
        self, notation: DrumNotation, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export notation to JSON format"""
        return {
            "notation_id": str(notation.id),
            "video_id": str(notation.video_id),
            "tempo": notation.tempo,
            "time_signature": notation.time_signature,
            "notation_data": notation.notation_json,
            "exported_at": datetime.utcnow().isoformat(),
        }

    async def _export_to_svg(
        self, notation: DrumNotation, options: Dict[str, Any]
    ) -> str:
        """Export notation to SVG format"""
        # Placeholder - would implement actual SVG generation using music notation library
        return f"<svg>Placeholder SVG for notation {notation.id}</svg>"
