"""Conservative, versioned semantic identity and safe lexical normalization."""

from __future__ import annotations

import hashlib
import json
import unicodedata

from .models import SemanticRequest


NORMALIZATION_VERSION = "nfc-casefold-space-v1"


def fingerprint(request: SemanticRequest) -> str:
    """Hash all typed result-affecting fields; no transport header or secret exists here."""
    encoded = json.dumps(
        request.descriptor(), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"semantic-request-v{request.schema_version}:{digest}"


def normalize_phrase_v1(phrase: str) -> str:
    """Only Unicode, case, and whitespace; preserve ё, word order, numbers, operators."""
    if not isinstance(phrase, str) or not phrase.strip():
        raise ValueError("phrase must be nonempty text")
    normalized = unicodedata.normalize("NFC", phrase).casefold()
    return " ".join(normalized.split())
