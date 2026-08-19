"""Speech and conversation WebSocket endpoints."""

import json
import logging
import time
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import AuthUser, get_current_user, verify_token
from ..core.config import get_settings
from ..core.database import SessionLocal, get_db
from ..models.orm import SpeakingSession
from ..models.schemas import (
    ConversationCreate,
    ConversationSession,
    SpeechDrillCreate,
    SpeechDrillSession,
)
from ..services.qwen import QwenRealtimeGateway, transcribe_cantonese

logger = logging.getLogger("canto.speech")
router = APIRouter(prefix="/speech", tags=["speech"])
settings = get_settings()
gateway = QwenRealtimeGateway()

SCENARIOS = {
    "restaurant-order": {
        "title": "Ordering food",
        "vocab": ["食", "飲", "要", "唔該", "幾多錢"],
        "grammar": ["我要...", "唔該", "幾多錢"],
    },
    "greeting-friend": {
        "title": "Meeting a friend",
        "vocab": ["你好", "最近", "好忙", "得閒"],
        "grammar": ["你最近點呀", "我...緊"],
    },
}


@router.post("/conversations", response_model=ConversationSession)
async def create_conversation(
    body: ConversationCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    scenario = SCENARIOS.get(body.scenario_id)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    target = body.target_vocab or scenario["vocab"]
    session = SpeakingSession(
        user_id=user.id,
        session_type="conversation",
        scenario_id=body.scenario_id,
        target_vocab=target,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    instructions = gateway.build_instructions(
        scenario["title"],
        target,
        body.grammar_limits or scenario["grammar"],
    )
    return ConversationSession(
        id=session.id,
        scenario_id=body.scenario_id,
        target_vocab=target,
        ws_url=f"/speech/conversations/{session.id}/ws",
        instructions=instructions,
    )


@router.post("/drills", response_model=SpeechDrillSession)
async def create_drill(
    body: SpeechDrillCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session = SpeakingSession(
        user_id=user.id,
        session_type="drill",
        lesson_id=body.lesson_id,
        target_vocab=[body.expected_text],
        transcript_json=[{"expected": body.expected_text, "jyutping": body.expected_jyutping}],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SpeechDrillSession(id=session.id, ws_url=f"/speech/drills/{session.id}/ws")


@router.post("/drills/assess")
async def assess_drill(
    audio: Annotated[UploadFile, File()],
    expected_text: Annotated[str, Form()],
    user: Annotated[AuthUser, Depends(get_current_user)],
    expected_jyutping: Annotated[str, Form()] = "",
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "No audio received")
    transcript = await transcribe_cantonese(audio_bytes)
    return {
        "transcript": transcript or "",
        "expected_text": expected_text,
        "expected_jyutping": expected_jyutping,
        "feedback": (
            "Speech captured. Compare it with the model and retry if needed."
            if transcript
            else "We could not hear that clearly. Try again closer to the microphone."
        ),
    }


@router.websocket("/conversations/{session_id}/ws")
async def conversation_ws(websocket: WebSocket, session_id: UUID):
    authorization = websocket.headers.get("authorization", "")
    token = (
        authorization[7:]
        if authorization.lower().startswith("bearer ")
        else websocket.query_params.get("token")
    )
    if not token:
        await websocket.close(code=4401, reason="Bearer authentication required")
        return
    async with SessionLocal() as auth_db:
        try:
            user = await verify_token(token, auth_db)
        except HTTPException:
            await websocket.close(code=4401, reason="Invalid or expired access token")
            return

    await websocket.accept()
    start = time.time()
    max_seconds = settings.max_conversation_minutes * 60
    transcript: list[dict] = []
    vocab_used: list[str] = []

    async def forward_to_client(event: dict) -> None:
        await websocket.send_json(event)
        etype = event.get("type", "")
        if etype == "response.audio_transcript.done":
            transcript.append({"role": "assistant", "text": event.get("transcript", "")})
        elif etype == "conversation.item.input_audio_transcription.completed":
            text = event.get("transcript", "")
            transcript.append({"role": "user", "text": text})

    qwen_ws = None
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(SpeakingSession).where(
                    SpeakingSession.id == session_id,
                    SpeakingSession.user_id == user.id,
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                await websocket.close(code=4404)
                return
            scenario = SCENARIOS.get(session.scenario_id or "", {})
            instructions = gateway.build_instructions(
                scenario.get("title", "Cantonese practice"),
                session.target_vocab or [],
                [],
            )

        qwen_ws = await gateway.connect_session(instructions, forward_to_client)

        while True:
            if time.time() - start > max_seconds:
                await websocket.send_json({"type": "session.timeout", "message": "Time limit reached"})
                break
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes"):
                await gateway.send_audio(qwen_ws, message["bytes"])
            elif message.get("text"):
                data = json.loads(message["text"])
                if data.get("type") == "close":
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Conversation WebSocket error")
        await websocket.send_json({"type": "error", "message": str(exc)})
    finally:
        if qwen_ws:
            await qwen_ws.close()
        async with SessionLocal() as db:
            result = await db.execute(
                select(SpeakingSession).where(
                    SpeakingSession.id == session_id,
                    SpeakingSession.user_id == user.id,
                )
            )
            session = result.scalar_one_or_none()
            if session:
                for entry in transcript:
                    if entry["role"] == "user":
                        for v in session.target_vocab or []:
                            if v in entry["text"] and v not in vocab_used:
                                vocab_used.append(v)
                session.transcript_json = transcript
                session.vocab_used = vocab_used
                session.duration_seconds = int(time.time() - start)
                session.feedback = (
                    f"Used {len(vocab_used)}/{len(session.target_vocab or [])} target words."
                )
                await db.commit()
                transcript_dir = Path(settings.local_user_dir) / "transcripts"
                transcript_dir.mkdir(parents=True, exist_ok=True)
                transcript_file = transcript_dir / f"{session.id}.json"
                transcript_file.write_text(
                    json.dumps(
                        {
                            "session_id": str(session.id),
                            "scenario_id": session.scenario_id,
                            "target_vocab": session.target_vocab,
                            "vocab_used": vocab_used,
                            "duration_seconds": session.duration_seconds,
                            "feedback": session.feedback,
                            "transcript": transcript,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        await websocket.close()
