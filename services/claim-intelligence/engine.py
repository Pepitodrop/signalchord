from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClusteredClaim:
    cluster_id: str
    normalized_proposition: str
    stance: str


def normalize_claim(proposition: str) -> str:
    value = proposition.casefold()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def cluster_claim(proposition: str) -> ClusteredClaim:
    normalized = normalize_claim(proposition)
    cluster_id = f"claim-cluster:{hashlib.sha256(normalized.encode()).hexdigest()[:24]}"
    negative_tokens = {"denied", "not", "never", "no"}
    stance = "negative" if negative_tokens.intersection(normalized.split()) else "positive"
    return ClusteredClaim(cluster_id=cluster_id, normalized_proposition=normalized, stance=stance)
