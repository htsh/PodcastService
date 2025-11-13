from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import hashlib
from pymongo.database import Database

from src.db.gridfs_manager import GridFSManager


class CacheManager:
    """
    Cache manager that uses MongoDB GridFS for all file storage.
    Audio files and transcripts are stored in GridFS instead of filesystem.
    Subscriptions and episodes are handled by repositories.
    """

    def __init__(self, db: Database):
        """Initialize with MongoDB database instance"""
        self.db = db
        self.gridfs = GridFSManager(db)

    def _get_cache_key(self, key: str) -> str:
        """Generate a stable cache key"""
        return hashlib.sha256(key.encode()).hexdigest()

    # Audio file caching (GridFS-based)
    def cache_download(self, url: str, file_path: Path, metadata: Optional[Dict] = None) -> str:
        """
        Cache a downloaded audio file in GridFS.

        Args:
            url: Original URL of the audio
            file_path: Path to temporary file on disk
            metadata: Additional metadata

        Returns:
            GridFS file ID
        """
        return self.gridfs.store_audio(file_path, url, metadata)

    def get_cached_download_path(self, url: str) -> Optional[str]:
        """
        Get GridFS file ID for cached download by URL.

        Args:
            url: Original URL

        Returns:
            GridFS file ID as string, or None if not found
        """
        result = self.gridfs.get_audio_by_url(url)
        return result[0] if result else None

    def get_cached_download_data(self, url: str) -> Optional[bytes]:
        """
        Get audio file data by URL.

        Args:
            url: Original URL

        Returns:
            File data as bytes, or None if not found
        """
        result = self.gridfs.get_audio_by_url(url)
        return result[1] if result else None

    def is_download_cached(self, url: str) -> bool:
        """Check if a download is cached in GridFS"""
        return self.get_cached_download_path(url) is not None

    def get_download_metadata(self, url: str) -> Optional[Dict]:
        """Get metadata for a cached download from GridFS"""
        file_id = self.get_cached_download_path(url)
        if file_id:
            return self.gridfs.get_audio_metadata(file_id)
        return None

    # Transcript caching (GridFS-based)
    def cache_transcript(self, audio_path: str, transcript_path: Path) -> str:
        """
        Cache a transcript in GridFS.

        Args:
            audio_path: Reference to audio file (file_id or path)
            transcript_path: Path to temporary transcript file

        Returns:
            GridFS file ID
        """
        # Read transcript text
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_text = f.read()

        # Store in GridFS
        return self.gridfs.store_transcript(
            transcript_text=transcript_text,
            audio_path=audio_path,
            episode_url=audio_path  # Use audio_path as reference
        )

    def get_cached_transcript_path(self, audio_path: str) -> Optional[str]:
        """
        Get GridFS file ID for cached transcript.

        Args:
            audio_path: Audio file reference

        Returns:
            GridFS file ID as string, or None if not found
        """
        result = self.gridfs.get_transcript_by_audio(audio_path)
        return result[0] if result else None

    def get_cached_transcript_text(self, audio_path: str) -> Optional[str]:
        """
        Get transcript text by audio reference.

        Args:
            audio_path: Audio file reference

        Returns:
            Transcript text, or None if not found
        """
        result = self.gridfs.get_transcript_by_audio(audio_path)
        return result[1] if result else None

    def is_transcript_cached(self, audio_path: str) -> bool:
        """Check if a transcript is cached in GridFS"""
        return self.get_cached_transcript_path(audio_path) is not None

    # Subscription and episode management delegated to repositories
    def save_subscription(self, subscription: Dict):
        """Backward compatibility - saves to MongoDB via repository"""
        from src.db import SubscriptionRepository
        from src.db.models import Subscription

        repo = SubscriptionRepository(self.db)
        sub_model = Subscription(
            id=subscription['id'],
            type=subscription['type'],
            title=subscription.get('title', ''),
            feed_url=subscription.get('feed_url'),
            url=subscription.get('url')
        )
        repo.create(sub_model)

    def get_all_subscriptions(self) -> List[Dict]:
        """Backward compatibility - retrieves from MongoDB via repository"""
        from src.db import SubscriptionRepository

        repo = SubscriptionRepository(self.db)
        subscriptions = repo.find_all()
        return [sub.to_dict() for sub in subscriptions]

    def remove_subscription(self, subscription_id: str) -> bool:
        """Backward compatibility - removes from MongoDB via repository"""
        from src.db import SubscriptionRepository

        repo = SubscriptionRepository(self.db)
        return repo.delete(subscription_id)

    # GridFS-specific methods
    def get_audio_by_id(self, file_id: str) -> Optional[bytes]:
        """Get audio file data by GridFS ID"""
        return self.gridfs.get_audio(file_id)

    def get_transcript_by_id(self, file_id: str) -> Optional[str]:
        """Get transcript text by GridFS ID"""
        return self.gridfs.get_transcript(file_id)

    def stream_audio(self, file_id: str):
        """Get a stream handle for audio file (for FastAPI streaming)"""
        return self.gridfs.stream_audio(file_id)

    def get_storage_stats(self) -> Dict:
        """Get GridFS storage statistics"""
        return self.gridfs.get_storage_stats()
