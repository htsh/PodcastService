# Speaker Diarization

This document describes the speaker diarization feature that separates speakers in podcast transcripts.

## Overview

Speaker diarization identifies and labels different speakers in an audio file, producing a transcript with speaker labels like `SPEAKER_00`, `SPEAKER_01`, etc.

## Features

- **Automatic Speaker Detection**: Identifies speakers without prior knowledge
- **Speaker Segmentation**: Breaks transcript into segments by speaker
- **Speaker Count**: Reports the number of unique speakers
- **Formatted Transcripts**: Creates readable transcripts with speaker labels
- **API Access**: Full diarization data available via REST API

## Setup

### 1. Install Dependencies

The speaker diarization feature requires additional Python packages:

```bash
pip install -r requirements.txt
```

This installs:
- `pyannote.audio>=3.1.0` - Speaker diarization models
- `torch>=2.0.0` - PyTorch for neural networks
- `torchaudio>=2.0.0` - Audio processing for PyTorch

### 2. Get HuggingFace Token

Speaker diarization uses models from HuggingFace that require authentication:

1. Create a free account at [huggingface.co](https://huggingface.co)
2. Go to [Settings > Access Tokens](https://huggingface.co/settings/tokens)
3. Create a new token with read permissions
4. Accept the model terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)

### 3. Configure Environment

Add to your `.env` file:

```bash
# Enable speaker diarization
ENABLE_DIARIZATION=true

# Your HuggingFace token
HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxx

# Optional: Constrain speaker count
# MIN_SPEAKERS=2
# MAX_SPEAKERS=5
```

## Usage

### Processing Episodes

Once configured, diarization happens automatically when processing episodes:

```bash
# Process a podcast episode
curl -X POST "http://localhost:8000/api/process/episode?url=PODCAST_URL"
```

### API Endpoints

#### Get Transcript with Diarization

```bash
GET /api/transcript/{url}
```

Returns:
```json
{
  "transcript": "Full transcript text...",
  "has_diarization": true,
  "speaker_count": 2,
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Welcome to the show.",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 5.5,
      "end": 10.3,
      "text": "Thanks for having me.",
      "speaker": "SPEAKER_01"
    }
  ]
}
```

#### Get Diarization Data Only

```bash
GET /api/diarization/{url}
```

Returns speaker information and segments without the full transcript.

### Episode History

The `/api/history` endpoint includes diarization status:

```json
{
  "url": "...",
  "title": "...",
  "has_diarization": true,
  "speaker_count": 2,
  "speakers": ["SPEAKER_00", "SPEAKER_01"]
}
```

## Configuration Options

### ENABLE_DIARIZATION

- **Type**: Boolean (true/false)
- **Default**: true
- **Description**: Enable or disable speaker diarization globally

### HUGGINGFACE_TOKEN

- **Type**: String
- **Required**: Yes (when diarization enabled)
- **Description**: HuggingFace API token for accessing pyannote models

### MIN_SPEAKERS

- **Type**: Integer
- **Optional**: Yes
- **Description**: Minimum number of expected speakers (helps improve accuracy)

### MAX_SPEAKERS

- **Type**: Integer
- **Optional**: Yes
- **Description**: Maximum number of expected speakers (helps improve accuracy)

## Technical Details

### Architecture

The diarization system uses a two-stage pipeline:

1. **Transcription**: MLX Whisper transcribes the audio to text
2. **Diarization**: pyannote.audio identifies speaker segments
3. **Alignment**: Segments are aligned to produce speaker-labeled transcript

### Models

- **Transcription**: MLX Whisper (Apple Silicon optimized)
- **Diarization**: pyannote/speaker-diarization-3.1

### Hardware Acceleration

The system automatically detects and uses available hardware:

- **NVIDIA GPU**: CUDA acceleration (fastest)
- **Apple Silicon**: MPS backend (Metal Performance Shaders)
- **CPU**: Fallback option (slower but works everywhere)

### Performance

Processing times vary based on audio length and hardware:

- **With GPU**: ~30-50% of audio duration
- **With CPU**: ~100-200% of audio duration

For a 1-hour podcast:
- **GPU**: 18-30 minutes
- **CPU**: 60-120 minutes

### Storage Impact

Diarization adds speaker segment metadata:

- **Segment data**: ~2-3x transcript size
- **For 1-hour podcast**: ~50KB → ~150KB (negligible)

## Accuracy

Diarization accuracy depends on audio quality:

- **High quality audio**: 90-95% accuracy
- **Background noise**: 70-85% accuracy
- **Overlapping speech**: 60-75% accuracy
- **Many speakers (5+)**: 65-80% accuracy

## Troubleshooting

### "Failed to initialize diarization pipeline"

**Cause**: Missing HuggingFace token or haven't accepted model terms

**Solution**:
1. Verify `HUGGINGFACE_TOKEN` in `.env`
2. Accept terms at https://huggingface.co/pyannote/speaker-diarization-3.1

### "pyannote.audio not installed"

**Cause**: Dependencies not installed

**Solution**:
```bash
pip install pyannote.audio torch torchaudio
```

### Diarization is slow

**Cause**: Running on CPU without GPU acceleration

**Solutions**:
- Use a machine with NVIDIA GPU or Apple Silicon
- Reduce audio length
- Process episodes in background (already implemented)

### Speaker count is incorrect

**Cause**: Automatic detection can sometimes over/under-segment

**Solutions**:
- Set `MIN_SPEAKERS` and `MAX_SPEAKERS` in `.env`
- Higher quality audio improves detection

## Disabling Diarization

To disable diarization without uninstalling:

```bash
# In .env
ENABLE_DIARIZATION=false
```

The system will continue to work normally without diarization.

## Data Model

Episodes with diarization include these fields:

```python
{
    "has_diarization": bool,
    "speaker_count": int,
    "speakers": List[str],  # ["SPEAKER_00", "SPEAKER_01", ...]
    "transcript_segments": List[{
        "start": float,      # Start time in seconds
        "end": float,        # End time in seconds
        "text": str,         # Segment text
        "speaker": str       # Speaker label
    }]
}
```

## Future Enhancements

Potential future improvements:

- Speaker name customization (label speakers by name)
- Speaker verification (verify speaker identity across episodes)
- Voice characteristics (gender, age, accent detection)
- Conversation analytics (speaking time, interruptions, etc.)
- Export formats (SRT subtitles with speakers, VTT, etc.)

## References

- [pyannote.audio documentation](https://github.com/pyannote/pyannote-audio)
- [pyannote models on HuggingFace](https://huggingface.co/pyannote)
- [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
