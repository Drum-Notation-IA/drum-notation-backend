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
    ) -> DrumNotation:
        """
        Generate complete musical notation from drum detection results
        """
        try:
            # Validate input
            if not drum_events:
                raise HTTPException(
                    status_code=400, detail="No drum events provided for notation"
                )

            # Calculate basic metrics
            estimated_tempo = tempo_bpm or self._estimate_tempo_from_events(drum_events)

            # Generate the complete notation structure
            notation_json = await self._generate_complete_notation(
                drum_events, estimated_tempo, time_signature, quantization_level
            )

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
    ) -> Dict[str, Any]:
        """
        Generate complete notation structure as JSON
        """
        # Generate musical structure
        musical_structure = self._generate_musical_structure(
            drum_events, tempo_bpm, time_signature, quantization_level
        )

        # Generate stroke timeline
        timeline = self._generate_stroke_timeline(drum_events, musical_structure)

        # Generate measures with beats and notes
        measures = self._generate_measures_from_events(
            drum_events, tempo_bpm, time_signature, quantization_level
        )

        # Build complete notation JSON
        notation_json = {
            "musical_structure": musical_structure,
            "timeline": timeline,
            "measures": measures,
            "drum_mapping": self.default_drum_mapping,
            "metadata": {
                "total_duration_seconds": max(
                    event.get("time_seconds", 0) for event in drum_events
                )
                if drum_events
                else 0,
                "total_measures": len(measures),
                "total_events": len(drum_events),
                "quantization_level": quantization_level,
                "generated_at": datetime.utcnow().isoformat(),
            },
            "exports": [],  # Will be populated when exports are generated
        }

        return notation_json

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
        Organize events into beats within a measure
        """
        beats = []

        for beat_num in range(1, beats_per_measure + 1):
            beat_start = measure_start_time + (beat_num - 1) * seconds_per_beat
            beat_end = beat_start + seconds_per_beat

            # Get events in this beat
            beat_events = [
                event
                for event in events
                if beat_start <= event.get("time_seconds", 0) < beat_end
            ]

            # Convert events to notes
            notes = []
            for event in beat_events:
                instrument = event.get("instrument", "unknown")
                velocity = event.get("velocity", 0.5)

                drum_mapping = self.default_drum_mapping.get(
                    instrument,
                    {"staff_position": "C5", "note_head": "normal", "line": 3},
                )

                note = {
                    "drum_type": instrument,
                    "staff_position": drum_mapping["staff_position"],
                    "note_duration": "quarter",  # Default duration
                    "note_head_type": drum_mapping["note_head"],
                    "velocity": velocity,
                    "accent": "accent" if velocity > 0.8 else None,
                    "ghost_note": velocity < 0.3,
                    "confidence_score": event.get("confidence", None),
                    "timestamp_seconds": event.get("time_seconds", 0),
                }
                notes.append(note)

            beat_data = {
                "beat_number": beat_num,
                "start_time_seconds": beat_start,
                "end_time_seconds": beat_end,
                "notes": notes,
                "note_count": len(notes),
            }

            beats.append(beat_data)

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
        """Estimate tempo from drum events using inter-onset intervals"""
        if len(drum_events) < 2:
            return 120.0  # Default tempo

        # Get timestamps and sort
        timestamps = sorted([event.get("time_seconds", 0) for event in drum_events])

        # Calculate inter-onset intervals
        intervals = []
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i - 1]
            if 0.1 < interval < 2.0:  # Filter reasonable intervals
                intervals.append(interval)

        if not intervals:
            return 120.0

        # Find most common interval (tempo)
        avg_interval = sum(intervals) / len(intervals)
        estimated_bpm = 60.0 / avg_interval

        # Clamp to reasonable range
        return max(60.0, min(200.0, estimated_bpm))

    def _get_beats_per_measure(self, time_signature: str) -> int:
        """Get beats per measure from time signature"""
        try:
            numerator = int(time_signature.split("/")[0])
            return numerator
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
