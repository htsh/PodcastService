from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


@dataclass
class Summary:
    """Episode summary structure"""
    comprehensive_summary: str = ""
    key_insights: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    wisdom: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Summary':
        if not data:
            return cls()
        return cls(
            comprehensive_summary=data.get('comprehensive_summary', ''),
            key_insights=data.get('key_insights', []),
            action_items=data.get('action_items', []),
            wisdom=data.get('wisdom', []),
            topics=data.get('topics', [])
        )


@dataclass
class Episode:
    """Episode document model"""
    url: str
    title: str
    file_hash: str
    audio_path: str
    processed_at: str
    duration: int = 0
    transcript_path: Optional[str] = None
    transcript: Optional[str] = None  # Store full transcript in DB
    summary_path: Optional[str] = None
    summary: Optional[Summary] = None
    has_summary: bool = False
    subscription_id: Optional[str] = None
    subscription_type: Optional[str] = None  # 'podcast' or 'youtube'
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None  # MongoDB _id as string
    # Speaker diarization fields
    transcript_segments: Optional[List[Dict]] = None  # Segments with speaker labels
    speaker_count: Optional[int] = None
    speakers: Optional[List[str]] = None
    has_diarization: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for MongoDB insertion"""
        data = {
            'url': self.url,
            'title': self.title,
            'file_hash': self.file_hash,
            'audio_path': self.audio_path,
            'processed_at': self.processed_at,
            'duration': self.duration,
            'has_summary': self.has_summary,
            'has_diarization': self.has_diarization,
            'metadata': self.metadata
        }

        # Optional fields
        if self.transcript_path:
            data['transcript_path'] = self.transcript_path
        if self.transcript:
            data['transcript'] = self.transcript
        if self.summary_path:
            data['summary_path'] = self.summary_path
        if self.summary:
            data['summary'] = self.summary.to_dict() if isinstance(self.summary, Summary) else self.summary
        if self.subscription_id:
            data['subscription_id'] = self.subscription_id
        if self.subscription_type:
            data['subscription_type'] = self.subscription_type
        if self.id:
            data['id'] = self.id
        # Diarization fields
        if self.transcript_segments:
            data['transcript_segments'] = self.transcript_segments
        if self.speaker_count is not None:
            data['speaker_count'] = self.speaker_count
        if self.speakers:
            data['speakers'] = self.speakers

        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Episode':
        """Create Episode from MongoDB document"""
        summary_data = data.get('summary')
        summary = Summary.from_dict(summary_data) if summary_data else None

        return cls(
            url=data['url'],
            title=data['title'],
            file_hash=data['file_hash'],
            audio_path=data['audio_path'],
            processed_at=data['processed_at'],
            duration=data.get('duration', 0),
            transcript_path=data.get('transcript_path'),
            transcript=data.get('transcript'),
            summary_path=data.get('summary_path'),
            summary=summary,
            has_summary=data.get('has_summary', False),
            subscription_id=data.get('subscription_id'),
            subscription_type=data.get('subscription_type'),
            metadata=data.get('metadata', {}),
            id=str(data.get('_id', '')) if data.get('_id') else data.get('id'),
            # Diarization fields
            transcript_segments=data.get('transcript_segments'),
            speaker_count=data.get('speaker_count'),
            speakers=data.get('speakers'),
            has_diarization=data.get('has_diarization', False)
        )


@dataclass
class Subscription:
    """Subscription document model"""
    id: str
    type: str  # 'podcast' or 'youtube'
    title: str = ""
    feed_url: Optional[str] = None  # For podcasts
    url: Optional[str] = None  # For YouTube
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for MongoDB insertion"""
        data = {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'created_at': self.created_at,
            'metadata': self.metadata
        }
        if self.feed_url:
            data['feed_url'] = self.feed_url
        if self.url:
            data['url'] = self.url
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Subscription':
        """Create Subscription from MongoDB document"""
        return cls(
            id=data['id'],
            type=data['type'],
            title=data.get('title', ''),
            feed_url=data.get('feed_url'),
            url=data.get('url'),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            metadata=data.get('metadata', {})
        )


@dataclass
class Settings:
    """Settings document model"""
    default_model: str = "base"
    output_format: str = "txt"
    auto_summarize: bool = True
    additional_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for MongoDB insertion"""
        return {
            'default_model': self.default_model,
            'output_format': self.output_format,
            'auto_summarize': self.auto_summarize,
            'additional_settings': self.additional_settings
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Settings':
        """Create Settings from MongoDB document"""
        return cls(
            default_model=data.get('default_model', 'base'),
            output_format=data.get('output_format', 'txt'),
            auto_summarize=data.get('auto_summarize', True),
            additional_settings=data.get('additional_settings', {})
        )
