"""
Notation Router
API endpoints for drum notation generation, management, and AI-powered enhancements
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.notation.schemas import (
    DetailedNotationResponse,
    DrumEventCreate,
    DrumEventResponse,
    NotationAnalysisResponse,
    NotationCreate,
    NotationEnhancementRequest,
    NotationExportRequest,
    NotationFromEventsRequest,
    NotationListResponse,
    NotationResponse,
    NotationSearchRequest,
    NotationStatsResponse,
    NotationUpdate,
    NotationValidationResponse,
    NotationWithEnhancements,
    PracticeVariationsRequest,
)
from app.modules.notation.service import NotationService
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notation", tags=["notation"])


@router.post("/", response_model=NotationResponse, status_code=201)
async def create_notation(
    notation_data: NotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new notation record"""
    try:
        service = NotationService()

        # Verify video ownership (you may want to add this check)
        # video = await verify_video_ownership(db, notation_data.video_id, current_user.id)

        # Create notation from provided data
        from app.modules.notation.models import Notation

        notation = Notation(
            video_id=notation_data.video_id,
            tempo=notation_data.tempo,
            time_signature=notation_data.time_signature,
            notation_json=notation_data.notation_json,
            model_version=notation_data.model_version,
            confidence_score=notation_data.confidence_score,
        )

        db.add(notation)
        await db.commit()
        await db.refresh(notation)

        logger.info(f"Created notation {notation.id} for user {current_user.id}")
        return notation

    except Exception as e:
        logger.error(f"Error creating notation: {e}")
        raise HTTPException(status_code=500, detail="Error creating notation")


@router.post("/from-events", response_model=NotationResponse, status_code=201)
async def create_notation_from_events(
    request: NotationFromEventsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate notation from detected drum events"""
    try:
        service = NotationService()

        # Get drum events for the video
        from sqlalchemy.future import select

        from app.modules.media.models import AudioFile
        from app.modules.notation.models import DrumEvent

        # Find audio files for this video
        audio_result = await db.execute(
            select(AudioFile).where(AudioFile.video_id == request.video_id)
        )
        audio_files = audio_result.scalars().all()

        if not audio_files:
            raise HTTPException(
                status_code=404, detail="No audio files found for video"
            )

        # Get all drum events
        drum_events = []
        for audio_file in audio_files:
            events_result = await db.execute(
                select(DrumEvent).where(DrumEvent.audio_file_id == audio_file.id)
            )
            drum_events.extend(events_result.scalars().all())

        if not drum_events:
            raise HTTPException(status_code=404, detail="No drum events found")

        # Create notation
        notation = await service.create_notation_from_events(
            db=db,
            video_id=request.video_id,
            drum_events=drum_events,
            tempo=request.tempo,
            time_signature=request.time_signature,
        )

        return notation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notation from events: {e}")
        raise HTTPException(status_code=500, detail="Error processing drum events")


@router.get("/", response_model=NotationListResponse)
async def list_notations(
    search: NotationSearchRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's notations with optional filtering"""
    try:
        from sqlalchemy import and_, func
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        # Build query
        query = select(Notation).join(Video).where(Video.user_id == current_user.id)

        # Apply filters
        filters = []
        if search.video_id:
            filters.append(Notation.video_id == search.video_id)
        if search.tempo_min:
            filters.append(Notation.tempo >= search.tempo_min)
        if search.tempo_max:
            filters.append(Notation.tempo <= search.tempo_max)
        if search.time_signature:
            filters.append(Notation.time_signature == search.time_signature)

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(func.count(Notation.id)).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        query = query.offset(search.offset).limit(search.limit)

        # Execute query
        result = await db.execute(query)
        notations = result.scalars().all()

        return NotationListResponse(
            notations=notations,
            total=total,
            limit=search.limit,
            offset=search.offset,
            has_more=(search.offset + len(notations)) < total,
        )

    except Exception as e:
        logger.error(f"Error listing notations: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving notations")


@router.get("/{notation_id}", response_model=DetailedNotationResponse)
async def get_notation(
    notation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed notation by ID"""
    try:
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        # Get notation with ownership verification
        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Convert to detailed response
        return DetailedNotationResponse(
            id=notation.id,
            video_id=notation.video_id,
            measures=notation.notation_json.get("measures", []),
            metadata=notation.notation_json.get("metadata", {}),
            confidence_score=notation.confidence_score,
            model_version=notation.model_version,
            created_at=notation.created_at,
            updated_at=notation.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notation: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving notation")


@router.put("/{notation_id}", response_model=NotationResponse)
async def update_notation(
    notation_id: UUID,
    update_data: NotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update notation"""
    try:
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        # Get notation with ownership verification
        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Update fields
        if update_data.tempo is not None:
            notation.tempo = update_data.tempo
        if update_data.time_signature is not None:
            notation.time_signature = update_data.time_signature
        if update_data.notation_json is not None:
            notation.notation_json = update_data.notation_json

        await db.commit()
        await db.refresh(notation)

        logger.info(f"Updated notation {notation_id} for user {current_user.id}")
        return notation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notation: {e}")
        raise HTTPException(status_code=500, detail="Error updating notation")


@router.delete("/{notation_id}", status_code=204)
async def delete_notation(
    notation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete notation"""
    try:
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        # Get notation with ownership verification
        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Soft delete
        notation.deleted_at = func.now()
        await db.commit()

        logger.info(f"Deleted notation {notation_id} for user {current_user.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notation: {e}")
        raise HTTPException(status_code=500, detail="Error deleting notation")


# OpenAI-powered endpoints


@router.post("/{notation_id}/enhance", response_model=NotationAnalysisResponse)
async def enhance_notation_with_ai(
    notation_id: UUID,
    request: NotationEnhancementRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enhance notation using OpenAI analysis"""
    try:
        service = NotationService()

        # Verify ownership
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Enhance with AI
        enhancement = await service.enhance_notation_with_ai(
            db=db,
            notation_id=notation_id,
            enhancement_type=request.enhancement_type,
        )

        logger.info(
            f"Enhanced notation {notation_id} with AI for user {current_user.id}"
        )
        return NotationAnalysisResponse(**enhancement)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enhancing notation with AI: {e}")
        raise HTTPException(status_code=500, detail="Error processing AI enhancement")


@router.get("/{notation_id}/with-enhancements", response_model=NotationWithEnhancements)
async def get_notation_with_enhancements(
    notation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get notation with all AI enhancements"""
    try:
        service = NotationService()

        # Verify ownership (basic check)
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Get enhanced data
        enhanced_data = await service.get_notation_with_enhancements(
            db=db, notation_id=notation_id
        )

        return NotationWithEnhancements(**enhanced_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced notation: {e}")
        raise HTTPException(
            status_code=500, detail="Error retrieving enhanced notation"
        )


@router.post("/{notation_id}/variations", response_model=NotationAnalysisResponse)
async def generate_practice_variations(
    notation_id: UUID,
    request: PracticeVariationsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate AI-powered practice variations"""
    try:
        service = NotationService()

        # Verify ownership
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Generate variations
        variations = await service.generate_practice_variations(
            db=db,
            notation_id=notation_id,
            difficulty_level=request.difficulty_level,
        )

        logger.info(
            f"Generated variations for notation {notation_id} for user {current_user.id}"
        )
        return NotationAnalysisResponse(variations=[variations])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating variations: {e}")
        raise HTTPException(
            status_code=500, detail="Error generating practice variations"
        )


@router.get("/{notation_id}/export")
async def export_notation(
    notation_id: UUID,
    request: NotationExportRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export notation to various formats"""
    try:
        service = NotationService()

        # Verify ownership
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Export
        exported_data = await service.export_notation(
            db=db, notation_id=notation_id, format_type=request.format_type
        )

        # Set appropriate headers
        if request.format_type == "musicxml":
            media_type = "application/vnd.recordare.musicxml+xml"
            filename = f"notation_{notation_id}.xml"
        elif request.format_type == "midi":
            media_type = "audio/midi"
            filename = f"notation_{notation_id}.mid"
        else:  # json
            media_type = "application/json"
            filename = f"notation_{notation_id}.json"

        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

        logger.info(
            f"Exported notation {notation_id} as {request.format_type} for user {current_user.id}"
        )
        return Response(
            content=exported_data,
            media_type=media_type,
            headers=headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting notation: {e}")
        raise HTTPException(status_code=500, detail="Error exporting notation")


@router.get("/{notation_id}/validate", response_model=NotationValidationResponse)
async def validate_notation(
    notation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate notation structure and content"""
    try:
        from sqlalchemy.future import select

        from app.modules.media.models import Video
        from app.modules.notation.models import Notation

        # Get notation with ownership verification
        result = await db.execute(
            select(Notation)
            .join(Video)
            .where(and_(Notation.id == notation_id, Video.user_id == current_user.id))
        )
        notation = result.scalar_one_or_none()

        if not notation:
            raise HTTPException(status_code=404, detail="Notation not found")

        # Basic validation
        errors = []
        warnings = []
        suggestions = []

        # Check required fields
        if not notation.notation_json:
            errors.append(
                {
                    "field": "notation_json",
                    "message": "Notation data is empty",
                    "value": None,
                }
            )

        # Check tempo
        if notation.tempo and (notation.tempo < 60 or notation.tempo > 200):
            warnings.append(f"Unusual tempo: {notation.tempo} BPM")

        # Check confidence
        if notation.confidence_score and notation.confidence_score < 0.7:
            warnings.append(f"Low confidence score: {notation.confidence_score}")
            suggestions.append("Consider re-analyzing the audio with better quality")

        is_valid = len(errors) == 0

        return NotationValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating notation: {e}")
        raise HTTPException(status_code=500, detail="Error validating notation")


@router.get("/stats/overview", response_model=NotationStatsResponse)
async def get_notation_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user's notation statistics"""
    try:
        from sqlalchemy import distinct, func
        from sqlalchemy.future import select

        from app.modules.media.models import AudioFile, Video
        from app.modules.notation.models import DrumEvent, Notation

        # Get total notations
        notations_result = await db.execute(
            select(func.count(Notation.id))
            .select_from(Notation)
            .join(Video)
            .where(Video.user_id == current_user.id)
        )
        total_notations = notations_result.scalar() or 0

        # Get total events
        events_result = await db.execute(
            select(func.count(DrumEvent.id))
            .select_from(DrumEvent)
            .join(AudioFile)
            .join(Video)
            .where(Video.user_id == current_user.id)
        )
        total_events = events_result.scalar() or 0

        # Get average tempo
        avg_tempo_result = await db.execute(
            select(func.avg(Notation.tempo))
            .select_from(Notation)
            .join(Video)
            .where(and_(Video.user_id == current_user.id, Notation.tempo.is_not(None)))
        )
        avg_tempo = avg_tempo_result.scalar()

        # Get common time signatures
        ts_result = await db.execute(
            select(Notation.time_signature, func.count(Notation.id).label("count"))
            .select_from(Notation)
            .join(Video)
            .where(
                and_(
                    Video.user_id == current_user.id,
                    Notation.time_signature.is_not(None),
                )
            )
            .group_by(Notation.time_signature)
            .order_by(func.count(Notation.id).desc())
            .limit(5)
        )
        common_time_signatures = [
            {"time_signature": row[0], "count": row[1]} for row in ts_result.fetchall()
        ]

        # Get instruments detected
        instruments_result = await db.execute(
            select(distinct(DrumEvent.instrument))
            .select_from(DrumEvent)
            .join(AudioFile)
            .join(Video)
            .where(Video.user_id == current_user.id)
        )
        instruments_detected = [row[0] for row in instruments_result.fetchall()]

        return NotationStatsResponse(
            total_notations=total_notations,
            total_events=total_events,
            avg_tempo=avg_tempo,
            common_time_signatures=common_time_signatures,
            instruments_detected=instruments_detected,
            confidence_distribution={
                "high": 0,  # Placeholder - you can implement proper calculation
                "medium": 0,
                "low": 0,
            },
        )

    except Exception as e:
        logger.error(f"Error getting notation statistics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")
