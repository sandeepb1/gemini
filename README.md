# Gemini AI Integration for Home Assistant

A comprehensive Home Assistant custom component that integrates Google Gemini AI for Text-to-Speech (TTS), Speech-to-Text (STT), and Conversation Agent capabilities.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/custom-components/gemini_ai.svg)](https://github.com/custom-components/gemini_ai/releases)
[![License](https://img.shields.io/github/license/custom-components/gemini_ai.svg)](LICENSE)

## Features

### 🎙️ Text-to-Speech (TTS)
- Multiple voice options (Aoede, Charon, Fenrir, Kore, Puck)
- Configurable speech speed and pitch
- 70+ language support
- Intelligent caching system
- Real-time voice preview

### 🎧 Speech-to-Text (STT)
- Multiple audio format support (WAV, OGG, FLAC, MP3, M4A)
- Large file chunking for efficient processing
- 70+ language support
- Stream processing capabilities
- File and stream transcription

### 💬 Conversation Agent
- Context-aware conversations
- Persistent conversation history
- Custom system prompts
- Intent recognition for Home Assistant
- Multi-language support
- Multiple concurrent conversations

### 🛠️ Services
- `gemini_ai.say` - Text-to-speech service
- `gemini_ai.transcribe` - Audio transcription service
- `gemini_ai.process` - Conversation processing service
- `gemini_ai.preview_voice` - Voice preview service

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/custom-components/gemini_ai` as repository
6. Select "Integration" as category
7. Click "Add"
8. Search for "Gemini AI" and install

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/custom-components/gemini_ai/releases)
2. Extract the contents
3. Copy the `custom_components/gemini_ai` folder to your Home Assistant `custom_components` directory
4. Restart Home Assistant

## Configuration

### Getting an API Key

1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Create a new API key
4. Copy the API key for use in Home Assistant

### Setting up the Integration

1. Go to **Settings** > **Devices & Services** in Home Assistant
2. Click **+ Add Integration**
3. Search for "Gemini AI"
4. Follow the setup wizard:
   - Enter your API key
   - Select models for each service
   - Configure voice preferences
   - Set advanced options

### Configuration Options

#### API Settings
- **API Key**: Your Google AI Studio API key (required)

#### Model Selection
- **TTS Model**: Model for text-to-speech (default: gemini-2.0-flash-exp)
- **STT Model**: Model for speech-to-text (default: gemini-2.0-flash)
- **Conversation Model**: Model for conversations (default: gemini-2.0-flash)

#### Voice Configuration
- **Default Voice**: Choose from Aoede, Charon, Fenrir, Kore, Puck
- **Voice Speed**: 0.25 to 4.0 (default: 1.0)
- **Voice Pitch**: -20.0 to 20.0 (default: 0.0)

#### Advanced Settings
- **System Prompt**: Custom prompt for the conversation agent
- **Language**: Default language code (default: en)

## Usage

### Text-to-Speech

#### Using the Service

```yaml
service: gemini_ai.say
data:
  message: "Hello, this is Gemini AI speaking!"
  voice: "Aoede"
  speed: 1.2
  language: "en"
```

#### Using the TTS Platform

```yaml
service: tts.speak
data:
  entity_id: tts.gemini_ai_tts
  message: "Hello from Home Assistant!"
  options:
    voice: "Charon"
    speed: 1.0
```

### Speech-to-Text

#### Transcribe Audio File

```yaml
service: gemini_ai.transcribe
data:
  audio_file: "/config/www/recording.wav"
  language: "en"
```

#### Using STT Platform

The integration automatically registers as an STT provider and can be used with Home Assistant's voice assistant features.

### Conversation Agent

#### Direct Service Call

```yaml
service: gemini_ai.process
data:
  text: "What's the weather like today?"
  conversation_id: "living_room"
  system_prompt: "You are a helpful home assistant."
```

#### Using as Default Conversation Agent

1. Go to **Settings** > **Voice assistants**
2. Select your voice assistant
3. Set "Conversation agent" to "Gemini AI Conversation"

### Voice Preview

```yaml
service: gemini_ai.preview_voice
data:
  voice: "Fenrir"
  text: "This is how Fenrir sounds."
  speed: 1.5
```

## Automation Examples

### Morning Announcement

```yaml
automation:
  - alias: "Morning Announcement"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      service: gemini_ai.say
      data:
        message: "Good morning! The weather today is {{ states('weather.home') }}."
        voice: "Aoede"
        speed: 1.0
```

### Voice Message Transcription

```yaml
automation:
  - alias: "Transcribe Voice Messages"
    trigger:
      platform: event
      event_type: folder_watcher
      event_data:
        event_type: created
    condition:
      condition: template
      value_template: "{{ trigger.event.data.file.endswith('.wav') }}"
    action:
      service: gemini_ai.transcribe
      data:
        audio_file: "{{ trigger.event.data.path }}"
```

### Smart Response System

```yaml
automation:
  - alias: "Smart Door Response"
    trigger:
      platform: state
      entity_id: binary_sensor.front_door
      to: "on"
    action:
      - service: gemini_ai.process
        data:
          text: "Someone is at the front door. What should I do?"
          conversation_id: "security"
        response_variable: ai_response
      - service: tts.speak
        data:
          entity_id: tts.gemini_ai_tts
          message: "{{ ai_response.text }}"
```

## Events

The integration fires several events that can be used in automations:

### `gemini_ai_tts_complete`
Fired when TTS generation is complete.

```yaml
trigger:
  platform: event
  event_type: gemini_ai_tts_complete
```

### `gemini_ai_stt_complete`
Fired when STT transcription is complete.

```yaml
trigger:
  platform: event
  event_type: gemini_ai_stt_complete
```

### `gemini_ai_conversation_response`
Fired when conversation processing is complete.

```yaml
trigger:
  platform: event
  event_type: gemini_ai_conversation_response
```

### `gemini_ai_error`
Fired when an error occurs.

```yaml
trigger:
  platform: event
  event_type: gemini_ai_error
```

## Troubleshooting

### Common Issues

#### API Key Invalid
- Verify your API key at [Google AI Studio](https://aistudio.google.com/)
- Ensure the API key has the necessary permissions
- Check that you're using the correct API key format

#### Quota Exceeded
- Check your usage limits in Google AI Studio
- Consider upgrading your plan if needed
- Monitor your API usage patterns

#### Audio File Too Large
- Maximum file size is 10MB
- Use compressed audio formats like MP3 or OGG
- Consider splitting large files into smaller chunks

#### Network Connectivity
- Ensure Home Assistant has internet access
- Check firewall settings
- Verify DNS resolution

### Debug Logging

Add this to your `configuration.yaml` to enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.gemini_ai: debug
```

## Advanced Configuration

### Custom System Prompts

You can customize the conversation agent's behavior with system prompts:

```yaml
# In the integration options
system_prompt: |
  You are a helpful home automation assistant. You can:
  - Control lights, switches, and other devices
  - Provide weather information
  - Answer questions about home status
  - Be friendly and conversational
  
  Always respond in a helpful and concise manner.
```

### Performance Optimization

#### Caching
- TTS responses are automatically cached for 1 hour
- Cache size is limited to 100 items
- Clear cache by restarting Home Assistant

#### Rate Limiting
- Maximum 5 concurrent API requests
- Automatic retry with exponential backoff
- Request timeout of 30 seconds

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Run tests: `pytest`
4. Run linting: `pre-commit run --all-files`

## Support

- [GitHub Issues](https://github.com/custom-components/gemini_ai/issues)
- [Home Assistant Community](https://community.home-assistant.io/)
- [Discord](https://discord.gg/home-assistant)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Google for the Gemini AI API
- Home Assistant team for the excellent platform
- The Home Assistant community for support and feedback