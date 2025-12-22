"""
Notation Service
Handles drum notation generation, conversion, and OpenAI-powered enhancements
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.openai_service import OpenAIService
from app.modules.media.models import AudioFile, Video
from app.modules.notation.models import DrumEvent, Notation, OpenAIEnrichment

logger = logging.getLogger(__name__)


class NotationService:
    """Service for drum notation generation and management"""

    def __init__(self):
        self.openai_service = OpenAIService()

    async def create_notation_from_events(
        self,
        db: AsyncSession,
        video_id: uuid.UUID,
        drum_events: List[DrumEvent],
        tempo: Optional[int] = None,
        time_signature: str = "4/4",
    ) -> Notation:
        """Convert drum events to musical notation"""
        try:
            # Generate basic notation structure
            notation_data = await self._convert_events_to_notation(
                drum_events, tempo, time_signature
            )

            # Create notation record
            notation = Notation(
                video_id=video_id,
                tempo=tempo,
                time_signature=time_signature,
                notation_json=notation_data,
                model_version="v1.0",
                confidence_score=self._calculate_confidence_score(drum_events),
            )

            db.add(notation)
            await db.commit()
            await db.refresh(notation)

            logger.info(f"Created notation {notation.id} for video {video_id}")
            return notation

        except Exception as e:
            logger.error(f"Error creating notation: {e}")
            await db.rollback()
            raise

    async def enhance_notation_with_ai(
        self,
        db: AsyncSession,
        notation_id: uuid.UUID,
        enhancement_type: str = "full_analysis",
    ) -> Dict:
        """Enhance notation using OpenAI analysis"""
        try:
            # Get notation
            result = await db.execute(
                select(Notation).where(Notation.id == notation_id)
            )
            notation = result.scalar_one_or_none()

            if not notation:
                raise ValueError(f"Notation {notation_id} not found")

            if not self.openai_service.is_enabled():
                logger.warning("OpenAI service not available for enhancement")
                return {"error": "OpenAI service not configured"}

            # Prepare input data
            input_data = {
                "notation": notation.notation_json,
                "tempo": notation.tempo,
                "time_signature": notation.time_signature,
                "enhancement_type": enhancement_type,
            }

            # Check if we already have this enhancement
            prompt_hash = self._calculate_prompt_hash(input_data)
            existing = await self._get_existing_enrichment(db, notation_id, prompt_hash)

            if existing:
                logger.info(
                    f"Using cached OpenAI enrichment for notation {notation_id}"
                )
                return existing.output_json

            # Get AI enhancement
            if enhancement_type == "pattern_analysis":
                ai_result = await self.openai_service.analyze_drum_pattern(
                    notation.notation_json
                )
            elif enhancement_type == "style_classification":
                ai_result = await self.openai_service.classify_musical_style(
                    notation.notation_json
                )
            elif enhancement_type == "practice_instructions":
                ai_result = await self.openai_service.generate_practice_instructions(
                    notation.notation_json
                )
            else:  # full_analysis
                ai_result = await self._perform_full_ai_analysis(notation)

            # Save enrichment
            enrichment = OpenAIEnrichment(
                notation_id=notation_id,
                prompt_hash=prompt_hash,
                model=self.openai_service.model,
                input_json=input_data,
                output_json=ai_result,
            )

            db.add(enrichment)
            await db.commit()

            logger.info(f"Created OpenAI enrichment for notation {notation_id}")
            return ai_result

        except Exception as e:
            logger.error(f"Error enhancing notation with AI: {e}")
            await db.rollback()
            raise

    async def get_notation_with_enhancements(
        self, db: AsyncSession, notation_id: uuid.UUID
    ) -> Dict:
        """Get notation with all AI enhancements"""
        try:
            # Get notation
            result = await db.execute(
                select(Notation).where(Notation.id == notation_id)
            )
            notation = result.scalar_one_or_none()

            if not notation:
                raise ValueError(f"Notation {notation_id} not found")

            # Get all enrichments
            enrichments_result = await db.execute(
                select(OpenAIEnrichment)
                .where(OpenAIEnrichment.notation_id == notation_id)
                .order_by(desc(OpenAIEnrichment.created_at))
            )
            enrichments = enrichments_result.scalars().all()

            # Combine data
            response = {
                "notation": {
                    "id": str(notation.id),
                    "video_id": str(notation.video_id),
                    "tempo": notation.tempo,
                    "time_signature": notation.time_signature,
                    "notation_json": notation.notation_json,
                    "confidence_score": notation.confidence_score,
                    "created_at": notation.created_at.isoformat(),
                    "updated_at": notation.updated_at.isoformat(),
                },
                "ai_enhancements": [
                    {
                        "id": str(e.id),
                        "model": e.model,
                        "enhancement": e.output_json,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in enrichments
                ],
            }

            return response

        except Exception as e:
            logger.error(f"Error getting enhanced notation: {e}")
            raise

    async def export_notation(
        self, db: AsyncSession, notation_id: uuid.UUID, format_type: str = "musicxml"
    ) -> bytes:
        """Export notation to various formats"""
        try:
            # Get notation
            result = await db.execute(
                select(Notation).where(Notation.id == notation_id)
            )
            notation = result.scalar_one_or_none()

            if not notation:
                raise ValueError(f"Notation {notation_id} not found")

            if format_type.lower() == "musicxml":
                return await self._export_to_musicxml(notation)
            elif format_type.lower() == "midi":
                return await self._export_to_midi(notation)
            elif format_type.lower() == "json":
                return json.dumps(notation.notation_json, indent=2).encode("utf-8")
            else:
                raise ValueError(f"Unsupported export format: {format_type}")

        except Exception as e:
            logger.error(f"Error exporting notation: {e}")
            raise

    async def generate_practice_variations(
        self,
        db: AsyncSession,
        notation_id: uuid.UUID,
        difficulty_level: str = "intermediate",
    ) -> Dict:
        """Generate practice variations using AI"""
        try:
            # Get notation
            result = await db.execute(
                select(Notation).where(Notation.id == notation_id)
            )
            notation = result.scalar_one_or_none()

            if not notation:
                raise ValueError(f"Notation {notation_id} not found")

            if not self.openai_service.is_enabled():
                return {"error": "OpenAI service not configured"}

            # Generate variations
            variations = await self.openai_service.generate_pattern_variations(
                notation.notation_json, difficulty_level=difficulty_level
            )

            return variations

        except Exception as e:
            logger.error(f"Error generating practice variations: {e}")
            raise

    # Private helper methods

    async def _convert_events_to_notation(
        self, drum_events: List[DrumEvent], tempo: Optional[int], time_signature: str
    ) -> Dict:
        """Convert drum events to structured notation"""
        if not drum_events:
            return {"measures": [], "metadata": {"empty": True}}

        # Sort events by time
        sorted_events = sorted(drum_events, key=lambda x: x.time_seconds)

        # Estimate tempo if not provided
        if not tempo:
            tempo = self._estimate_tempo(sorted_events)

        # Calculate time signature components
        beats_per_measure, note_value = map(int, time_signature.split("/"))
        seconds_per_beat = 60.0 / tempo
        seconds_per_measure = seconds_per_beat * beats_per_measure

        # Group events into measures
        measures = []
        current_measure = 0
        current_events = []

        for event in sorted_events:
            event_measure = int(event.time_seconds / seconds_per_measure)

            if event_measure > current_measure:
                if current_events:
                    measures.append(
                        self._create_measure(
                            current_events,
                            current_measure,
                            seconds_per_beat,
                            beats_per_measure,
                        )
                    )
                current_measure = event_measure
                current_events = []

            current_events.append(event)

        # Add final measure
        if current_events:
            measures.append(
                self._create_measure(
                    current_events, current_measure, seconds_per_beat, beats_per_measure
                )
            )

        return {
            "measures": measures,
            "metadata": {
                "tempo": tempo,
                "time_signature": time_signature,
                "total_measures": len(measures),
                "total_events": len(sorted_events),
                "duration_seconds": sorted_events[-1].time_seconds
                if sorted_events
                else 0,
            },
        }

    def _create_measure(
        self,
        events: List[DrumEvent],
        measure_number: int,
        seconds_per_beat: float,
        beats_per_measure: int,
    ) -> Dict:
        """Create a single measure from events"""
        beats = []

        for beat_num in range(beats_per_measure):
            beat_start = (
                measure_number * beats_per_measure * seconds_per_beat
                + beat_num * seconds_per_beat
            )
            beat_end = beat_start + seconds_per_beat

            # Find events in this beat
            beat_events = [e for e in events if beat_start <= e.time_seconds < beat_end]

            # Group events by sub-beat position
            beat_data = {
                "beat_number": beat_num + 1,
                "events": [
                    {
                        "instrument": event.instrument,
                        "velocity": event.velocity or 0.5,
                        "position": (event.time_seconds - beat_start)
                        / seconds_per_beat,
                        "confidence": event.confidence or 0.8,
                    }
                    for event in beat_events
                ],
            }

            beats.append(beat_data)

        return {
            "measure_number": measure_number + 1,
            "beats": beats,
            "total_events": len(events),
        }

    def _estimate_tempo(self, events: List[DrumEvent]) -> int:
        """Estimate tempo from drum events"""
        if len(events) < 4:
            return 120  # Default tempo

        # Calculate intervals between events
        intervals = []
        for i in range(1, len(events)):
            interval = events[i].time_seconds - events[i - 1].time_seconds
            if 0.2 < interval < 2.0:  # Reasonable beat intervals
                intervals.append(interval)

        if not intervals:
            return 120

        # Find most common interval (approximate)
        intervals.sort()
        median_interval = intervals[len(intervals) // 2]

        # Convert to BPM
        estimated_bpm = 60.0 / median_interval

        # Round to reasonable BPM values
        if estimated_bpm < 80:
            return 80
        elif estimated_bpm > 200:
            return 200
        else:
            return round(estimated_bpm)

    def _calculate_confidence_score(self, events: List[DrumEvent]) -> float:
        """Calculate overall confidence score for notation"""
        if not events:
            return 0.0

        confidences = [e.confidence for e in events if e.confidence is not None]
        if not confidences:
            return 0.8  # Default confidence

        return sum(confidences) / len(confidences)

    def _calculate_prompt_hash(self, input_data: Dict) -> str:
        """Calculate hash of input data for caching"""
        prompt_str = json.dumps(input_data, sort_keys=True)
        return hashlib.sha256(prompt_str.encode()).hexdigest()

    async def _get_existing_enrichment(
        self, db: AsyncSession, notation_id: uuid.UUID, prompt_hash: str
    ) -> Optional[OpenAIEnrichment]:
        """Check for existing OpenAI enrichment"""
        result = await db.execute(
            select(OpenAIEnrichment).where(
                and_(
                    OpenAIEnrichment.notation_id == notation_id,
                    OpenAIEnrichment.prompt_hash == prompt_hash,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _perform_full_ai_analysis(self, notation: Notation) -> Dict:
        """Perform comprehensive AI analysis"""
        results = {}

        try:
            # Pattern analysis
            results[
                "pattern_analysis"
            ] = await self.openai_service.analyze_drum_pattern(notation.notation_json)
        except Exception as e:
            logger.warning(f"Pattern analysis failed: {e}")
            results["pattern_analysis"] = {"error": str(e)}

        try:
            # Style classification
            results[
                "style_classification"
            ] = await self.openai_service.classify_musical_style(notation.notation_json)
        except Exception as e:
            logger.warning(f"Style classification failed: {e}")
            results["style_classification"] = {"error": str(e)}

        try:
            # Practice instructions
            results[
                "practice_instructions"
            ] = await self.openai_service.generate_practice_instructions(
                notation.notation_json
            )
        except Exception as e:
            logger.warning(f"Practice instructions failed: {e}")
            results["practice_instructions"] = {"error": str(e)}

        return results

    async def _export_to_musicxml(self, notation: Notation) -> bytes:
        """Export notation to MusicXML format"""
        # Basic MusicXML structure
        musicxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work>
    <work-title>Drum Notation</work-title>
  </work>
  <identification>
    <creator type="software">Drum Notation Backend</creator>
  </identification>
  <part-list>
    <score-part id="P1">
      <part-name>Drums</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key>
          <fifths>0</fifths>
        </key>
        <time>
          <beats>{notation.time_signature.split("/")[0] if notation.time_signature else "4"}</beats>
          <beat-type>{notation.time_signature.split("/")[1] if notation.time_signature else "4"}</beat-type>
        </time>
        <clef>
          <sign>percussion</sign>
        </clef>
      </attributes>
      <note>
        <rest/>
        <duration>16</duration>
      </note>
    </measure>
  </part>
</score-partwise>"""

        return musicxml.encode("utf-8")

    async def _export_to_midi(self, notation: Notation) -> bytes:
        """Export notation to MIDI format"""
        # Basic MIDI header (this is a simplified version)
        midi_data = bytearray(
            [
                0x4D,
                0x54,
                0x68,
                0x64,  # "MThd"
                0x00,
                0x00,
                0x00,
                0x06,  # Header length
                0x00,
                0x00,  # Format 0
                0x00,
                0x01,  # 1 track
                0x01,
                0xE0,  # 480 ticks per quarter note
                0x4D,
                0x54,
                0x72,
                0x6B,  # "MTrk"
                0x00,
                0x00,
                0x00,
                0x04,  # Track length
                0x00,
                0xFF,
                0x2F,
                0x00,  # End of track
            ]
        )

        return bytes(midi_data)
