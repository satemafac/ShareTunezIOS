"""Scoring a candidate track against a source song. Pure — no network.

The matching this replaces (views.py:1340-1357, tasks.py:22-39) was: build
`"{name} {artist}"`, search with `limit=1`, take `items[0]`. No duration check,
no artist verification, no confidence signal, and — because unmatched tracks
were simply skipped by an `if items:` guard — silent wrong results and silently
shifted playlist ordering.

Here, ISRC short-circuits everything (it is an exact key). Fuzzy matching is the
fallback, and it returns a *confidence* so the client can decide between showing
nothing, a quiet "not the right version?" affordance, or an expanded picker.

Weights and thresholds are tuned against the fixture harness, not by intuition.
Change them only with harness numbers in hand.
"""

from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz

from .normalize import extract_version_tags, normalize_text
from .types import MatchMethod

# --- Weights (must sum to 1.0) --------------------------------------------
W_TITLE = 0.45
W_ARTIST = 0.30
W_DURATION = 0.25

#: Weights when duration is unavailable on either side, renormalised.
W_TITLE_NO_DUR = 0.60
W_ARTIST_NO_DUR = 0.40

#: Duration delta at which the duration sub-score reaches zero.
DURATION_TOLERANCE_MS = 5_000
#: Beyond this, cap the whole score — duration is the strongest discriminator
#: between a studio cut and a live/extended take, and it overrides text agreement.
DURATION_HARD_LIMIT_MS = 7_000
DURATION_HARD_CAP = 0.50

#: Candidate carries a version tag the source lacks (the common failure:
#: searching "Song Artist" and getting a remix).
PENALTY_EXTRA_TAG = 0.35
#: Source carries a tag the candidate lacks — also wrong, but less common.
PENALTY_MISSING_TAG = 0.20
PENALTY_EXPLICIT_MISMATCH = 0.05

#: Confidence unavailable duration costs, so a text-only match can't read as certain.
NO_DURATION_CEILING = 0.90

# --- Thresholds -----------------------------------------------------------
AUTO_THRESHOLD = 0.72
LOW_THRESHOLD = 0.55
#: Minimum lead over the runner-up before a top result is treated as decisive.
AMBIGUITY_GAP = 0.06


class MatchOutcome(str, Enum):
    """What the client should do with the result."""

    #: Deliver silently. Quiet swap affordance only.
    AUTO = "auto"
    #: Deliver the best, but show alternates — the top two are too close.
    AMBIGUOUS = "ambiguous"
    #: Deliver the best with alternates expanded by default.
    LOW = "low"
    #: Don't auto-pick. Show a picker.
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Scored:
    """A candidate with its score and the sub-scores that produced it.

    The breakdown is kept because tuning against the fixture harness is
    impossible if you can only see the total.
    """

    candidate: object
    score: float
    title_sim: float
    artist_sim: float
    duration_score: float
    penalties: float
    method: MatchMethod

    @property
    def is_exact(self):
        return self.method in (MatchMethod.ORIGIN, MatchMethod.ISRC)


def _similarity(a, b):
    """0.0–1.0 token-set similarity over normalised text.

    `token_set_ratio` because word order varies between services
    ("Weeknd, The" vs "The Weeknd") and one side often carries extra tokens.
    """
    a_n, b_n = normalize_text(a), normalize_text(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 1.0
    return fuzz.token_set_ratio(a_n, b_n) / 100.0


def _duration_score(source_ms, candidate_ms):
    """1.0 at identical, decaying to 0.0 at DURATION_TOLERANCE_MS.

    Returns None when either side is unknown, so the caller renormalises rather
    than treating "unknown" as "bad".
    """
    if not source_ms or not candidate_ms:
        return None
    delta = abs(source_ms - candidate_ms)
    if delta >= DURATION_TOLERANCE_MS:
        return 0.0
    return 1.0 - (delta / DURATION_TOLERANCE_MS)


def _tag_penalty(source_text, candidate_text):
    """Penalty for version-tag disagreement between source and candidate."""
    src = extract_version_tags(source_text)
    cand = extract_version_tags(candidate_text)
    if src == cand:
        return 0.0
    penalty = 0.0
    if cand - src:
        penalty += PENALTY_EXTRA_TAG
    if src - cand:
        penalty += PENALTY_MISSING_TAG
    return min(penalty, PENALTY_EXTRA_TAG + PENALTY_MISSING_TAG)


def score_candidate(source, candidate):
    """Score one candidate `SongIdentity` against the source `SongIdentity`.

    ISRC equality short-circuits to an exact match. Otherwise: weighted title,
    artist and duration similarity, minus version-tag and explicit penalties.
    """
    if source.isrc and candidate.isrc and source.isrc == candidate.isrc:
        return Scored(candidate, 1.0, 1.0, 1.0, 1.0, 0.0, MatchMethod.ISRC)

    title_sim = _similarity(source.title, candidate.title)
    artist_sim = _similarity(source.artist, candidate.artist)
    dur = _duration_score(source.duration_ms, candidate.duration_ms)

    if dur is None:
        base = W_TITLE_NO_DUR * title_sim + W_ARTIST_NO_DUR * artist_sim
        base = min(base, NO_DURATION_CEILING)
        dur_component = 0.0
    else:
        base = W_TITLE * title_sim + W_ARTIST * artist_sim + W_DURATION * dur
        dur_component = dur

    penalties = _tag_penalty(source.title, candidate.title)
    if (
        source.explicit is not None
        and candidate.explicit is not None
        and source.explicit != candidate.explicit
    ):
        penalties += PENALTY_EXPLICIT_MISMATCH

    score = max(0.0, base - penalties)

    # Duration disagreement this large means it is a different recording,
    # however well the text agrees.
    if (
        source.duration_ms
        and candidate.duration_ms
        and abs(source.duration_ms - candidate.duration_ms) > DURATION_HARD_LIMIT_MS
    ):
        score = min(score, DURATION_HARD_CAP)

    return Scored(
        candidate=candidate,
        score=round(score, 4),
        title_sim=round(title_sim, 4),
        artist_sim=round(artist_sim, 4),
        duration_score=round(dur_component, 4),
        penalties=round(penalties, 4),
        method=MatchMethod.FUZZY,
    )


def rank_candidates(source, candidates):
    """Score and sort candidates, best first. Stable for equal scores."""
    return sorted(
        (score_candidate(source, c) for c in candidates),
        key=lambda s: s.score,
        reverse=True,
    )


def classify(ranked):
    """`(MatchOutcome, best_or_None, alternates)` for a ranked list.

    An exact ISRC hit is always AUTO regardless of the runner-up — two catalogue
    entries sharing an ISRC are the same recording, so a close second is not
    evidence of ambiguity.
    """
    if not ranked:
        return MatchOutcome.NONE, None, []

    best = ranked[0]
    alternates = ranked[1:4]

    if best.is_exact:
        return MatchOutcome.AUTO, best, alternates
    if best.score < LOW_THRESHOLD:
        return MatchOutcome.NONE, best, alternates
    if best.score < AUTO_THRESHOLD:
        return MatchOutcome.LOW, best, alternates

    gap = best.score - ranked[1].score if len(ranked) > 1 else 1.0
    if gap < AMBIGUITY_GAP:
        return MatchOutcome.AMBIGUOUS, best, alternates
    return MatchOutcome.AUTO, best, alternates


def match(source, candidates):
    """Convenience wrapper: rank then classify."""
    return classify(rank_candidates(source, candidates))
