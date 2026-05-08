class TutorError(Exception):
    """Base for all tutor AI errors."""


class IngestionError(TutorError):
    """Raised when doc parsing or chunking fails."""


class LLMError(TutorError):
    """Raised when an LLM call fails or returns unparseable output."""


class TTSError(TutorError):
    """Raised when audio rendering fails."""


class PlayerError(TutorError):
    """Raised when the interactive player encounters an unrecoverable state."""


class ConfigError(TutorError):
    """Raised when required config (API key, ffmpeg) is missing."""


class VideoError(TutorError):
    """Raised when any step of the video pipeline fails."""
