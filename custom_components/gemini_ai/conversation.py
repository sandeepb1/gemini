"""Conversation platform for Gemini AI integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.conversation import ConversationEntity, ConversationInput, ConversationResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .api_client import GeminiAPIClient, GeminiAPIError
from .const import (
    CONF_CONVERSATION_MODEL,
    CONF_SYSTEM_PROMPT,
    CONF_LANGUAGE,
    DEFAULT_CONVERSATION_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_LANGUAGE,
    DOMAIN,
    EVENT_CONVERSATION_RESPONSE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gemini Conversation platform via config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api_client = data["api_client"]
    config = data["config"]
    
    conversation_entity = GeminiConversationEntity(
        api_client=api_client,
        config=config,
        entry_id=config_entry.entry_id,
        hass=hass,
    )
    
    async_add_entities([conversation_entity])


class GeminiConversationEntity(ConversationEntity):
    """Gemini AI Conversation entity."""

    def __init__(
        self,
        api_client: GeminiAPIClient,
        config: Dict[str, Any],
        entry_id: str,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the Conversation entity."""
        self._api_client = api_client
        self._config = config
        self._entry_id = entry_id
        self._hass = hass
        
        # Conversation settings
        self._model = config.get(CONF_CONVERSATION_MODEL, DEFAULT_CONVERSATION_MODEL)
        self._system_prompt = config.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)
        self._language = config.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        
        # Conversation history storage
        self._store = Store(hass, 1, f"gemini_ai_conversations_{entry_id}")
        self._conversations: Dict[str, List[Dict[str, str]]] = {}
        self._conversations_loaded = False
        
        # Load conversations on startup
        hass.async_create_task(self._load_conversations())

    async def _load_conversations(self) -> None:
        """Load conversation history from storage."""
        try:
            stored_conversations = await self._store.async_load()
            if stored_conversations:
                self._conversations = stored_conversations
            self._conversations_loaded = True
        except Exception as err:
            _LOGGER.warning("Failed to load conversation history: %s", err)
            self._conversations_loaded = True

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Gemini AI Conversation"

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{DOMAIN}_{self._entry_id}_conversation"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        # Gemini supports many languages for conversation
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

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a conversation turn."""
        if not self._conversations_loaded:
            await self._load_conversations()
        
        try:
            # Get or create conversation history
            conversation_id = user_input.conversation_id or "default"
            conversation_history = self._conversations.get(conversation_id, [])
            
            # Prepare the input text
            user_text = user_input.text.strip()
            
            _LOGGER.debug(
                "Processing conversation input: '%s' (conversation_id: %s)",
                user_text[:100],
                conversation_id,
            )
            
            # Check for special commands
            if user_text.lower() in ["clear", "reset", "new conversation"]:
                # Clear conversation history
                if conversation_id in self._conversations:
                    del self._conversations[conversation_id]
                    await self._save_conversations()
                
                return ConversationResult(
                    response=ConversationResult.ResponseType.ACTION_DONE,
                    data={"text": "Conversation history cleared."},
                )
            
            # Check for intent processing
            intent_response = await self._process_intent(user_text, conversation_history)
            if intent_response:
                return intent_response
            
            # Generate response using Gemini API
            response_text = await self._api_client.generate_content(
                model=self._model,
                prompt=user_text,
                system_prompt=self._system_prompt,
                conversation_history=conversation_history,
            )
            
            if not response_text:
                response_text = "I'm sorry, I couldn't generate a response."
            
            # Update conversation history
            conversation_history.append({
                "role": "user",
                "content": user_text,
            })
            conversation_history.append({
                "role": "assistant", 
                "content": response_text,
            })
            
            # Limit conversation history size
            max_history = 20  # Keep last 20 exchanges
            if len(conversation_history) > max_history:
                conversation_history = conversation_history[-max_history:]
            
            # Store updated conversation
            self._conversations[conversation_id] = conversation_history
            await self._save_conversations()
            
            # Fire event
            self._hass.bus.async_fire(
                EVENT_CONVERSATION_RESPONSE,
                {
                    "conversation_id": conversation_id,
                    "user_input": user_text,
                    "response": response_text,
                    "model": self._model,
                },
            )
            
            _LOGGER.debug("Generated response: %s", response_text[:100])
            
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": response_text},
            )
            
        except GeminiAPIError as err:
            _LOGGER.error("Gemini API error during conversation: %s", err)
            return ConversationResult(
                response=ConversationResult.ResponseType.ERROR,
                data={"text": f"Sorry, I encountered an error: {str(err)}"},
            )
            
        except Exception as err:
            _LOGGER.error("Unexpected error during conversation: %s", err)
            return ConversationResult(
                response=ConversationResult.ResponseType.ERROR,
                data={"text": "Sorry, I encountered an unexpected error."},
            )

    async def _process_intent(
        self,
        user_text: str,
        conversation_history: List[Dict[str, str]],
    ) -> Optional[ConversationResult]:
        """Process potential Home Assistant intents."""
        # Basic intent detection based on keywords
        lower_text = user_text.lower()
        
        # Home Assistant control intents
        if any(word in lower_text for word in ["turn on", "turn off", "switch on", "switch off"]):
            return await self._process_control_intent(user_text, conversation_history)
        
        # Weather intents
        if any(word in lower_text for word in ["weather", "temperature", "forecast"]):
            return await self._process_weather_intent(user_text, conversation_history)
        
        # Time/date intents
        if any(word in lower_text for word in ["time", "date", "what time", "what day"]):
            return await self._process_time_intent(user_text, conversation_history)
        
        # No specific intent detected
        return None

    async def _process_control_intent(
        self,
        user_text: str,
        conversation_history: List[Dict[str, str]],
    ) -> ConversationResult:
        """Process device control intents."""
        # Use Gemini to understand the intent and generate a structured response
        control_prompt = f"""
        You are a Home Assistant voice assistant. The user said: "{user_text}"
        
        This appears to be a device control request. Please respond with:
        1. A confirmation of what action you would take
        2. Note that you're a demo integration and cannot actually control devices yet
        
        Be helpful and conversational.
        """
        
        try:
            response = await self._api_client.generate_content(
                model=self._model,
                prompt=control_prompt,
                system_prompt=self._system_prompt,
                conversation_history=conversation_history,
            )
            
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": response or "I understand you want to control a device, but I'm still learning how to do that."},
            )
            
        except Exception as err:
            _LOGGER.error("Error processing control intent: %s", err)
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": "I understand you want to control something, but I'm having trouble processing that right now."},
            )

    async def _process_weather_intent(
        self,
        user_text: str,
        conversation_history: List[Dict[str, str]],
    ) -> ConversationResult:
        """Process weather-related intents."""
        weather_prompt = f"""
        You are a Home Assistant voice assistant. The user asked: "{user_text}"
        
        This appears to be a weather request. Please respond helpfully, noting that:
        1. You don't have access to current weather data in this demo
        2. In a full integration, you could access Home Assistant's weather entities
        3. Be conversational and suggest how they could get weather information
        
        Be helpful and friendly.
        """
        
        try:
            response = await self._api_client.generate_content(
                model=self._model,
                prompt=weather_prompt,
                system_prompt=self._system_prompt,
                conversation_history=conversation_history,
            )
            
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": response or "I'd love to help with weather information, but I don't have access to weather data right now."},
            )
            
        except Exception as err:
            _LOGGER.error("Error processing weather intent: %s", err)
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": "I'd like to help with weather information, but I'm having trouble accessing that right now."},
            )

    async def _process_time_intent(
        self,
        user_text: str,
        conversation_history: List[Dict[str, str]],
    ) -> ConversationResult:
        """Process time/date related intents."""
        import datetime
        
        current_time = datetime.datetime.now()
        time_info = current_time.strftime("%I:%M %p on %A, %B %d, %Y")
        
        time_prompt = f"""
        You are a Home Assistant voice assistant. The user asked: "{user_text}"
        
        This appears to be a time/date request. The current time is: {time_info}
        
        Please provide a natural, conversational response that includes the relevant time/date information.
        """
        
        try:
            response = await self._api_client.generate_content(
                model=self._model,
                prompt=time_prompt,
                system_prompt=self._system_prompt,
                conversation_history=conversation_history,
            )
            
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": response or f"The current time is {time_info}."},
            )
            
        except Exception as err:
            _LOGGER.error("Error processing time intent: %s", err)
            return ConversationResult(
                response=ConversationResult.ResponseType.ACTION_DONE,
                data={"text": f"The current time is {time_info}."},
            )

    async def _save_conversations(self) -> None:
        """Save conversation history to storage."""
        try:
            await self._store.async_save(self._conversations)
        except Exception as err:
            _LOGGER.warning("Failed to save conversation history: %s", err)

    async def async_get_conversation_history(
        self,
        conversation_id: str,
    ) -> List[Dict[str, str]]:
        """Get conversation history for a specific conversation ID."""
        if not self._conversations_loaded:
            await self._load_conversations()
        
        return self._conversations.get(conversation_id, [])

    async def async_clear_conversation_history(
        self,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Clear conversation history for a specific conversation ID or all conversations."""
        if not self._conversations_loaded:
            await self._load_conversations()
        
        if conversation_id:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
        else:
            self._conversations.clear()
        
        await self._save_conversations()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        await self._save_conversations() 