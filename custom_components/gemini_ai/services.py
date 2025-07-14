"""Services for Gemini AI integration."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api_client import GeminiAPIClient, GeminiAPIError
from .const import (
    DOMAIN,
    SERVICE_SAY,
    SERVICE_TRANSCRIBE,
    SERVICE_PROCESS,
    SERVICE_PREVIEW_VOICE,
    AVAILABLE_VOICES,
    SUPPORTED_AUDIO_FORMATS,
    MAX_AUDIO_SIZE,
    EVENT_TTS_COMPLETE,
    EVENT_STT_COMPLETE,
    EVENT_CONVERSATION_RESPONSE,
    EVENT_ERROR,
)

_LOGGER = logging.getLogger(__name__)

# Service schemas
SAY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("voice", default="Aoede"): vol.In(AVAILABLE_VOICES),
        vol.Optional("speed", default=1.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.25, max=4.0)
        ),
        vol.Optional("cache", default=True): cv.boolean,
        vol.Optional("language", default="en"): cv.string,
    }
)

TRANSCRIBE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("audio_file"): cv.string,
        vol.Optional("language"): cv.string,
        vol.Optional("model"): cv.string,
    }
)

PROCESS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("text"): cv.string,
        vol.Optional("conversation_id", default="default"): cv.string,
        vol.Optional("system_prompt"): cv.string,
        vol.Optional("language", default="en"): cv.string,
        vol.Optional("model"): cv.string,
    }
)

PREVIEW_VOICE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("voice"): vol.In(AVAILABLE_VOICES),
        vol.Optional("text", default="Hello, this is a voice preview."): cv.string,
        vol.Optional("speed", default=1.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.25, max=4.0)
        ),
    }
)


async def async_register_services(hass: HomeAssistant, api_client: GeminiAPIClient) -> None:
    """Register services for Gemini AI integration."""
    
    async def say_service(call: ServiceCall) -> None:
        """Handle the say service call."""
        try:
            message = call.data["message"]
            voice = call.data.get("voice", "Aoede")
            speed = call.data.get("speed", 1.0)
            language = call.data.get("language", "en")
            use_cache = call.data.get("cache", True)
            
            _LOGGER.debug("Say service called: message='%s', voice='%s'", message[:50], voice)
            
            # Generate speech
            audio_data = await api_client.synthesize_speech(
                model="gemini-2.0-flash-exp",  # Use TTS model
                text=message,
                voice=voice,
                speed=speed,
            )
            
            # Fire completion event
            hass.bus.async_fire(
                EVENT_TTS_COMPLETE,
                {
                    "message": message,
                    "voice": voice,
                    "speed": speed,
                    "language": language,
                    "audio_size": len(audio_data),
                    "success": True,
                },
            )
            
            _LOGGER.debug("Say service completed successfully")
            
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error in say service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_SAY,
                    "error": str(err),
                    "message": call.data.get("message", ""),
                },
            )
            
        except Exception as err:
            _LOGGER.error("Unexpected error in say service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_SAY,
                    "error": f"Unexpected error: {str(err)}",
                    "message": call.data.get("message", ""),
                },
            )

    async def transcribe_service(call: ServiceCall) -> None:
        """Handle the transcribe service call."""
        try:
            audio_file = call.data["audio_file"]
            language = call.data.get("language")
            model = call.data.get("model", "gemini-2.0-flash")
            
            _LOGGER.debug("Transcribe service called: file='%s'", audio_file)
            
            # Validate file exists and size
            if not os.path.isfile(audio_file):
                raise ValueError(f"Audio file not found: {audio_file}")
            
            file_size = os.path.getsize(audio_file)
            if file_size > MAX_AUDIO_SIZE:
                raise ValueError(f"Audio file too large: {file_size} bytes (max: {MAX_AUDIO_SIZE})")
            
            # Read audio file
            with open(audio_file, "rb") as f:
                audio_data = f.read()
            
            # Determine MIME type from file extension
            file_ext = os.path.splitext(audio_file)[1].lower()
            mime_type_mapping = {
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".ogg": "audio/ogg",
                ".flac": "audio/flac",
                ".m4a": "audio/mp4",
            }
            mime_type = mime_type_mapping.get(file_ext, "audio/wav")
            
            # Transcribe audio
            transcription = await api_client.transcribe_audio(
                model=model,
                audio_data=audio_data,
                mime_type=mime_type,
                language=language,
            )
            
            # Fire completion event
            hass.bus.async_fire(
                EVENT_STT_COMPLETE,
                {
                    "audio_file": audio_file,
                    "transcription": transcription,
                    "language": language,
                    "model": model,
                    "file_size": file_size,
                    "success": True,
                },
            )
            
            _LOGGER.debug("Transcribe service completed: '%s'", transcription[:100])
            
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error in transcribe service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_TRANSCRIBE,
                    "error": str(err),
                    "audio_file": call.data.get("audio_file", ""),
                },
            )
            
        except Exception as err:
            _LOGGER.error("Unexpected error in transcribe service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_TRANSCRIBE,
                    "error": f"Unexpected error: {str(err)}",
                    "audio_file": call.data.get("audio_file", ""),
                },
            )

    async def process_service(call: ServiceCall) -> None:
        """Handle the process service call."""
        try:
            text = call.data["text"]
            conversation_id = call.data.get("conversation_id", "default")
            system_prompt = call.data.get("system_prompt")
            language = call.data.get("language", "en")
            model = call.data.get("model", "gemini-2.0-flash")
            
            _LOGGER.debug("Process service called: text='%s', conversation_id='%s'", text[:50], conversation_id)
            
            # Generate response
            response = await api_client.generate_content(
                model=model,
                prompt=text,
                system_prompt=system_prompt,
                conversation_history=None,  # Service doesn't maintain history
            )
            
            # Fire completion event
            hass.bus.async_fire(
                EVENT_CONVERSATION_RESPONSE,
                {
                    "conversation_id": conversation_id,
                    "user_input": text,
                    "response": response,
                    "model": model,
                    "language": language,
                    "success": True,
                },
            )
            
            _LOGGER.debug("Process service completed: '%s'", response[:100])
            
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error in process service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_PROCESS,
                    "error": str(err),
                    "text": call.data.get("text", ""),
                    "conversation_id": call.data.get("conversation_id", ""),
                },
            )
            
        except Exception as err:
            _LOGGER.error("Unexpected error in process service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_PROCESS,
                    "error": f"Unexpected error: {str(err)}",
                    "text": call.data.get("text", ""),
                    "conversation_id": call.data.get("conversation_id", ""),
                },
            )

    async def preview_voice_service(call: ServiceCall) -> None:
        """Handle the preview voice service call."""
        try:
            voice = call.data["voice"]
            text = call.data.get("text", "Hello, this is a voice preview.")
            speed = call.data.get("speed", 1.0)
            
            _LOGGER.debug("Preview voice service called: voice='%s'", voice)
            
            # Generate voice preview
            audio_data = await api_client.preview_voice(voice, text)
            
            # Fire completion event
            hass.bus.async_fire(
                EVENT_TTS_COMPLETE,
                {
                    "message": text,
                    "voice": voice,
                    "speed": speed,
                    "language": "en",
                    "audio_size": len(audio_data),
                    "is_preview": True,
                    "success": True,
                },
            )
            
            _LOGGER.debug("Preview voice service completed")
            
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error in preview voice service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_PREVIEW_VOICE,
                    "error": str(err),
                    "voice": call.data.get("voice", ""),
                },
            )
            
        except Exception as err:
            _LOGGER.error("Unexpected error in preview voice service: %s", err)
            hass.bus.async_fire(
                EVENT_ERROR,
                {
                    "service": SERVICE_PREVIEW_VOICE,
                    "error": f"Unexpected error: {str(err)}",
                    "voice": call.data.get("voice", ""),
                },
            )

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAY,
        say_service,
        schema=SAY_SERVICE_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRANSCRIBE,
        transcribe_service,
        schema=TRANSCRIBE_SERVICE_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_PROCESS,
        process_service,
        schema=PROCESS_SERVICE_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_PREVIEW_VOICE,
        preview_voice_service,
        schema=PREVIEW_VOICE_SERVICE_SCHEMA,
    )
    
    _LOGGER.info("Gemini AI services registered successfully")


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services for Gemini AI integration."""
    services = [SERVICE_SAY, SERVICE_TRANSCRIBE, SERVICE_PROCESS, SERVICE_PREVIEW_VOICE]
    
    for service in services:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    
    _LOGGER.info("Gemini AI services unregistered") 