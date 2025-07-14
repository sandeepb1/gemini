"""Constants for the Gemini AI integration."""
from __future__ import annotations

from typing import Final

# Integration domain
DOMAIN: Final = "gemini_ai"

# Configuration keys
CONF_API_KEY: Final = "api_key"
CONF_TTS_MODEL: Final = "tts_model"
CONF_STT_MODEL: Final = "stt_model"
CONF_CONVERSATION_MODEL: Final = "conversation_model"
CONF_DEFAULT_VOICE: Final = "default_voice"
CONF_VOICE_SPEED: Final = "voice_speed"
CONF_VOICE_PITCH: Final = "voice_pitch"
CONF_SYSTEM_PROMPT: Final = "system_prompt"
CONF_LANGUAGE: Final = "language"

# API Configuration
API_BASE_URL: Final = "https://generativelanguage.googleapis.com/v1beta/"
LIVE_API_URL: Final = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

# Default models
DEFAULT_TTS_MODEL: Final = "gemini-2.0-flash-exp"
DEFAULT_STT_MODEL: Final = "gemini-2.0-flash"
DEFAULT_CONVERSATION_MODEL: Final = "gemini-2.0-flash"

# Available models
AVAILABLE_MODELS: Final = {
    "tts": ["gemini-2.0-flash-exp"],
    "stt": ["gemini-2.0-flash", "gemini-1.5-flash"],
    "conversation": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
}

# Voice options
AVAILABLE_VOICES: Final = [
    "Aoede",
    "Charon", 
    "Fenrir",
    "Kore",
    "Puck"
]

# Default configuration values
DEFAULT_VOICE: Final = "Aoede"
DEFAULT_VOICE_SPEED: Final = 1.0
DEFAULT_VOICE_PITCH: Final = 0.0
DEFAULT_LANGUAGE: Final = "en"
DEFAULT_SYSTEM_PROMPT: Final = "You are a helpful Home Assistant voice assistant."

# Audio settings
SUPPORTED_AUDIO_FORMATS: Final = ["mp3", "wav", "ogg", "flac", "m4a"]
MAX_AUDIO_SIZE: Final = 10 * 1024 * 1024  # 10MB
AUDIO_CHUNK_SIZE: Final = 1024 * 1024  # 1MB chunks

# Service names
SERVICE_SAY: Final = "say"
SERVICE_TRANSCRIBE: Final = "transcribe"
SERVICE_PROCESS: Final = "process"
SERVICE_PREVIEW_VOICE: Final = "preview_voice"

# Event names
EVENT_TTS_COMPLETE: Final = f"{DOMAIN}_tts_complete"
EVENT_STT_COMPLETE: Final = f"{DOMAIN}_stt_complete"
EVENT_CONVERSATION_RESPONSE: Final = f"{DOMAIN}_conversation_response"
EVENT_ERROR: Final = f"{DOMAIN}_error"

# Cache settings
CACHE_TTL: Final = 3600  # 1 hour
MAX_CACHE_SIZE: Final = 100  # Maximum cached items

# Rate limiting
MAX_CONCURRENT_REQUESTS: Final = 5
REQUEST_TIMEOUT: Final = 30  # seconds
RETRY_ATTEMPTS: Final = 3
RETRY_DELAY: Final = 1  # seconds

# Platforms
PLATFORMS: Final = ["tts", "stt", "conversation"]

# Error messages
ERROR_INVALID_API_KEY: Final = "Invalid API key"
ERROR_QUOTA_EXCEEDED: Final = "API quota exceeded"
ERROR_NETWORK_ERROR: Final = "Network error"
ERROR_AUDIO_FORMAT: Final = "Unsupported audio format"
ERROR_AUDIO_SIZE: Final = "Audio file too large"
ERROR_MODEL_NOT_AVAILABLE: Final = "Model not available" 