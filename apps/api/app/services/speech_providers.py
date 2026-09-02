import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    confidence: float | None
    provider: str
    model: str
    latency_ms: int


class SpeechToTextProvider(Protocol):
    provider_name: str
    model_name: str

    async def transcribe(self, audio_path: Path, content_type: str) -> TranscriptionResult: ...


class MockSpeechToTextProvider:
    provider_name = "mock"
    model_name = "deterministic-development-transcriber-v1"

    async def transcribe(self, audio_path: Path, content_type: str) -> TranscriptionResult:
        del audio_path, content_type
        started = time.monotonic()
        return TranscriptionResult(
            text=(
                "Ich arbeite als Softwareentwickler und erkläre meine Projekte "
                "strukturiert. Zuerst beschreibe ich das Problem, dann meine Lösung "
                "und am Ende das Ergebnis."
            ),
            language="de",
            confidence=1.0,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=max(1, int((time.monotonic() - started) * 1000)),
        )


class OpenAISpeechToTextProvider:
    provider_name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI transcription")
        self.model_name = settings.openai_transcription_model
        self.api_key = settings.openai_api_key.get_secret_value()
        self.timeout = settings.speech_provider_timeout_seconds

    async def transcribe(self, audio_path: Path, content_type: str) -> TranscriptionResult:
        started = time.monotonic()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with audio_path.open("rb") as audio:
            files = {
                "file": (
                    audio_path.name,
                    audio,
                    content_type,
                )
            }
            data = {
                "model": self.model_name,
                "language": "de",
                "response_format": "json",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                )
        response.raise_for_status()
        payload = response.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            raise RuntimeError("Transcription provider returned an empty transcript")
        return TranscriptionResult(
            text=text,
            language=str(payload.get("language") or "de"),
            confidence=None,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=max(1, int((time.monotonic() - started) * 1000)),
        )


def get_speech_to_text_provider() -> SpeechToTextProvider:
    provider = get_settings().speech_transcription_provider
    if provider == "openai":
        return OpenAISpeechToTextProvider()
    if provider == "mock":
        return MockSpeechToTextProvider()
    raise RuntimeError(f"Unsupported speech transcription provider: {provider}")
