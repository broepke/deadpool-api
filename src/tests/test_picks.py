"""Tests for PicksService — leaderboard scoring, pick counts, next-drafter
rotation, and the picks listing."""
import pytest

from ..services.picks import PicksService


class FakeDB:
    """In-memory stand-in for DynamoDBClient covering the methods PicksService uses."""

    def __init__(self, players, picks_by_player, people):
        self._players = players
        self._picks = picks_by_player
        self._people = people

    async def get_players(self, year=None):
        return [dict(p) for p in self._players]

    async def get_player_picks(self, player_id, year=None):
        return list(self._picks.get(player_id, []))

    async def batch_get_player_picks(self, player_ids, year=None):
        return {pid: list(self._picks.get(pid, [])) for pid in player_ids}

    async def batch_get_people(self, person_ids):
        return {pid: self._people[pid] for pid in person_ids if pid in self._people}

    async def get_person(self, person_id):
        return self._people.get(person_id)

    async def get_draft_order(self, year=None):
        return [{"year": 2025}]


# Canonical dataset (expected values verified against the live services).
PEOPLE = {
    "alive1":    {"id": "alive1", "name": "Alive One", "metadata": {"Age": 50}},
    "alive2":    {"id": "alive2", "name": "Alive Two", "metadata": {"Age": 60}},
    "dead2025a": {"id": "dead2025a", "name": "Dead A", "metadata": {"Age": 80, "DeathDate": "2025-03-10"}},
    "dead2025b": {"id": "dead2025b", "name": "Dead B", "metadata": {"Age": 90, "DeathDate": "2025-06-01"}},
    "dead2024":  {"id": "dead2024", "name": "Dead Old", "metadata": {"Age": 70, "DeathDate": "2024-05-05"}},
}
PLAYERS = [
    {"id": "P1", "name": "Player One", "draft_order": 1, "year": 2025},
    {"id": "P2", "name": "Player Two", "draft_order": 2, "year": 2025},
    {"id": "P3", "name": "Player Three", "draft_order": 3, "year": 2025},
]
PICKS = {
    "P1": [{"person_id": "dead2025a", "year": 2025, "timestamp": "2025-01-02T10:00:00"},
           {"person_id": "alive1", "year": 2025, "timestamp": "2025-01-05T10:00:00"}],
    "P2": [{"person_id": "dead2025b", "year": 2025, "timestamp": "2025-01-03T10:00:00"},
           {"person_id": "dead2024", "year": 2025, "timestamp": "2025-01-04T10:00:00"},
           {"person_id": "alive2", "year": 2025, "timestamp": "2025-01-06T10:00:00"}],
    "P3": [],
}


@pytest.fixture
def service():
    return PicksService(FakeDB(PLAYERS, PICKS, PEOPLE))


class TestLeaderboard:
    async def test_scores_only_deaths_in_target_year(self, service):
        result = await service.get_leaderboard(2025)
        scores = {e.player_name: e.score for e in result["data"]}
        # P1: dead2025a (50 + 100-80 = 70). P2: dead2025b (50 + 100-90 = 60);
        # dead2024 excluded (died 2024). P3: no picks.
        assert scores == {"Player One": 70, "Player Two": 60, "Player Three": 0}

    async def test_sorted_by_score_descending(self, service):
        result = await service.get_leaderboard(2025)
        scores = [e.score for e in result["data"]]
        assert scores == sorted(scores, reverse=True)

    async def test_empty_when_no_players(self):
        svc = PicksService(FakeDB([], {}, {}))
        result = await svc.get_leaderboard(2025)
        assert result["data"] == []


class TestPicksCounts:
    async def test_counts_only_living_picks(self, service):
        result = await service.get_picks_counts(2025)
        counts = {e.player_name: e.pick_count for e in result["data"]}
        # Only alive picks count: P1 -> alive1 (1), P2 -> alive2 (1), P3 -> 0.
        assert counts == {"Player One": 1, "Player Two": 1, "Player Three": 0}

    async def test_sorted_by_draft_order(self, service):
        result = await service.get_picks_counts(2025)
        orders = [e.draft_order for e in result["data"]]
        assert orders == [1, 2, 3]


class TestNextDrafter:
    async def test_picks_fewest_total_picks_then_lowest_draft_order(self, service):
        result = await service.get_next_drafter()
        # P3 has 0 picks so drafts next despite the highest draft order.
        assert result["data"]["player_id"] == "P3"
        assert result["data"]["current_pick_count"] == 0

    async def test_excludes_players_at_20_active_picks(self):
        people = {f"a{i}": {"id": f"a{i}", "name": f"A{i}", "metadata": {"Age": 50}} for i in range(20)}
        players = [
            {"id": "FULL", "name": "Full", "draft_order": 1, "year": 2025},
            {"id": "OK", "name": "Ok", "draft_order": 2, "year": 2025},
        ]
        picks = {
            "FULL": [{"person_id": f"a{i}", "year": 2025, "timestamp": f"2025-01-{i + 1:02d}T00:00:00"}
                     for i in range(20)],
            "OK": [{"person_id": "a0", "year": 2025, "timestamp": "2025-02-01T00:00:00"}],
        }
        svc = PicksService(FakeDB(players, picks, people))
        result = await svc.get_next_drafter()
        # FULL has 20 active picks and is excluded even though its draft order is lower.
        assert result["data"]["player_id"] == "OK"

    async def test_no_eligible_players(self):
        svc = PicksService(FakeDB([], {}, {}))
        result = await svc.get_next_drafter()
        assert result["data"]["player_id"] == ""


class TestGetPicks:
    async def test_includes_players_without_picks(self, service):
        result = await service.get_picks(2025, page=1, page_size=50)
        # 5 real picks + 1 placeholder row for P3 (no picks).
        assert result["total"] == 6
        no_pick_rows = [d for d in result["data"] if d.pick_person_id is None]
        assert len(no_pick_rows) == 1
        assert no_pick_rows[0].player_name == "Player Three"

    async def test_pagination_limits_rows(self, service):
        result = await service.get_picks(2025, page=1, page_size=2)
        assert len(result["data"]) == 2
        assert result["total"] == 6
        assert result["total_pages"] == 3

    async def test_limit_overrides_pagination(self, service):
        result = await service.get_picks(2025, limit=3)
        assert len(result["data"]) == 3
        assert result["page"] == 1
        assert result["total_pages"] == 1


class TestGetPicksByPerson:
    async def test_finds_players_who_picked_person(self, service):
        result = await service.get_picks_by_person("dead2025a", year=2025)
        assert result["total"] == 1
        assert result["data"][0].player_name == "Player One"
        assert result["data"][0].pick_person_name == "Dead A"

    async def test_unknown_person_returns_not_found(self, service):
        result = await service.get_picks_by_person("does-not-exist", year=2025)
        assert result["total"] == 0
        assert result["data"] == []
