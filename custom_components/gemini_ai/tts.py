"""Text-to-speech platform for Gemini AI integration."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, Optional

from homeassistant.components.tts import CONF_LANG, TextToSpeechEntity, Voice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .api_client import GeminiAPIClient, GeminiAPIError
from .const import (
    CONF_TTS_MODEL,
    CONF_DEFAULT_VOICE,
    CONF_VOICE_SPEED,
    CONF_VOICE_PITCH,
    CONF_LANGUAGE,
    DEFAULT_TTS_MODEL,
    DEFAULT_VOICE,
    DEFAULT_VOICE_SPEED,
    DEFAULT_VOICE_PITCH,
    DEFAULT_LANGUAGE,
    AVAILABLE_VOICES,
    DOMAIN,
    CACHE_TTL,
    MAX_CACHE_SIZE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gemini TTS platform via config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api_client = data["api_client"]
    config = data["config"]
    
    tts_entity = GeminiTTSEntity(
        api_client=api_client,
        config=config,
        entry_id=config_entry.entry_id,
        hass=hass,
    )
    
    async_add_entities([tts_entity])


class GeminiTTSEntity(TextToSpeechEntity):
    """Gemini AI Text-to-Speech entity."""

    def __init__(
        self,
        api_client: GeminiAPIClient,
        config: Dict[str, Any],
        entry_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the TTS entity."""
        self._api_client = api_client
        self._config = config
        self._entry_id = entry_id
        self._hass = hass
        
        # TTS settings
        self._model = config.get(CONF_TTS_MODEL, DEFAULT_TTS_MODEL)
        self._default_voice = config.get(CONF_DEFAULT_VOICE, DEFAULT_VOICE)
        self._default_speed = config.get(CONF_VOICE_SPEED, DEFAULT_VOICE_SPEED)
        self._default_pitch = config.get(CONF_VOICE_PITCH, DEFAULT_VOICE_PITCH)
        self._language = config.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        
        # Cache setup
        self._store = Store(hass, 1, f"gemini_ai_tts_cache_{entry_id}")
        self._cache: Dict[str, Any] = {}
        self._cache_loaded = False
        
        # Load cache on startup
        hass.async_create_task(self._load_cache())

    async def _load_cache(self) -> None:
        """Load TTS cache from storage."""
        try:
            stored_cache = await self._store.async_load()
            if stored_cache:
                self._cache = stored_cache
            self._cache_loaded = True
        except Exception as err:
            _LOGGER.warning("Failed to load TTS cache: %s", err)
            self._cache_loaded = True

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Gemini AI TTS"

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{DOMAIN}_{self._entry_id}_tts"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        # Gemini supports many languages, return common ones
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
    def supported_options(self) -> list[str]:
        """Return list of supported options."""
        return ["voice", "speed", "pitch"]

    def get_supported_voices(self, language: str) -> list[Voice]:
        """Return list of supported voices for given language (sync version)."""
        # Return default voices immediately for WebSocket API compatibility
        return [
            Voice(voice_id=voice, name=voice)
            for voice in AVAILABLE_VOICES
        ]

    async def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return list of supported voices for given language."""
        # For now, return static voices to avoid API calls during setup
        # This prevents coroutine serialization issues with WebSocket API
        return [
            Voice(voice_id=voice, name=voice)
            for voice in AVAILABLE_VOICES
        ]

    @property
    def supported_voices(self) -> list[Voice]:
        """Return list of supported voices (sync property for WebSocket API)."""
        return [
            Voice(voice_id=voice, name=voice)
            for voice in AVAILABLE_VOICES
        ]

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: Dict[str, Any] | None = None,
    ) -> tuple[str, bytes]:
        """Load TTS from Gemini AI."""
        if not self._cache_loaded:
            await self._load_cache()
            
        # Parse options
        if options is None:
            options = {}
            
        voice = options.get("voice", self._default_voice)
        speed = float(options.get("speed", self._default_speed))
        pitch = float(options.get("pitch", self._default_pitch))
        
        # Create cache key
        cache_key = self._create_cache_key(message, language, voice, speed, pitch)
        
        # Check cache first
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            if self._is_cache_valid(cache_entry):
                _LOGGER.debug("Using cached TTS for message: %s", message[:50])
                # Decode base64 data back to bytes
                import base64
                cached_data = base64.b64decode(cache_entry["data"])
                return cache_entry["content_type"], cached_data
        
        try:
            # Generate speech using API
            _LOGGER.debug("Generating TTS for message: %s", message[:50])
            audio_data = await self._api_client.synthesize_speech(
                model=self._model,
                text=message,
                voice=voice,
                speed=speed,
            )
            
            if not audio_data:
                # If API returns empty data, generate a placeholder
                _LOGGER.warning("Gemini API returned empty audio data, using placeholder")
                audio_data = self._generate_placeholder_audio(message)
            
            content_type = "wav"  # Return codec name for FFmpeg compatibility
            
            # Cache the result
            await self._cache_audio(cache_key, content_type, audio_data)
            
            return content_type, audio_data
            
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error during TTS: %s", err)
            # Generate placeholder audio for errors
            audio_data = self._generate_placeholder_audio(f"Error: {str(err)}")
            return "wav", audio_data
            
        except Exception as err:
            _LOGGER.error("Unexpected error during TTS: %s", err)
            # Generate placeholder audio for errors
            audio_data = self._generate_placeholder_audio("Error occurred during speech synthesis")
            return "wav", audio_data

    def _create_cache_key(
        self,
        message: str,
        language: str,
        voice: str,
        speed: float,
        pitch: float,
    ) -> str:
        """Create a cache key for the given parameters."""
        key_data = f"{message}|{language}|{voice}|{speed}|{pitch}|{self._model}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        import time
        return time.time() - cache_entry.get("timestamp", 0) < CACHE_TTL

    async def _cache_audio(self, cache_key: str, content_type: str, audio_data: bytes) -> None:
        """Cache audio data."""
        import time
        import base64
        
        # Remove old entries if cache is full
        if len(self._cache) >= MAX_CACHE_SIZE:
            await self._cleanup_cache()
        
        # Add to cache (encode bytes as base64 for JSON serialization)
        self._cache[cache_key] = {
            "content_type": content_type,
            "data": base64.b64encode(audio_data).decode('utf-8'),
            "timestamp": time.time(),
        }
        
        # Save to storage (async)
        self._hass.async_create_task(self._save_cache())

    async def _cleanup_cache(self) -> None:
        """Remove old cache entries."""
        import time
        current_time = time.time()
        
        # Remove expired entries
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time - entry.get("timestamp", 0) > CACHE_TTL
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        # If still too many entries, remove oldest
        if len(self._cache) >= MAX_CACHE_SIZE:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].get("timestamp", 0)
            )
            
            # Keep only the newest entries
            keep_count = MAX_CACHE_SIZE // 2
            self._cache = dict(sorted_entries[-keep_count:])

    async def _save_cache(self) -> None:
        """Save cache to storage."""
        try:
            await self._store.async_save(self._cache)
        except Exception as err:
            _LOGGER.warning("Failed to save TTS cache: %s", err)

    def _generate_placeholder_audio(self, message: str) -> bytes:
        """Generate placeholder audio data."""
        # Generate a simple WAV file with silence to avoid FFmpeg errors
        _LOGGER.debug("Generating placeholder audio for: %s", message[:50])
        
        # Use the same WAV generation as the API client
        duration_ms = len(message) * 50  # Scale duration by message length
        return self._generate_wav_silence(duration_ms)
    
    def _generate_wav_silence(self, duration_ms: int) -> bytes:
        """Generate a WAV file with silence."""
        import struct
        
        # WAV file parameters
        sample_rate = 22050
        channels = 1
        bits_per_sample = 16
        duration_seconds = min(duration_ms / 1000.0, 3.0)  # Max 3 seconds
        num_samples = int(sample_rate * duration_seconds)
        
        # WAV header
        wav_header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + num_samples * channels * bits_per_sample // 8,
            b'WAVE',
            b'fmt ',
            16,  # PCM
            1,   # PCM
            channels,
            sample_rate,
            sample_rate * channels * bits_per_sample // 8,
            channels * bits_per_sample // 8,
            bits_per_sample,
            b'data',
            num_samples * channels * bits_per_sample // 8
        )
        
        # Generate silence (zeros)
        audio_data = b'\x00' * (num_samples * channels * bits_per_sample // 8)
        
        return wav_header + audio_data

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        await self._save_cache() 