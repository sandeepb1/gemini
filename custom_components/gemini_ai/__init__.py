"""The Gemini AI integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import GeminiAPIClient
from .const import (
    CONF_API_KEY,
    CONF_TTS_MODEL,
    CONF_STT_MODEL,
    CONF_CONVERSATION_MODEL,
    CONF_DEFAULT_VOICE,
    CONF_SYSTEM_PROMPT,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS_MAP = {
    "tts": Platform.TTS,
    "stt": Platform.STT,
    "conversation": Platform.CONVERSATION,
}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Gemini AI integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gemini AI from a config entry."""
    _LOGGER.debug("Setting up Gemini AI integration")
    
    # Get configuration
    api_key = entry.data[CONF_API_KEY]
    
    # Create API client
    session = async_get_clientsession(hass)
    api_client = GeminiAPIClient(
        api_key=api_key,
        session=session,
        hass=hass
    )
    
    # Test API connection
    try:
        await api_client.test_connection()
    except Exception as err:
        _LOGGER.error("Failed to connect to Gemini API: %s", err)
        return False
    
    # Store API client in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        "config": entry.data,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, [PLATFORMS_MAP[platform] for platform in PLATFORMS]
    )
    
    # Register services
    await _async_register_services(hass, entry)
    
    # Listen for config updates
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    
    _LOGGER.info("Gemini AI integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Gemini AI integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [PLATFORMS_MAP[platform] for platform in PLATFORMS]
    )
    
    if unload_ok:
        # Clean up API client
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api_client = data["api_client"]
        await api_client.close()
    
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates."""
    _LOGGER.debug("Updating Gemini AI configuration")
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register integration services."""
    try:
        from .services import async_register_services
        
        data = hass.data[DOMAIN][entry.entry_id]
        api_client = data["api_client"]
        
        await async_register_services(hass, api_client)
        _LOGGER.debug("Services registered successfully for domain: %s", DOMAIN)
    except Exception as err:
        _LOGGER.error("Failed to register services for %s: %s", DOMAIN, err)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Migration logic for future versions
        pass

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True 