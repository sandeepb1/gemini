# Home Assistant Custom Component: Gemini AI Integration

Create a comprehensive Home Assistant custom component (HACS compatible) that integrates Google
Gemini AI for Text-to-Speech (TTS), Speech-to-Text (STT), and Conversation Agent capabilities.

## Core Requirements

### Integration Overview

- **Name**: Gemini AI Integration
- **Domain**: `gemini_ai`
- **Platform**: Home Assistant Custom Component (HACS compatible)
- **API**: Google AI Studio Gemini API (NOT Google Cloud Platform)
- **Key Features**: TTS, STT, and Conversation Agent

### API Integration Details

1. **Authentication**
    - Use API Key from Google AI Studio (https://aistudio.google.com/)
    - Store API key securely using Home Assistant's credential storage
    - Validate API key on configuration

2. **Model Support**
    - TTS: `gemini-2.0-flash-exp` (via Live API)
    - STT: `gemini-2.0-flash` or `gemini-1.5-flash`
    - Conversation: `gemini-2.0-flash` or `gemini-1.5-flash`

3. **API Endpoints**
    - Base URL: `https://generativelanguage.googleapis.com/v1beta/`
    - TTS: Use Live API with WebSocket connection
    - STT: Use audio upload endpoint
    - Conversation: Use generateContent endpoint

## Technical Implementation

### File Structure

```
custom_components/
└── gemini_ai/
    ├── __init__.py
    ├── manifest.json
    ├── config_flow.py
    ├── const.py
    ├── tts.py
    ├── stt.py
    ├── conversation.py
    ├── api_client.py
    ├── translations/
    │   └── en.json
    └── services.yaml
```

### Component Architecture

1. **__init__.py**
    - Initialize the integration
    - Set up platforms (tts, stt, conversation)
    - Handle configuration updates
    - Manage API client lifecycle

2. **config_flow.py**
    - Implement ConfigFlow for UI-based setup
    - API key validation
    - Model selection for each service
    - Voice selection for TTS with preview functionality
    - Store configuration in config entry

3. **api_client.py**
    - Centralized API client for all Gemini services
    - Handle authentication
    - Implement retry logic and error handling
    - WebSocket management for Live API

4. **tts.py**
    - Implement TextToSpeechEntity
    - Use Gemini Live API for speech synthesis
    - Support multiple voices
    - Handle audio streaming
    - Cache generated audio

5. **stt.py**
    - Implement SpeechToTextEntity
    - Use Gemini audio API for transcription
    - Support multiple audio formats
    - Handle large audio files with chunking

6. **conversation.py**
    - Implement ConversationEntity
    - Use Gemini chat API
    - Maintain conversation context
    - Support system prompts
    - Handle multi-turn conversations

### Configuration UI Requirements

1. **Initial Setup Flow**
   ```python
   # Step 1: API Key
   - Text input for API key
   - Validate button to test connection
   - Error handling for invalid keys

   # Step 2: Model Selection
   - Dropdown for TTS model
   - Dropdown for STT model
   - Dropdown for Conversation model
   - Show available models based on API capabilities

   # Step 3: TTS Voice Configuration
   - List available voices
   - Play button for each voice preview
   - Select default voice
   - Voice speed/pitch controls (if supported)
   ```

2. **Options Flow**
    - Allow reconfiguration of all settings
    - Add/remove services
    - Update API key

### API Implementation Details

1. **TTS Implementation**
   ```python
   # Use WebSocket for Live API
   # Handle streaming audio
   # Support voice selection
   # Implement audio format conversion
   ```

2. **STT Implementation**
   ```python
   # Handle audio upload
   # Support multiple formats (mp3, wav, ogg)
   # Implement chunking for large files
   # Return transcription with confidence scores
   ```

3. **Conversation Implementation**
   ```python
   # Maintain conversation history
   # Support custom system prompts
   # Handle context management
   # Implement intent recognition
   ```

### Home Assistant Integration Points

1. **Services**
    - `gemini_ai.say` - TTS service
    - `gemini_ai.transcribe` - STT service
    - `gemini_ai.process` - Conversation service
    - `gemini_ai.preview_voice` - Voice preview service

2. **Events**
    - Fire events for transcription completion
    - Fire events for conversation responses
    - Fire events for errors

3. **Entities**
    - TTS entity with voice selection
    - STT entity with language support
    - Conversation entity with agent capabilities

### Error Handling

1. **API Errors**
    - Rate limiting with exponential backoff
    - Quota exceeded notifications
    - Network error recovery
    - Invalid API key handling

2. **User Errors**
    - Clear error messages in UI
    - Validation for all inputs
    - Helpful error recovery suggestions

### Performance Optimization

1. **Caching**
    - Cache TTS audio for repeated phrases
    - Cache model capabilities
    - Cache voice samples

2. **Resource Management**
    - Limit concurrent API calls
    - Implement request queuing
    - Clean up old cache entries

### Security Considerations

1. **API Key Storage**
    - Use Home Assistant's secure storage
    - Never log API keys
    - Encrypt sensitive data

2. **Data Privacy**
    - Don't store conversation history by default
    - Allow users to opt-in to history
    - Implement data retention policies

### Testing Requirements

1. **Unit Tests**
    - Test each component independently
    - Mock API responses
    - Test error conditions

2. **Integration Tests**
    - Test with Home Assistant
    - Test UI flows
    - Test service calls

### Documentation

1. **README.md**
    - Installation instructions
    - Configuration guide
    - Usage examples
    - Troubleshooting

2. **Code Documentation**
    - Docstrings for all classes/methods
    - Type hints throughout
    - Comments for complex logic

### HACS Compatibility

1. **Repository Structure**
    - Follow HACS requirements
    - Include hacs.json
    - Version tagging
    - Release notes

2. **Validation**
    - Pass HACS validation
    - No blocking errors
    - Proper categorization

## Specific Implementation Notes

1. **DO NOT** use Google Cloud Platform APIs or authentication
2. **DO NOT** create demo content or example automations
3. **DO NOT** hardcode any API keys or sensitive data
4. **DO** use async/await throughout for non-blocking operations
5. **DO** follow Home Assistant development best practices
6. **DO** implement proper logging with appropriate levels

## UI/UX Requirements

1. **Configuration UI**
    - Clean, intuitive interface
    - Step-by-step wizard
    - Real-time validation
    - Preview capabilities

2. **Voice Preview**
    - Play button for each voice option
    - Sample text for preview
    - Loading indicators
    - Error handling for preview failures

3. **Model Selection**
    - Show model capabilities
    - Indicate which models support which features
    - Default recommendations

## Additional Features

1. **Advanced Options**
    - Custom system prompts for conversation
    - Audio preprocessing options
    - Response filtering
    - Language preferences

2. **Monitoring**
    - API usage statistics
    - Response time metrics
    - Error rate tracking

3. **Backup/Restore**
    - Export configuration
    - Import configuration
    - Migration support

Create this integration following Home Assistant's development guidelines, ensuring it's
production-ready, well-tested, and user-friendly. The integration should be installable via HACS and
provide a seamless experience for users wanting to use Gemini AI services in their Home Assistant
setup.
