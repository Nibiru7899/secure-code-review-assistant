"""Small presentation helpers; never change stored engineering evidence."""
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

LOCAL_TIME = timezone(timedelta(hours=5, minutes=30), "IST")
OUTCOMES = {"CANDIDATES": "Candidates need review", "NO_SUPPORTED_FINDING": "No supported finding",
            "INSUFFICIENT_EVIDENCE": "Not enough evidence", "FAILED": "Analysis failed",
            "ANSWERED": "Cited explanation", "RUNNING": "Review in progress",
            "COMPLETED": "Review completed", "INTERRUPTED": "Review interrupted"}
SUPPORT = {"STRONG": "Source, analyzer and rule support", "SUPPORTED": "Source with rule or analyzer support",
           "AI-ONLY CANDIDATE": "Source-backed AI candidate"}


def local_time(value):
    if not value:
        return "Not recorded"
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timestamp.replace(tzinfo=timestamp.tzinfo or timezone.utc).astimezone(LOCAL_TIME).strftime("%d %b %Y · %H:%M IST")
    except ValueError:
        return "Time unavailable"


def diagnostic_text(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Use a UTF-8 text file. The selected file cannot be decoded.") from exc
    if not value.strip():
        raise ValueError("Paste a diagnostic log or select a text file before interpreting it.")
    if len(value) > 6000:
        raise ValueError("This evidence exceeds 6,000 characters. Select a smaller relevant excerpt; nothing was truncated.")
    if value.lstrip().startswith("<"):
        try:
            ElementTree.fromstring(value)
        except ElementTree.ParseError as exc:
            raise ValueError("The XML report is malformed. Correct it or import a plain-text excerpt.") from exc
    return value
