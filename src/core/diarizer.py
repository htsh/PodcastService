from pathlib import Path
from typing import Optional, Dict, List
import os
import warnings

# Suppress pyannote warnings
warnings.filterwarnings('ignore', category=UserWarning)


class Diarizer:
    """Speaker diarization using pyannote.audio"""

    def __init__(
        self,
        hf_token: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        use_auth_token: Optional[str] = None
    ):
        """
        Initialize the diarizer.

        Args:
            hf_token: HuggingFace token for accessing pyannote models
            min_speakers: Minimum number of expected speakers
            max_speakers: Maximum number of expected speakers
            use_auth_token: Deprecated, use hf_token instead
        """
        self.hf_token = hf_token or use_auth_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.pipeline = None
        self._initialized = False

    def _initialize_pipeline(self):
        """Lazy initialization of the pyannote pipeline."""
        if self._initialized:
            return

        try:
            from pyannote.audio import Pipeline

            print("Initializing speaker diarization pipeline...")

            # Use the latest pyannote model
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )

            # Try to use GPU if available
            try:
                import torch
                if torch.cuda.is_available():
                    self.pipeline.to(torch.device("cuda"))
                    print("Using GPU for diarization")
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    self.pipeline.to(torch.device("mps"))
                    print("Using Apple Silicon MPS for diarization")
                else:
                    print("Using CPU for diarization")
            except Exception as e:
                print(f"GPU detection failed, using CPU: {e}")

            self._initialized = True
            print("Diarization pipeline initialized successfully")

        except ImportError as e:
            raise RuntimeError(
                "pyannote.audio not installed. Install with: pip install pyannote.audio"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize diarization pipeline. "
                f"Make sure you have accepted the pyannote model terms at: "
                f"https://huggingface.co/pyannote/speaker-diarization-3.1 "
                f"and provided a valid HuggingFace token. Error: {e}"
            ) from e

    def diarize(self, audio_path: Path) -> Optional[Dict]:
        """
        Perform speaker diarization on an audio file.

        Args:
            audio_path: Path to the audio file

        Returns:
            Dictionary with diarization results:
            {
                'segments': [
                    {
                        'start': float,
                        'end': float,
                        'speaker': str
                    },
                    ...
                ],
                'speakers': [str],  # List of unique speaker labels
                'speaker_count': int
            }
            Returns None if diarization fails.
        """
        try:
            # Initialize pipeline on first use
            if not self._initialized:
                self._initialize_pipeline()

            print(f"Performing speaker diarization on {audio_path}")

            # Prepare diarization parameters
            diarization_params = {}
            if self.min_speakers is not None:
                diarization_params['min_speakers'] = self.min_speakers
            if self.max_speakers is not None:
                diarization_params['max_speakers'] = self.max_speakers

            # Run diarization
            diarization = self.pipeline(str(audio_path), **diarization_params)

            # Convert pyannote output to our format
            segments = []
            speakers = set()

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segment = {
                    'start': float(turn.start),
                    'end': float(turn.end),
                    'speaker': speaker
                }
                segments.append(segment)
                speakers.add(speaker)

            result = {
                'segments': segments,
                'speakers': sorted(list(speakers)),
                'speaker_count': len(speakers)
            }

            print(f"Diarization complete: found {len(speakers)} speakers in {len(segments)} segments")

            return result

        except Exception as e:
            print(f"Error during diarization of {audio_path}: {e}")
            print("Continuing without speaker diarization")
            return None

    def align_transcript_with_diarization(
        self,
        transcript_segments: List[Dict],
        diarization_segments: List[Dict]
    ) -> List[Dict]:
        """
        Align transcript segments with speaker diarization.

        Args:
            transcript_segments: List of transcript segments with 'start', 'end', 'text'
            diarization_segments: List of speaker segments with 'start', 'end', 'speaker'

        Returns:
            List of aligned segments with speaker labels:
            [
                {
                    'start': float,
                    'end': float,
                    'text': str,
                    'speaker': str
                },
                ...
            ]
        """
        if not diarization_segments:
            return transcript_segments

        aligned_segments = []

        for trans_seg in transcript_segments:
            trans_start = trans_seg['start']
            trans_end = trans_seg['end']
            trans_mid = (trans_start + trans_end) / 2

            # Find the speaker segment that overlaps most with this transcript segment
            best_speaker = None
            best_overlap = 0

            for diar_seg in diarization_segments:
                diar_start = diar_seg['start']
                diar_end = diar_seg['end']

                # Calculate overlap
                overlap_start = max(trans_start, diar_start)
                overlap_end = min(trans_end, diar_end)
                overlap = max(0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = diar_seg['speaker']

            # Create aligned segment
            aligned_seg = trans_seg.copy()
            aligned_seg['speaker'] = best_speaker or 'UNKNOWN'
            aligned_segments.append(aligned_seg)

        return aligned_segments

    def format_transcript_with_speakers(self, segments: List[Dict]) -> str:
        """
        Format transcript segments with speaker labels.

        Args:
            segments: List of segments with 'speaker' and 'text'

        Returns:
            Formatted transcript string with speaker labels
        """
        if not segments:
            return ""

        formatted_lines = []
        current_speaker = None

        for segment in segments:
            speaker = segment.get('speaker', 'UNKNOWN')
            text = segment.get('text', '').strip()

            if not text:
                continue

            # Add speaker label when speaker changes
            if speaker != current_speaker:
                formatted_lines.append(f"\n{speaker}:")
                current_speaker = speaker

            formatted_lines.append(text)

        return ' '.join(formatted_lines).strip()
