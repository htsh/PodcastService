"""
GridFS Manager for storing large files in MongoDB.

This module provides a high-level interface for storing and retrieving
audio files and transcripts using MongoDB's GridFS.
"""

from pathlib import Path
from typing import Optional, BinaryIO, Dict, Any
from datetime import datetime
import hashlib
import logging
from io import BytesIO

from pymongo.database import Database
from gridfs import GridFS, GridFSBucket
from bson import ObjectId

logger = logging.getLogger(__name__)


class GridFSManager:
    """Manager for GridFS file operations"""

    def __init__(self, db: Database):
        """
        Initialize GridFS manager with database connection.

        Creates two GridFS buckets:
        - audio_files: For storing downloaded audio
        - transcripts: For storing transcript text files
        """
        self.db = db
        self.audio_bucket = GridFSBucket(db, bucket_name="audio_files")
        self.transcript_bucket = GridFSBucket(db, bucket_name="transcripts")
        logger.info("GridFS manager initialized with audio_files and transcripts buckets")

    def _get_file_hash(self, file_data: bytes) -> str:
        """Generate SHA256 hash of file content"""
        return hashlib.sha256(file_data).hexdigest()

    # Audio file operations

    def store_audio(
        self,
        file_path: Path,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store an audio file in GridFS.

        Args:
            file_path: Path to the audio file on disk
            url: Original URL of the audio
            metadata: Additional metadata to store

        Returns:
            GridFS file ID as string
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Generate hash for deduplication
            file_hash = self._get_file_hash(file_data)

            # Check if file already exists
            existing = self.db.audio_files.files.find_one({"metadata.file_hash": file_hash})
            if existing:
                logger.info(f"Audio file already exists in GridFS: {file_hash}")
                return str(existing['_id'])

            # Prepare metadata
            file_metadata = {
                "url": url,
                "file_hash": file_hash,
                "original_filename": file_path.name,
                "uploaded_at": datetime.utcnow().isoformat(),
                "content_type": self._get_content_type(file_path),
            }
            if metadata:
                file_metadata.update(metadata)

            # Upload to GridFS
            file_id = self.audio_bucket.upload_from_stream(
                filename=file_path.name,
                source=BytesIO(file_data),
                metadata=file_metadata
            )

            logger.info(f"Stored audio file in GridFS: {file_path.name} -> {file_id}")
            return str(file_id)

        except Exception as e:
            logger.error(f"Error storing audio file {file_path}: {e}")
            raise

    def get_audio(self, file_id: str) -> Optional[bytes]:
        """
        Retrieve audio file data from GridFS.

        Args:
            file_id: GridFS file ID

        Returns:
            File data as bytes, or None if not found
        """
        try:
            grid_out = self.audio_bucket.open_download_stream(ObjectId(file_id))
            return grid_out.read()
        except Exception as e:
            logger.error(f"Error retrieving audio file {file_id}: {e}")
            return None

    def get_audio_by_url(self, url: str) -> Optional[tuple[str, bytes]]:
        """
        Retrieve audio file by original URL.

        Args:
            url: Original URL of the audio

        Returns:
            Tuple of (file_id, file_data) or None if not found
        """
        try:
            doc = self.db.audio_files.files.find_one({"metadata.url": url})
            if not doc:
                return None

            file_id = str(doc['_id'])
            data = self.get_audio(file_id)
            return (file_id, data) if data else None

        except Exception as e:
            logger.error(f"Error retrieving audio by URL {url}: {e}")
            return None

    def stream_audio(self, file_id: str) -> Optional[GridFSBucket]:
        """
        Get a stream handle for audio file (for streaming responses).

        Args:
            file_id: GridFS file ID

        Returns:
            GridFS download stream
        """
        try:
            return self.audio_bucket.open_download_stream(ObjectId(file_id))
        except Exception as e:
            logger.error(f"Error opening audio stream {file_id}: {e}")
            return None

    def get_audio_metadata(self, file_id: str) -> Optional[Dict]:
        """Get metadata for an audio file"""
        try:
            doc = self.db.audio_files.files.find_one({"_id": ObjectId(file_id)})
            return doc.get('metadata') if doc else None
        except Exception as e:
            logger.error(f"Error getting audio metadata {file_id}: {e}")
            return None

    def delete_audio(self, file_id: str) -> bool:
        """Delete an audio file from GridFS"""
        try:
            self.audio_bucket.delete(ObjectId(file_id))
            logger.info(f"Deleted audio file: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting audio file {file_id}: {e}")
            return False

    # Transcript operations

    def store_transcript(
        self,
        transcript_text: str,
        audio_path: str,
        episode_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a transcript in GridFS.

        Args:
            transcript_text: The transcript text content
            audio_path: Reference to audio file (file_id or path)
            episode_url: Original episode URL
            metadata: Additional metadata

        Returns:
            GridFS file ID as string
        """
        try:
            # Convert text to bytes
            text_data = transcript_text.encode('utf-8')

            # Generate hash for deduplication
            file_hash = self._get_file_hash(text_data)

            # Check if transcript already exists
            existing = self.db.transcripts.files.find_one({"metadata.file_hash": file_hash})
            if existing:
                logger.info(f"Transcript already exists in GridFS: {file_hash}")
                return str(existing['_id'])

            # Prepare metadata
            file_metadata = {
                "audio_path": audio_path,
                "episode_url": episode_url,
                "file_hash": file_hash,
                "uploaded_at": datetime.utcnow().isoformat(),
                "content_type": "text/plain",
                "char_count": len(transcript_text),
            }
            if metadata:
                file_metadata.update(metadata)

            # Upload to GridFS
            filename = f"transcript_{file_hash[:12]}.txt"
            file_id = self.transcript_bucket.upload_from_stream(
                filename=filename,
                source=BytesIO(text_data),
                metadata=file_metadata
            )

            logger.info(f"Stored transcript in GridFS: {filename} -> {file_id}")
            return str(file_id)

        except Exception as e:
            logger.error(f"Error storing transcript: {e}")
            raise

    def get_transcript(self, file_id: str) -> Optional[str]:
        """
        Retrieve transcript text from GridFS.

        Args:
            file_id: GridFS file ID

        Returns:
            Transcript text, or None if not found
        """
        try:
            grid_out = self.transcript_bucket.open_download_stream(ObjectId(file_id))
            return grid_out.read().decode('utf-8')
        except Exception as e:
            logger.error(f"Error retrieving transcript {file_id}: {e}")
            return None

    def get_transcript_by_audio(self, audio_path: str) -> Optional[tuple[str, str]]:
        """
        Retrieve transcript by audio file reference.

        Args:
            audio_path: Audio file path or ID

        Returns:
            Tuple of (file_id, transcript_text) or None if not found
        """
        try:
            doc = self.db.transcripts.files.find_one({"metadata.audio_path": audio_path})
            if not doc:
                return None

            file_id = str(doc['_id'])
            text = self.get_transcript(file_id)
            return (file_id, text) if text else None

        except Exception as e:
            logger.error(f"Error retrieving transcript by audio {audio_path}: {e}")
            return None

    def get_transcript_metadata(self, file_id: str) -> Optional[Dict]:
        """Get metadata for a transcript"""
        try:
            doc = self.db.transcripts.files.find_one({"_id": ObjectId(file_id)})
            return doc.get('metadata') if doc else None
        except Exception as e:
            logger.error(f"Error getting transcript metadata {file_id}: {e}")
            return None

    def delete_transcript(self, file_id: str) -> bool:
        """Delete a transcript from GridFS"""
        try:
            self.transcript_bucket.delete(ObjectId(file_id))
            logger.info(f"Deleted transcript: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting transcript {file_id}: {e}")
            return False

    # Utility methods

    def _get_content_type(self, file_path: Path) -> str:
        """Determine content type from file extension"""
        extension = file_path.suffix.lower()
        content_types = {
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac',
            '.txt': 'text/plain',
        }
        return content_types.get(extension, 'application/octet-stream')

    def list_audio_files(self, limit: int = 100) -> list[Dict]:
        """List audio files with metadata"""
        try:
            cursor = self.db.audio_files.files.find().limit(limit)
            return [
                {
                    'id': str(doc['_id']),
                    'filename': doc['filename'],
                    'length': doc['length'],
                    'uploadDate': doc['uploadDate'],
                    'metadata': doc.get('metadata', {})
                }
                for doc in cursor
            ]
        except Exception as e:
            logger.error(f"Error listing audio files: {e}")
            return []

    def list_transcripts(self, limit: int = 100) -> list[Dict]:
        """List transcripts with metadata"""
        try:
            cursor = self.db.transcripts.files.find().limit(limit)
            return [
                {
                    'id': str(doc['_id']),
                    'filename': doc['filename'],
                    'length': doc['length'],
                    'uploadDate': doc['uploadDate'],
                    'metadata': doc.get('metadata', {})
                }
                for doc in cursor
            ]
        except Exception as e:
            logger.error(f"Error listing transcripts: {e}")
            return []

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics for GridFS buckets"""
        try:
            audio_stats = self.db.command("collstats", "audio_files.files")
            transcript_stats = self.db.command("collstats", "transcripts.files")

            return {
                'audio_files': {
                    'count': audio_stats.get('count', 0),
                    'size': audio_stats.get('size', 0),
                    'avg_size': audio_stats.get('avgObjSize', 0),
                },
                'transcripts': {
                    'count': transcript_stats.get('count', 0),
                    'size': transcript_stats.get('size', 0),
                    'avg_size': transcript_stats.get('avgObjSize', 0),
                }
            }
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}
