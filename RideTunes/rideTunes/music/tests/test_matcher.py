"""Tests for cross-service match scoring. Plain unittest, no Django, no network.

    cd RideTunes/rideTunes && python -m unittest music.tests.test_matcher -v

Each scenario is a failure mode the old matcher (views.py:1340-1357 --
`"{name} {artist}"`, search, `limit=1`, take items[0]) would have got wrong,
silently.
"""

import unittest

from music.resolvers.matcher import (
    AMBIGUITY_GAP,
    AUTO_THRESHOLD,
    LOW_THRESHOLD,
    MatchOutcome,
    classify,
    match,
    rank_candidates,
    score_candidate,
)
from music.resolvers.types import MatchMethod, SongIdentity


def song(title, artist, ms=200_000, isrc=None, explicit=None):
    return SongIdentity(
        title=title, artist=artist, duration_ms=ms, isrc=isrc, explicit=explicit
    )


STUDIO = song("Blinding Lights", "The Weeknd", 200_040, isrc="USUG11904206")


class ISRCShortCircuit(unittest.TestCase):
    def test_matching_isrc_is_exact_regardless_of_metadata(self):
        """Different title casing, artist punctuation and a 3s duration delta --
        the ISRC still makes it certain."""
        candidate = song("BLINDING LIGHTS", "Weeknd, The", 203_000, isrc="USUG11904206")
        s = score_candidate(STUDIO, candidate)
        self.assertEqual(s.method, MatchMethod.ISRC)
        self.assertEqual(s.score, 1.0)
        self.assertTrue(s.is_exact)

    def test_differing_isrc_falls_through_to_fuzzy(self):
        candidate = song("Blinding Lights", "The Weeknd", 200_040, isrc="GBXXX0000001")
        self.assertEqual(score_candidate(STUDIO, candidate).method, MatchMethod.FUZZY)

    def test_exact_hit_is_auto_even_with_a_close_runner_up(self):
        """Two catalogue entries sharing an ISRC are the same recording, so a
        close second is not evidence of ambiguity."""
        outcome, best, _ = match(
            STUDIO,
            [
                song("Blinding Lights", "The Weeknd", 200_040, isrc="USUG11904206"),
                song("Blinding Lights", "The Weeknd", 200_100),
            ],
        )
        self.assertEqual(outcome, MatchOutcome.AUTO)
        self.assertTrue(best.is_exact)


class FuzzyScoring(unittest.TestCase):
    def test_identical_metadata_scores_high(self):
        s = score_candidate(STUDIO, song("Blinding Lights", "The Weeknd", 200_040))
        self.assertGreaterEqual(s.score, AUTO_THRESHOLD)

    def test_promotional_noise_does_not_hurt(self):
        """The YouTube-source case: title carries junk the studio title lacks."""
        s = score_candidate(
            STUDIO, song("Blinding Lights (Official Video) [4K]", "TheWeekndVEVO", 200_040)
        )
        self.assertGreaterEqual(s.score, AUTO_THRESHOLD)

    def test_word_order_differences_tolerated(self):
        s = score_candidate(STUDIO, song("Blinding Lights", "Weeknd, The", 200_040))
        self.assertGreaterEqual(s.score, AUTO_THRESHOLD)

    def test_featured_artist_clause_does_not_break_a_match(self):
        s = score_candidate(
            song("Song", "Artist", 200_000), song("Song (feat. Drake)", "Artist", 200_000)
        )
        self.assertGreaterEqual(s.score, AUTO_THRESHOLD)

    def test_completely_different_song_scores_low(self):
        s = score_candidate(STUDIO, song("Bohemian Rhapsody", "Queen", 354_000))
        self.assertLess(s.score, LOW_THRESHOLD)


class VersionDiscrimination(unittest.TestCase):
    """The core value: a remix/live take must not be served for a studio request."""

    def test_remix_is_penalised(self):
        studio = score_candidate(STUDIO, song("Blinding Lights", "The Weeknd", 200_040))
        remix = score_candidate(
            STUDIO, song("Blinding Lights (Tiesto Remix)", "The Weeknd", 200_040)
        )
        self.assertGreater(studio.score, remix.score)
        self.assertGreater(remix.penalties, 0)

    def test_live_take_is_penalised(self):
        live = score_candidate(
            STUDIO, song("Blinding Lights (Live at Wembley)", "The Weeknd", 200_040)
        )
        self.assertGreater(live.penalties, 0)
        self.assertLess(live.score, AUTO_THRESHOLD)

    def test_studio_served_for_a_live_request_also_penalised(self):
        live_source = song("Blinding Lights (Live)", "The Weeknd", 215_000)
        s = score_candidate(live_source, song("Blinding Lights", "The Weeknd", 215_000))
        self.assertGreater(s.penalties, 0)

    def test_karaoke_never_auto_matches(self):
        outcome, _, _ = match(
            STUDIO, [song("Blinding Lights (Karaoke Version)", "Sing King", 200_040)]
        )
        self.assertIn(outcome, (MatchOutcome.NONE, MatchOutcome.LOW))


class DurationDiscrimination(unittest.TestCase):
    def test_large_delta_is_hard_capped_despite_perfect_text(self):
        """An extended mix has identical text. Duration is the only signal that
        catches it, so it must override text agreement."""
        s = score_candidate(STUDIO, song("Blinding Lights", "The Weeknd", 420_000))
        self.assertLessEqual(s.score, 0.50)
        self.assertLess(s.score, AUTO_THRESHOLD)

    def test_small_delta_tolerated(self):
        s = score_candidate(STUDIO, song("Blinding Lights", "The Weeknd", 201_200))
        self.assertGreaterEqual(s.score, AUTO_THRESHOLD)

    def test_unknown_duration_is_not_treated_as_bad(self):
        """YouTube candidates often lack duration. Missing != mismatched."""
        s = score_candidate(STUDIO, song("Blinding Lights", "The Weeknd", None))
        self.assertGreaterEqual(s.score, LOW_THRESHOLD)

    def test_unknown_duration_cannot_read_as_certain(self):
        s = score_candidate(STUDIO, song("Blinding Lights", "The Weeknd", None))
        self.assertLess(s.score, 1.0)


class Ranking(unittest.TestCase):
    def test_best_first(self):
        ranked = rank_candidates(
            STUDIO,
            [
                song("Blinding Lights (Remix)", "The Weeknd", 200_040),
                song("Blinding Lights", "The Weeknd", 200_040),
                song("Something Else", "Another Band", 300_000),
            ],
        )
        self.assertEqual(ranked[0].candidate.title, "Blinding Lights")
        self.assertEqual([round(s.score, 4) for s in ranked],
                         sorted((round(s.score, 4) for s in ranked), reverse=True))

    def test_close_results_are_flagged_ambiguous(self):
        outcome, _, alternates = match(
            song("Song", "Artist", 200_000),
            [
                song("Song", "Artist", 200_000),
                song("Song", "Artist", 200_050),   # near-identical duplicate
            ],
        )
        self.assertEqual(outcome, MatchOutcome.AMBIGUOUS)
        self.assertTrue(alternates)

    def test_empty_candidate_list(self):
        outcome, best, alternates = match(STUDIO, [])
        self.assertEqual(outcome, MatchOutcome.NONE)
        self.assertIsNone(best)
        self.assertEqual(alternates, [])

    def test_at_most_three_alternates(self):
        _, _, alternates = match(STUDIO, [song(f"Take {i}", "The Weeknd") for i in range(9)])
        self.assertLessEqual(len(alternates), 3)


class Thresholds(unittest.TestCase):
    def test_ordering_is_coherent(self):
        self.assertLess(LOW_THRESHOLD, AUTO_THRESHOLD)
        self.assertGreater(AMBIGUITY_GAP, 0)

    def test_outcome_boundaries(self):
        for score, expected in [
            (0.95, MatchOutcome.AUTO),
            (0.60, MatchOutcome.LOW),
            (0.30, MatchOutcome.NONE),
        ]:
            with self.subTest(score=score):
                fake = [_FakeScored(score)]
                self.assertEqual(classify(fake)[0], expected)


class _FakeScored:
    """Minimal stand-in so threshold boundaries can be probed directly."""

    def __init__(self, score):
        self.score = score
        self.candidate = None
        self.method = MatchMethod.FUZZY

    @property
    def is_exact(self):
        return False


if __name__ == "__main__":
    unittest.main(verbosity=2)
