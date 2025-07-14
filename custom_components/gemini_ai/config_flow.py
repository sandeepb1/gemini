"""Config flow for Gemini AI integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import GeminiAPIClient, GeminiAPIError
from .const import (
    CONF_API_KEY,
    CONF_TTS_MODEL,
    CONF_STT_MODEL,
    CONF_CONVERSATION_MODEL,
    CONF_DEFAULT_VOICE,
    CONF_VOICE_SPEED,
    CONF_VOICE_PITCH,
    CONF_SYSTEM_PROMPT,
    CONF_LANGUAGE,
    DEFAULT_TTS_MODEL,
    DEFAULT_STT_MODEL,
    DEFAULT_CONVERSATION_MODEL,
    DEFAULT_VOICE,
    DEFAULT_VOICE_SPEED,
    DEFAULT_VOICE_PITCH,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_LANGUAGE,
    AVAILABLE_VOICES,
    DOMAIN,
    ERROR_INVALID_API_KEY,
    ERROR_QUOTA_EXCEEDED,
    ERROR_NETWORK_ERROR,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default="Gemini AI"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    api_client = GeminiAPIClient(
        api_key=data[CONF_API_KEY],
        session=session,
        hass=hass,
    )
    
    try:
        # Test connection
        await api_client.test_connection()
        
        # Get available models
        available_models = await api_client.get_available_models()
        
        # Get available voices
        available_voices = await api_client.get_available_voices()
        
        return {
            "title": data.get(CONF_NAME, "Gemini AI"),
            "available_models": available_models,
            "available_voices": available_voices,
        }
    except GeminiAPIError as err:
        if ERROR_INVALID_API_KEY in str(err):
            raise InvalidAuth from err
        elif ERROR_QUOTA_EXCEEDED in str(err):
            raise QuotaExceeded from err
        elif ERROR_NETWORK_ERROR in str(err):
            raise CannotConnect from err
        else:
            raise CannotConnect from err
    finally:
        await api_client.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gemini AI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: Dict[str, Any] = {}
        self._available_models: Dict[str, Any] = {}
        self._available_voices: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Store validated data
                self._data.update(user_input)
                self._available_models = info["available_models"]
                self._available_voices = info["available_voices"]
                
                # Move to model selection step
                return await self.async_step_models()
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except QuotaExceeded:
                errors["base"] = "quota_exceeded"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://aistudio.google.com/",
            },
        )

    async def async_step_models(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle model selection step."""
        errors: dict[str, str] = {}
        
        # Create schema with available models
        tts_models = self._available_models.get("tts", [DEFAULT_TTS_MODEL])
        stt_models = self._available_models.get("stt", [DEFAULT_STT_MODEL])
        conversation_models = self._available_models.get("conversation", [DEFAULT_CONVERSATION_MODEL])
        
        if not tts_models:
            tts_models = [DEFAULT_TTS_MODEL]
        if not stt_models:
            stt_models = [DEFAULT_STT_MODEL]
        if not conversation_models:
            conversation_models = [DEFAULT_CONVERSATION_MODEL]
        
        models_schema = vol.Schema(
            {
                vol.Required(CONF_TTS_MODEL, default=tts_models[0]): vol.In(tts_models),
                vol.Required(CONF_STT_MODEL, default=stt_models[0]): vol.In(stt_models),
                vol.Required(CONF_CONVERSATION_MODEL, default=conversation_models[0]): vol.In(conversation_models),
            }
        )
        
        if user_input is not None:
            # Store model selections
            self._data.update(user_input)
            
            # Move to voice configuration step
            return await self.async_step_voice()

        return self.async_show_form(
            step_id="models",
            data_schema=models_schema,
            errors=errors,
        )

    async def async_step_voice(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle voice configuration step."""
        errors: dict[str, str] = {}
        
        # Use available voices or fallback to defaults
        voices = self._available_voices if self._available_voices else AVAILABLE_VOICES
        
        voice_schema = vol.Schema(
            {
                vol.Required(CONF_DEFAULT_VOICE, default=DEFAULT_VOICE): vol.In(voices),
                vol.Optional(CONF_VOICE_SPEED, default=DEFAULT_VOICE_SPEED): vol.All(
                    vol.Coerce(float), vol.Range(min=0.25, max=4.0)
                ),
                vol.Optional(CONF_VOICE_PITCH, default=DEFAULT_VOICE_PITCH): vol.All(
                    vol.Coerce(float), vol.Range(min=-20.0, max=20.0)
                ),
            }
        )
        
        if user_input is not None:
            # Store voice settings
            self._data.update(user_input)
            
            # Move to advanced settings step
            return await self.async_step_advanced()

        return self.async_show_form(
            step_id="voice",
            data_schema=voice_schema,
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced settings step."""
        errors: dict[str, str] = {}
        
        advanced_schema = vol.Schema(
            {
                vol.Optional(CONF_SYSTEM_PROMPT, default=DEFAULT_SYSTEM_PROMPT): str,
                vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
            }
        )
        
        if user_input is not None:
            # Store advanced settings
            self._data.update(user_input)
            
            # Create the config entry
            return self.async_create_entry(
                title=self._data.get(CONF_NAME, "Gemini AI"),
                data=self._data,
            )

        return self.async_show_form(
            step_id="advanced",
            data_schema=advanced_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Gemini AI."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._data: Dict[str, Any] = dict(config_entry.data)
        self._available_models: Dict[str, Any] = {}
        self._available_voices: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_api_settings()

    async def async_step_api_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle API settings step."""
        errors: dict[str, str] = {}
        
        current_api_key = self.config_entry.data.get(CONF_API_KEY, "")
        
        api_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=current_api_key): str,
            }
        )
        
        if user_input is not None:
            if user_input[CONF_API_KEY] != current_api_key:
                # API key changed, validate it
                try:
                    info = await validate_input(self.hass, user_input)
                    self._available_models = info["available_models"]
                    self._available_voices = info["available_voices"]
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except QuotaExceeded:
                    errors["base"] = "quota_exceeded"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                
                if errors:
                    return self.async_show_form(
                        step_id="api_settings",
                        data_schema=api_schema,
                        errors=errors,
                    )
            
            # Store API key
            self._data.update(user_input)
            return await self.async_step_model_settings()

        return self.async_show_form(
            step_id="api_settings",
            data_schema=api_schema,
            errors=errors,
        )

    async def async_step_model_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle model settings step."""
        errors: dict[str, str] = {}
        
        # Get current settings
        current_tts = self.config_entry.data.get(CONF_TTS_MODEL, DEFAULT_TTS_MODEL)
        current_stt = self.config_entry.data.get(CONF_STT_MODEL, DEFAULT_STT_MODEL)
        current_conversation = self.config_entry.data.get(CONF_CONVERSATION_MODEL, DEFAULT_CONVERSATION_MODEL)
        
        # Use available models if we have them, otherwise use defaults
        if self._available_models:
            tts_models = self._available_models.get("tts", [DEFAULT_TTS_MODEL])
            stt_models = self._available_models.get("stt", [DEFAULT_STT_MODEL])
            conversation_models = self._available_models.get("conversation", [DEFAULT_CONVERSATION_MODEL])
        else:
            tts_models = [DEFAULT_TTS_MODEL]
            stt_models = [DEFAULT_STT_MODEL]
            conversation_models = [DEFAULT_CONVERSATION_MODEL]
        
        models_schema = vol.Schema(
            {
                vol.Required(CONF_TTS_MODEL, default=current_tts): vol.In(tts_models),
                vol.Required(CONF_STT_MODEL, default=current_stt): vol.In(stt_models),
                vol.Required(CONF_CONVERSATION_MODEL, default=current_conversation): vol.In(conversation_models),
            }
        )
        
        if user_input is not None:
            # Store model settings
            self._data.update(user_input)
            return await self.async_step_voice_settings()

        return self.async_show_form(
            step_id="model_settings",
            data_schema=models_schema,
            errors=errors,
        )

    async def async_step_voice_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle voice settings step."""
        errors: dict[str, str] = {}
        
        # Get current settings
        current_voice = self.config_entry.data.get(CONF_DEFAULT_VOICE, DEFAULT_VOICE)
        current_speed = self.config_entry.data.get(CONF_VOICE_SPEED, DEFAULT_VOICE_SPEED)
        current_pitch = self.config_entry.data.get(CONF_VOICE_PITCH, DEFAULT_VOICE_PITCH)
        current_system_prompt = self.config_entry.data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)
        current_language = self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        
        # Use available voices if we have them, otherwise use defaults
        voices = self._available_voices if self._available_voices else AVAILABLE_VOICES
        
        voice_schema = vol.Schema(
            {
                vol.Required(CONF_DEFAULT_VOICE, default=current_voice): vol.In(voices),
                vol.Optional(CONF_VOICE_SPEED, default=current_speed): vol.All(
                    vol.Coerce(float), vol.Range(min=0.25, max=4.0)
                ),
                vol.Optional(CONF_VOICE_PITCH, default=current_pitch): vol.All(
                    vol.Coerce(float), vol.Range(min=-20.0, max=20.0)
                ),
                vol.Optional(CONF_SYSTEM_PROMPT, default=current_system_prompt): str,
                vol.Optional(CONF_LANGUAGE, default=current_language): str,
            }
        )
        
        if user_input is not None:
            # Store voice settings
            self._data.update(user_input)
            
            # Update the config entry
            return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="voice_settings",
            data_schema=voice_schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class QuotaExceeded(HomeAssistantError):
    """Error to indicate quota is exceeded.""" 