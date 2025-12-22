"""
Notation Repository
Database access layer for drum notation operations aligned with actual database schema
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.notation.models import DrumNotation, OpenAIEnrichment


class DrumNotationRepository:
    """Repository for drum notation operations"""

    def __init__(self):
        pass

    async def create_notation(
        self,
        db: AsyncSession,
        video_id: UUID,
        tempo: Optional[int] = None,
        time_signature: Optional[str] = None,
        notation_json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> DrumNotation:
        """Create a new drum notation record"""
        notation_data = notation_json or {}

        notation = DrumNotation(
            video_id=video_id,
            tempo=tempo,
            time_signature=time_signature,
            notation_json=notation_data,
            **kwargs,
        )
        db.add(notation)
        await db.commit()
        await db.refresh(notation)
        return notation

    async def get_by_video_id(
        self, db: AsyncSession, video_id: UUID
    ) -> Optional[DrumNotation]:
        """Get notation by video ID"""
        query = select(DrumNotation).where(
            and_(
                DrumNotation.video_id == video_id,
                DrumNotation.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_enrichments(
        self, db: AsyncSession, notation_id: UUID
    ) -> Optional[DrumNotation]:
        """Get notation with OpenAI enrichments loaded"""
        query = (
            select(DrumNotation)
            .options(selectinload(DrumNotation.openai_enrichments))
            .where(
                and_(
                    DrumNotation.id == notation_id,
                    DrumNotation.deleted_at.is_(None),
                )
            )
        )
        result = await db.execute(query)
        notation = result.scalar_one_or_none()

        # Filter out deleted enrichments in Python since we can't use where() on selectinload
        if notation and notation.openai_enrichments:
            notation.openai_enrichments = [
                enrichment
                for enrichment in notation.openai_enrichments
                if enrichment.deleted_at is None
            ]

        return notation

    async def update_notation_json(
        self, db: AsyncSession, notation_id: UUID, notation_json: Dict[str, Any]
    ) -> Optional[DrumNotation]:
        """Update the notation JSON data"""
        query = (
            update(DrumNotation)
            .where(
                and_(
                    DrumNotation.id == notation_id,
                    DrumNotation.deleted_at.is_(None),
                )
            )
            .values(
                notation_json=notation_json,
                updated_at=datetime.utcnow(),
            )
            .returning(DrumNotation)
        )
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    async def update_tempo_and_time_signature(
        self,
        db: AsyncSession,
        notation_id: UUID,
        tempo: Optional[int] = None,
        time_signature: Optional[str] = None,
    ) -> Optional[DrumNotation]:
        """Update tempo and time signature"""
        update_data: Dict[str, Any] = {"updated_at": datetime.utcnow()}

        if tempo is not None:
            update_data["tempo"] = tempo
        if time_signature is not None:
            update_data["time_signature"] = time_signature

        query = (
            update(DrumNotation)
            .where(
                and_(
                    DrumNotation.id == notation_id,
                    DrumNotation.deleted_at.is_(None),
                )
            )
            .values(**update_data)
            .returning(DrumNotation)
        )
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    async def list_by_user_videos(
        self, db: AsyncSession, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[DrumNotation]:
        """Get notations for videos owned by a specific user"""
        # This requires joining with videos table to check user_id
        from app.modules.media.models import Video

        query = (
            select(DrumNotation)
            .join(Video, DrumNotation.video_id == Video.id)
            .where(
                and_(
                    Video.user_id == user_id,
                    DrumNotation.deleted_at.is_(None),
                    Video.deleted_at.is_(None),
                )
            )
            .order_by(desc(DrumNotation.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_recent_notations(
        self, db: AsyncSession, limit: int = 10
    ) -> List[DrumNotation]:
        """Get recently created notations"""
        query = (
            select(DrumNotation)
            .where(DrumNotation.deleted_at.is_(None))
            .order_by(desc(DrumNotation.created_at))
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


class OpenAIEnrichmentRepository:
    """Repository for OpenAI enrichment operations"""

    def __init__(self):
        pass

    async def create_enrichment(
        self,
        db: AsyncSession,
        notation_id: UUID,
        prompt_hash: str,
        model: str,
        input_json: Dict[str, Any],
        output_json: Dict[str, Any],
        **kwargs,
    ) -> OpenAIEnrichment:
        """Create a new OpenAI enrichment record"""
        enrichment = OpenAIEnrichment(
            notation_id=notation_id,
            prompt_hash=prompt_hash,
            model=model,
            input_json=input_json,
            output_json=output_json,
            **kwargs,
        )
        db.add(enrichment)
        await db.commit()
        await db.refresh(enrichment)
        return enrichment

    async def get_by_prompt_hash(
        self, db: AsyncSession, notation_id: UUID, prompt_hash: str
    ) -> Optional[OpenAIEnrichment]:
        """Get enrichment by notation ID and prompt hash (for caching)"""
        query = select(OpenAIEnrichment).where(
            and_(
                OpenAIEnrichment.notation_id == notation_id,
                OpenAIEnrichment.prompt_hash == prompt_hash,
                OpenAIEnrichment.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_notation_id(
        self, db: AsyncSession, notation_id: UUID
    ) -> List[OpenAIEnrichment]:
        """Get all enrichments for a notation"""
        query = (
            select(OpenAIEnrichment)
            .where(
                and_(
                    OpenAIEnrichment.notation_id == notation_id,
                    OpenAIEnrichment.deleted_at.is_(None),
                )
            )
            .order_by(desc(OpenAIEnrichment.created_at))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_recent_enrichments(
        self, db: AsyncSession, limit: int = 10
    ) -> List[OpenAIEnrichment]:
        """Get recent enrichments across all notations"""
        query = (
            select(OpenAIEnrichment)
            .where(OpenAIEnrichment.deleted_at.is_(None))
            .order_by(desc(OpenAIEnrichment.created_at))
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


# Helper repositories for data that doesn't have dedicated tables
# but needs to be managed within the JSON structure


class StrokeEventRepository:
    """Repository-like interface for stroke events stored in notation JSON"""

    @staticmethod
    def get_stroke_events(notation: DrumNotation) -> List[Dict[str, Any]]:
        """Extract stroke events from notation JSON"""
        return notation.get_timeline()

    @staticmethod
    def set_stroke_events(notation: DrumNotation, events: List[Dict[str, Any]]) -> None:
        """Update stroke events in notation JSON"""
        notation.set_timeline(events)

    @staticmethod
    def add_stroke_event(notation: DrumNotation, event: Dict[str, Any]) -> None:
        """Add a single stroke event to notation JSON"""
        events = notation.get_timeline()
        events.append(event)
        # Sort by timestamp
        events.sort(key=lambda x: x.get("timestamp_seconds", 0))
        notation.set_timeline(events)


class NotationMeasureRepository:
    """Repository-like interface for measures stored in notation JSON"""

    @staticmethod
    def get_measures(notation: DrumNotation) -> List[Dict[str, Any]]:
        """Extract measures from notation JSON"""
        return notation.get_measures()

    @staticmethod
    def set_measures(notation: DrumNotation, measures: List[Dict[str, Any]]) -> None:
        """Update measures in notation JSON"""
        notation.set_measures(measures)

    @staticmethod
    def get_measure_by_number(
        notation: DrumNotation, measure_number: int
    ) -> Optional[Dict[str, Any]]:
        """Get a specific measure by number"""
        measures = notation.get_measures()
        for measure in measures:
            if measure.get("measure_number") == measure_number:
                return measure
        return None


class NotationBeatRepository:
    """Repository-like interface for beats stored in notation JSON"""

    @staticmethod
    def get_beats_for_measure(
        notation: DrumNotation, measure_number: int
    ) -> List[Dict[str, Any]]:
        """Extract beats for a specific measure from notation JSON"""
        measure = NotationMeasureRepository.get_measure_by_number(
            notation, measure_number
        )
        if measure:
            return measure.get("beats", [])
        return []

    @staticmethod
    def set_beats_for_measure(
        notation: DrumNotation, measure_number: int, beats: List[Dict[str, Any]]
    ) -> None:
        """Update beats for a specific measure in notation JSON"""
        measures = notation.get_measures()
        for measure in measures:
            if measure.get("measure_number") == measure_number:
                measure["beats"] = beats
                break
        notation.set_measures(measures)


class DrumNoteRepository:
    """Repository-like interface for drum notes stored in notation JSON"""

    @staticmethod
    def get_notes_for_beat(
        notation: DrumNotation, measure_number: int, beat_number: float
    ) -> List[Dict[str, Any]]:
        """Extract notes for a specific beat from notation JSON"""
        beats = NotationBeatRepository.get_beats_for_measure(notation, measure_number)
        for beat in beats:
            if beat.get("beat_number") == beat_number:
                return beat.get("notes", [])
        return []

    @staticmethod
    def add_note_to_beat(
        notation: DrumNotation,
        measure_number: int,
        beat_number: float,
        note: Dict[str, Any],
    ) -> None:
        """Add a note to a specific beat in notation JSON"""
        measures = notation.get_measures()
        for measure in measures:
            if measure.get("measure_number") == measure_number:
                beats = measure.get("beats", [])
                for beat in beats:
                    if beat.get("beat_number") == beat_number:
                        notes = beat.get("notes", [])
                        notes.append(note)
                        beat["notes"] = notes
                        break
                measure["beats"] = beats
                break
        notation.set_measures(measures)


class NotationExportRepository:
    """Repository-like interface for exports stored in notation JSON"""

    @staticmethod
    def get_exports(notation: DrumNotation) -> List[Dict[str, Any]]:
        """Extract exports from notation JSON"""
        if notation.notation_json is None:
            return []
        return notation.notation_json.get("exports", [])

    @staticmethod
    def set_exports(notation: DrumNotation, exports: List[Dict[str, Any]]) -> None:
        """Update exports in notation JSON"""
        if notation.notation_json is None:
            notation.notation_json = {}
        if isinstance(notation.notation_json, dict):
            notation.notation_json["exports"] = exports

    @staticmethod
    def add_export(notation: DrumNotation, export: Dict[str, Any]) -> None:
        """Add an export to notation JSON"""
        exports = NotationExportRepository.get_exports(notation)
        exports.append(export)
        NotationExportRepository.set_exports(notation, exports)

    @staticmethod
    def get_export_by_format(
        notation: DrumNotation, export_format: str
    ) -> Optional[Dict[str, Any]]:
        """Get export by format"""
        exports = NotationExportRepository.get_exports(notation)
        for export in exports:
            if export.get("export_format") == export_format:
                return export
        return None


class DrumKitMappingRepository:
    """Repository-like interface for drum kit mappings stored in notation JSON"""

    @staticmethod
    def get_drum_mapping(notation: DrumNotation) -> Dict[str, Any]:
        """Extract drum kit mapping from notation JSON"""
        if notation.notation_json is None:
            return {}
        return notation.notation_json.get("drum_mapping", {})

    @staticmethod
    def set_drum_mapping(notation: DrumNotation, mapping: Dict[str, Any]) -> None:
        """Update drum kit mapping in notation JSON"""
        if notation.notation_json is None:
            notation.notation_json = {}
        if isinstance(notation.notation_json, dict):
            notation.notation_json["drum_mapping"] = mapping

    @staticmethod
    def get_default_mapping() -> Dict[str, Any]:
        """Get default drum kit mapping"""
        return {
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
