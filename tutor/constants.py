# Audio
WPM = 130
SILENCE_BREATH_MS = 150
SILENCE_TURN_MS = 500
SILENCE_UNIT_MS = 1200
SILENCE_SESSION_MS = 800
TTS_SEMAPHORE_LIMIT = 8

# Voices
VOICE_TUTOR = "en-US-GuyNeural"
VOICE_STUDENT = "en-US-JennyNeural"
VOICE_COTUTOR = "en-US-SaraNeural"
RATE_TUTOR = "+0%"
RATE_STUDENT = "+5%"
RATE_COTUTOR = "+0%"

# Ingestion
STRATEGY_A_TOKEN_LIMIT = 6_000
STRATEGY_B_TOKEN_LIMIT = 60_000
MAX_CHUNK_TOKENS = 4_000
MIN_CHUNK_TOKENS = 50
SUMMARY_CACHE_DIR = ".tutor_cache"

# Complexity
WORDS_PER_COMPLEXITY: dict[int, int] = {1: 200, 2: 380, 3: 580}
OVERHEAD_WORDS = 200  # intro + transitions + outro

# Player
PLAYER_POLL_HZ = 10

# Versioning
PROMPT_VERSION = "v1"
MAX_UNITS = 8
MIN_UNITS = 3
DEFAULT_DURATION_MIN = 20
DEFAULT_DIFFICULTY = "beginner"
DEFAULT_FORMAT = "tutor-student"
DEFAULT_SUBJECT = "java"

# Code-to-speech substitutions (pattern, replacement)
CODE_SUBSTITUTIONS = [
    (r"List<String>", "a List of Strings"),
    (r"HashMap<(\w+),\s*(\w+)>", r"a HashMap from \1 to \2"),
    (r"!=", "not equal to"),
    (r"(?<![=!<>])==(?![=])", "double equals"),
    (r"\.equals\(", "dot equals("),
    (r"@(\w+)", r"\1 annotation"),
    (r"(\w+)\[\]", r"\1 array"),
    (r"NullPointerException", "Null Pointer Exception"),
    (r"StackOverflowError", "Stack Overflow Error"),
    (r"IllegalArgumentException", "Illegal Argument Exception"),
]
