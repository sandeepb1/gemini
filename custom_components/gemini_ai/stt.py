"""Speech-to-text platform for Gemini AI integration."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncIterable, Dict, Optional

from homeassistant.components.stt import (
    SpeechMetadata,
    SpeechResult,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import GeminiAPIClient, GeminiAPIError
from .const import (
    CONF_STT_MODEL,
    CONF_LANGUAGE,
    DEFAULT_STT_MODEL,
    DEFAULT_LANGUAGE,
    SUPPORTED_AUDIO_FORMATS,
    MAX_AUDIO_SIZE,
    AUDIO_CHUNK_SIZE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gemini STT platform via config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api_client = data["api_client"]
    config = data["config"]
    
    stt_entity = GeminiSTTEntity(
        api_client=api_client,
        config=config,
        entry_id=config_entry.entry_id,
        hass=hass,
    )
    
    async_add_entities([stt_entity])


class GeminiSTTEntity(SpeechToTextEntity):
    """Gemini AI Speech-to-Text entity."""

    def __init__(
        self,
        api_client: GeminiAPIClient,
        config: Dict[str, Any],
        entry_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the STT entity."""
        self._api_client = api_client
        self._config = config
        self._entry_id = entry_id
        self._hass = hass
        
        # STT settings
        self._model = config.get(CONF_STT_MODEL, DEFAULT_STT_MODEL)
        self._language = config.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Gemini AI STT"

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{DOMAIN}_{self._entry_id}_stt"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        # Gemini supports many languages for STT
        return [
            "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh",
            "ar", "hi", "th", "vi", "tr", "pl", "nl", "sv", "da", "no",
            "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv",
            "lt", "mt", "ga", "is", "mk", "sq", "sr", "bs", "me", "uk",
            "be", "kk", "ky", "uz", "tg", "mn", "ka", "hy", "az", "eu",
            "ca", "gl", "cy", "br", "co", "eo", "ia", "ie", "ig", "mg",
            "mi", "ms", "sw", "zu", "xh", "af", "am", "bn", "gu", "he",
            "kn", "ml", "mr", "ne", "or", "pa", "si", "ta", "te", "ur"
        ]

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._language

    @property
    def supported_formats(self) -> list[str]:
        """Return a list of supported formats."""
        # Simplified to only support WAV as requested
        return ["wav"]

    @property
    def supported_codecs(self) -> list[str]:
        """Return a list of supported codecs."""
        return ["pcm"]

    @property
    def supported_bit_rates(self) -> list[int]:
        """Return a list of supported bit rates."""
        return [16]

    @property
    def supported_sample_rates(self) -> list[int]:
        """Return a list of supported sample rates."""
        return [16000]

    @property
    def supported_channels(self) -> list[int]:
        """Return a list of supported channels."""
        return [1]

    async def async_process_audio_stream(
        self,
        metadata: SpeechMetadata,
        stream: AsyncIterable[bytes],
    ) -> SpeechResult:
        """Process audio stream and return speech result."""
        try:
            # Collect audio data from stream
            audio_data = bytearray()
            async for chunk in stream:
                audio_data.extend(chunk)
                
                # Check size limit
                if len(audio_data) > MAX_AUDIO_SIZE:
                    _LOGGER.error("Audio stream too large: %d bytes", len(audio_data))
                    return SpeechResult(
                        text="Error: Audio file too large",
                        result=SpeechResult.ResultType.ERROR,
                    )
            
            if not audio_data:
                _LOGGER.warning("Empty audio stream received")
                return SpeechResult(
                    text="",
                    result=SpeechResult.ResultType.SUCCESS,
                )
            
            # Use WAV format
            mime_type = "audio/wav"
            
            _LOGGER.debug(
                "Processing audio: %d bytes, language: %s",
                len(audio_data),
                metadata.language,
            )
            
            # Process audio data
            if len(audio_data) > AUDIO_CHUNK_SIZE:
                # For large files, process in chunks
                text = await self._process_large_audio(
                    bytes(audio_data),
                    mime_type,
                    metadata.language,
                )
            else:
                # Process as single chunk
                text = await self._api_client.transcribe_audio(
                    model=self._model,
                    audio_data=bytes(audio_data),
                    mime_type=mime_type,
                    language=metadata.language,
                )
            
            if text:
                _LOGGER.debug("Transcription result: %s", text[:100])
                return SpeechResult(
                    text=text.strip(),
                    result=SpeechResult.ResultType.SUCCESS,
                )
            else:
                _LOGGER.warning("Empty transcription result")
                return SpeechResult(
                    text="",
                    result=SpeechResult.ResultType.SUCCESS,
                )
                
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error during transcription: %s", err)
            return SpeechResult(
                text=f"Error: {str(err)}",
                result=SpeechResult.ResultType.ERROR,
            )
            
        except Exception as err:
            _LOGGER.error("Unexpected error during transcription: %s", err)
            return SpeechResult(
                text=f"Unexpected error: {str(err)}",
                result=SpeechResult.ResultType.ERROR,
            )

    async def _process_large_audio(
        self,
        audio_data: bytes,
        mime_type: str,
        language: str,
    ) -> str:
        """Process large audio files by chunking."""
        chunks = []
        chunk_size = AUDIO_CHUNK_SIZE
        
        # Split audio into chunks
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            chunks.append(chunk)
        
        _LOGGER.debug("Processing large audio in %d chunks", len(chunks))
        
        # Process chunks concurrently with a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests
        
        async def process_chunk(chunk_data: bytes) -> str:
            async with semaphore:
                try:
                    return await self._api_client.transcribe_audio(
                        model=self._model,
                        audio_data=chunk_data,
                        mime_type=mime_type,
                        language=language,
                    )
                except Exception as err:
                    _LOGGER.warning("Error processing audio chunk: %s", err)
                    return ""
        
        # Process all chunks
        tasks = [process_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        transcription_parts = []
        for result in results:
            if isinstance(result, Exception):
                _LOGGER.warning("Chunk processing failed: %s", result)
                continue
            if result and result.strip():
                transcription_parts.append(result.strip())
        
        return " ".join(transcription_parts)

    async def async_transcribe_file(
        self,
        file_path: str,
        language: str | None = None,
    ) -> str:
        """Transcribe audio file directly."""
        try:
            # Check if file exists and is readable
            if not os.path.isfile(file_path):
                raise ValueError(f"File not found: {file_path}")
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > MAX_AUDIO_SIZE:
                raise ValueError(f"File too large: {file_size} bytes")
            
            # Read audio file
            with open(file_path, "rb") as file:
                audio_data = file.read()
            
            # Use WAV format
            mime_type = "audio/wav"
            
            # Use configured language if not specified
            if language is None:
                language = self._language
            
            _LOGGER.debug(
                "Transcribing file: %s (%d bytes), mime_type: %s, language: %s",
                file_path,
                len(audio_data),
                mime_type,
                language,
            )
            
            # Process audio
            if len(audio_data) > AUDIO_CHUNK_SIZE:
                text = await self._process_large_audio(audio_data, mime_type, language)
            else:
                text = await self._api_client.transcribe_audio(
                    model=self._model,
                    audio_data=audio_data,
                    mime_type=mime_type,
                    language=language,
                )
            
            return text.strip() if text else ""
            
        except Exception as err:
            _LOGGER.error("Error transcribing file %s: %s", file_path, err)
            raise 