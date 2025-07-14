"""API client for Google Gemini AI services."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import time
import base64
from urllib.parse import urljoin

import aiohttp
import websockets
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import (
    API_BASE_URL,
    LIVE_API_URL,
    REQUEST_TIMEOUT,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    MAX_CONCURRENT_REQUESTS,
    ERROR_INVALID_API_KEY,
    ERROR_QUOTA_EXCEEDED,
    ERROR_NETWORK_ERROR,
    ERROR_MODEL_NOT_AVAILABLE,
    DEFAULT_TTS_MODEL,
)

_LOGGER = logging.getLogger(__name__)


class GeminiAPIError(HomeAssistantError):
    """Exception for Gemini API errors."""


class GeminiAPIClient:
    """Client for Google Gemini AI API."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._session = session
        self._hass = hass
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._websocket: Optional[websockets.WebSocketServerProtocol] = None
        
        # Storage for caching
        self._store = Store(hass, 1, f"gemini_ai_cache")
        self._cache: Dict[str, Any] = {}
        
    async def test_connection(self) -> bool:
        """Test the API connection."""
        try:
            url = urljoin(API_BASE_URL, "models")
            headers = {"x-goog-api-key": self._api_key}
            
            async with self._session.get(url, headers=headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 401:
                    raise GeminiAPIError(ERROR_INVALID_API_KEY)
                elif response.status == 429:
                    raise GeminiAPIError(ERROR_QUOTA_EXCEEDED)
                elif response.status >= 400:
                    raise GeminiAPIError(f"API error: {response.status}")
                    
                data = await response.json()
                return "models" in data
                
        except asyncio.TimeoutError:
            raise GeminiAPIError(ERROR_NETWORK_ERROR)
        except aiohttp.ClientError as err:
            raise GeminiAPIError(f"Network error: {err}")

    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models from the API."""
        cache_key = "available_models"
        
        # Check cache
        if cache_key in self._cache:
            cache_time, models = self._cache[cache_key]
            if time.time() - cache_time < 3600:  # 1 hour cache
                return models
        
        try:
            url = urljoin(API_BASE_URL, "models")
            headers = {"x-goog-api-key": self._api_key}
            
            async with self._session.get(url, headers=headers, timeout=REQUEST_TIMEOUT) as response:
                if response.status != 200:
                    raise GeminiAPIError(f"Failed to get models: {response.status}")
                
                data = await response.json()
                models = {
                    "tts": [],
                    "stt": [],
                    "conversation": []
                }
                
                for model in data.get("models", []):
                    model_name = model.get("name", "").split("/")[-1]
                    supported_methods = model.get("supportedGenerationMethods", [])
                    
                    if "generateContent" in supported_methods:
                        models["conversation"].append(model_name)
                        models["stt"].append(model_name)
                    
                    # TTS models typically support different methods
                    if "generateContentStream" in supported_methods:
                        models["tts"].append(model_name)
                
                # Cache the result
                self._cache[cache_key] = (time.time(), models)
                return models
                
        except Exception as err:
            _LOGGER.error("Failed to get available models: %s", err)
            # Return default models if API fails
            return {
                "tts": ["gemini-2.0-flash-exp"],
                "stt": ["gemini-2.0-flash", "gemini-1.5-flash"],
                "conversation": ["gemini-2.0-flash", "gemini-1.5-flash"]
            }

    async def generate_content(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Generate content using Gemini API."""
        async with self._semaphore:
            return await self._make_request_with_retry(
                self._generate_content_request,
                model,
                prompt,
                system_prompt,
                conversation_history,
            )

    async def _generate_content_request(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Make the actual content generation request."""
        url = urljoin(API_BASE_URL, f"models/{model}:generateContent")
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        
        # Build the request payload
        contents = []
        
        # Add system prompt if provided
        if system_prompt:
            contents.append({
                "role": "model",
                "parts": [{"text": system_prompt}]
            })
        
        # Add conversation history if provided
        if conversation_history:
            for message in conversation_history:
                contents.append({
                    "role": message.get("role", "user"),
                    "parts": [{"text": message["content"]}]
                })
        
        # Add current prompt
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        async with self._session.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 401:
                raise GeminiAPIError(ERROR_INVALID_API_KEY)
            elif response.status == 429:
                raise GeminiAPIError(ERROR_QUOTA_EXCEEDED)
            elif response.status == 404:
                raise GeminiAPIError(ERROR_MODEL_NOT_AVAILABLE)
            elif response.status >= 400:
                error_data = await response.text()
                raise GeminiAPIError(f"API error {response.status}: {error_data}")
            
            data = await response.json()
            
            # Extract the generated content
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiAPIError("No response generated")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise GeminiAPIError("No content in response")
            
            return parts[0].get("text", "")

    async def transcribe_audio(
        self,
        model: str,
        audio_data: bytes,
        mime_type: str,
        language: Optional[str] = None,
    ) -> str:
        """Transcribe audio using Gemini API."""
        async with self._semaphore:
            return await self._make_request_with_retry(
                self._transcribe_audio_request,
                model,
                audio_data,
                mime_type,
                language,
            )

    async def _transcribe_audio_request(
        self,
        model: str,
        audio_data: bytes,
        mime_type: str,
        language: Optional[str] = None,
    ) -> str:
        """Make the actual audio transcription request."""
        url = urljoin(API_BASE_URL, f"models/{model}:generateContent")
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        
        # Encode audio data
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Please transcribe this audio{f' in {language}' if language else ''}:"
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": audio_base64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            }
        }
        
        async with self._session.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT * 2) as response:
            if response.status == 401:
                raise GeminiAPIError(ERROR_INVALID_API_KEY)
            elif response.status == 429:
                raise GeminiAPIError(ERROR_QUOTA_EXCEEDED)
            elif response.status == 404:
                raise GeminiAPIError(ERROR_MODEL_NOT_AVAILABLE)
            elif response.status >= 400:
                error_data = await response.text()
                raise GeminiAPIError(f"API error {response.status}: {error_data}")
            
            data = await response.json()
            
            # Extract the transcription
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiAPIError("No transcription generated")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise GeminiAPIError("No content in transcription response")
            
            return parts[0].get("text", "")

    async def _make_request_with_retry(self, request_func, *args, **kwargs) -> Any:
        """Make a request with retry logic."""
        last_error = None
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                return await request_func(*args, **kwargs)
            except GeminiAPIError as err:
                last_error = err
                if "quota" in str(err).lower() or "rate" in str(err).lower():
                    # Exponential backoff for rate limiting
                    delay = RETRY_DELAY * (2 ** attempt)
                    _LOGGER.warning("Rate limited, retrying in %s seconds", delay)
                    await asyncio.sleep(delay)
                else:
                    # Don't retry for auth errors or permanent failures
                    raise
            except Exception as err:
                last_error = GeminiAPIError(f"Request failed: {err}")
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY)
        
        raise last_error

    async def synthesize_speech(
        self,
        model: str,
        text: str,
        voice: str = "Aoede",
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize speech using Gemini Live API."""
        async with self._semaphore:
            return await self._make_request_with_retry(
                self._synthesize_speech_request,
                model,
                text,
                voice,
                speed,
            )

    async def _synthesize_speech_request(
        self,
        model: str,
        text: str,
        voice: str,
        speed: float,
    ) -> bytes:
        """Make the actual TTS request using WebSocket."""
        # For now, we'll use a simple generateContent approach
        # In a full implementation, this would use the Live API WebSocket
        url = urljoin(API_BASE_URL, f"models/{model}:generateContent")
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Generate speech audio for the following text with voice '{voice}' at speed {speed}: {text}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
            }
        }
        
        async with self._session.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT * 2) as response:
            if response.status == 401:
                raise GeminiAPIError(ERROR_INVALID_API_KEY)
            elif response.status == 429:
                raise GeminiAPIError(ERROR_QUOTA_EXCEEDED)
            elif response.status == 404:
                raise GeminiAPIError(ERROR_MODEL_NOT_AVAILABLE)
            elif response.status >= 400:
                error_data = await response.text()
                raise GeminiAPIError(f"API error {response.status}: {error_data}")
            
            # For now, return empty bytes as placeholder
            # In a real implementation, this would return the audio data
            return b""

    async def get_available_voices(self) -> List[str]:
        """Get available voices for TTS."""
        from .const import AVAILABLE_VOICES
        return AVAILABLE_VOICES

    async def preview_voice(self, voice: str, sample_text: str = "Hello, this is a voice preview.") -> bytes:
        """Generate a voice preview sample."""
        return await self.synthesize_speech(
            DEFAULT_TTS_MODEL,
            sample_text,
            voice,
            1.0
        )

    async def close(self) -> None:
        """Close the API client and clean up resources."""
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
        
        # Save cache to storage
        if self._cache:
            await self._store.async_save(self._cache) 