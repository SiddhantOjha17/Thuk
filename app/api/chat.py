"""Chat endpoints — text, voice, image input to the agent."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import process_message
from app.auth.dependencies import get_current_user
from app.database.base import get_db
from app.database.models import User
from app.database.schemas import ChatMessageRequest, ChatResponse
from app.processors.image_processor import ImageProcessor
from app.processors.voice_processor import VoiceProcessor
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    body: ChatMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Process a plain text message through the agent."""
    response = await process_message(body.text, user, db, source_type="text")
    return ChatResponse(response=response)


@router.post("/voice", response_model=ChatResponse)
async def chat_voice(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe an audio file and process through the agent."""
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File must be an audio type",
        )

    audio_data = await file.read()
    if len(audio_data) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file too large (max 25 MB)",
        )

    processor = VoiceProcessor(user)
    transcript = await processor.transcribe(audio_data)

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not transcribe audio. Please try again.",
        )

    response = await process_message(transcript, user, db, source_type="voice")
    return ChatResponse(response=response)


@router.post("/image", response_model=ChatResponse)
async def chat_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract transaction details from an image and process through the agent."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File must be an image type",
        )

    image_data = await file.read()
    if len(image_data) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large (max 25 MB)",
        )

    processor = ImageProcessor(user)
    extracted = await processor.extract_text(image_data)

    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract transaction details from image.",
        )

    response = await process_message(
        f"[From bank transaction screenshot]: {extracted}",
        user,
        db,
        source_type="image",
    )
    return ChatResponse(response=response)
