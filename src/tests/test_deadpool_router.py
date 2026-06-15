"""Integration tests for the deadpool router.

These mount the full app and patch the DynamoDBClient the router constructs, so
requests flow through the real routing, services, and response models.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from ..main import app

client = TestClient(app, raise_server_exceptions=False)
BASE = "/api/v1/deadpool"


class FakeDB:
    """Configurable in-memory DynamoDBClient stand-in for router tests."""

    def __init__(self, players=None, people=None, picks=None):
        self._players = players or []
        self._people = people or {}
        self._picks = picks or {}
        self.created_people = []
        self.created_picks = []

    async def get_players(self, year=None):
        return [dict(p) for p in self._players]

    async def get_player(self, player_id, year=None):
        pid = player_id.replace("PLAYER#", "")
        return next((dict(p) for p in self._players if p["id"] == pid), None)

    async def get_person(self, person_id):
        return self._people.get(person_id)

    async def get_people(self, status=None):
        people = list(self._people.values())
        if status == "deceased":
            people = [p for p in people if p.get("metadata", {}).get("DeathDate")]
        elif status == "alive":
            people = [p for p in people if not p.get("metadata", {}).get("DeathDate")]
        return people

    async def get_player_picks(self, player_id, year=None):
        return list(self._picks.get(player_id, []))

    async def batch_get_player_picks(self, player_ids, year=None):
        return {pid: list(self._picks.get(pid, [])) for pid in player_ids}

    async def batch_get_people(self, person_ids):
        return {pid: self._people[pid] for pid in person_ids if pid in self._people}

    async def update_person(self, person_id, updates):
        self.created_people.append((person_id, updates))
        return {"id": person_id, "name": updates.get("name"), "status": "active", "metadata": {}}

    async def update_player_pick(self, player_id, person_id, year=None):
        self.created_picks.append((player_id, person_id, year))
        return {"player_id": player_id, "person_id": person_id, "year": year,
                "timestamp": "2026-01-01T00:00:00"}


PLAYERS = [
    {"id": "P1", "name": "Player One", "draft_order": 1, "year": 2026},
    {"id": "P2", "name": "Player Two", "draft_order": 2, "year": 2026},
]
PEOPLE = {
    "alive1": {"id": "alive1", "name": "Alive One", "status": "active", "metadata": {"Age": 50}},
    "dead1": {"id": "dead1", "name": "Dead One", "status": "deceased",
              "metadata": {"Age": 80, "DeathDate": "2026-02-01"}},
}


def patch_db(fake):
    """Patch the DynamoDBClient constructor used throughout the router."""
    return patch("src.routers.deadpool.DynamoDBClient", return_value=fake)


class TestPlayers:
    def test_get_players(self):
        with patch_db(FakeDB(players=PLAYERS)):
            resp = client.get(f"{BASE}/players?year=2026")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_get_player_not_found(self):
        with patch_db(FakeDB(players=PLAYERS)):
            resp = client.get(f"{BASE}/players/nope?year=2026")
        assert resp.status_code == 404


class TestPeople:
    def test_get_people_paginated(self):
        with patch_db(FakeDB(people=PEOPLE)):
            resp = client.get(f"{BASE}/people?page=1&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1

    def test_get_people_invalid_status(self):
        with patch_db(FakeDB(people=PEOPLE)):
            resp = client.get(f"{BASE}/people?status=bogus")
        assert resp.status_code == 400

    def test_get_person_not_found(self):
        with patch_db(FakeDB(people=PEOPLE)):
            resp = client.get(f"{BASE}/people/missing")
        assert resp.status_code == 404


class TestLeaderboardAndDrafting:
    def test_leaderboard(self):
        picks = {"P1": [{"person_id": "dead1", "year": 2026, "timestamp": "2026-01-02T00:00:00"}],
                 "P2": [{"person_id": "alive1", "year": 2026, "timestamp": "2026-01-03T00:00:00"}]}
        with patch_db(FakeDB(players=PLAYERS, people=PEOPLE, picks=picks)):
            resp = client.get(f"{BASE}/leaderboard?year=2026")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # P1 picked someone who died in 2026 (50 + 100-80 = 70); P2 picked a living person.
        assert data[0]["player_name"] == "Player One"
        assert data[0]["score"] == 70

    def test_next_drafter(self):
        picks = {"P1": [{"person_id": "alive1", "year": 2026, "timestamp": "2026-01-02T00:00:00"}],
                 "P2": []}
        with patch_db(FakeDB(players=PLAYERS, people=PEOPLE, picks=picks)):
            resp = client.get(f"{BASE}/draft-next")
        assert resp.status_code == 200
        # P2 has no picks, so it drafts next.
        assert resp.json()["data"]["player_id"] == "P2"

    def test_picks_counts_counts_living_only(self):
        picks = {"P1": [{"person_id": "alive1", "year": 2026, "timestamp": "2026-01-02T00:00:00"},
                        {"person_id": "dead1", "year": 2026, "timestamp": "2026-01-03T00:00:00"}],
                 "P2": []}
        with patch_db(FakeDB(players=PLAYERS, people=PEOPLE, picks=picks)):
            resp = client.get(f"{BASE}/picks-counts?year=2026")
        assert resp.status_code == 200
        counts = {d["player_name"]: d["pick_count"] for d in resp.json()["data"]}
        assert counts == {"Player One": 1, "Player Two": 0}  # dead1 not counted

    def test_draft_new_person(self):
        fake = FakeDB(players=PLAYERS, people={}, picks={"P1": [], "P2": []})
        with patch_db(fake):
            resp = client.post(f"{BASE}/draft", json={"name": "Fresh Face", "player_id": "P1"})
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["is_new"] is True
        assert body["name"] == "Fresh Face"
        assert len(fake.created_people) == 1
        assert len(fake.created_picks) == 1

    def test_draft_rejects_duplicate(self):
        people = {"x": {"id": "x", "name": "Jane Doe", "status": "active", "metadata": {}}}
        picks = {"P1": [{"person_id": "x", "year": 2026, "timestamp": "2026-01-02T00:00:00"}],
                 "P2": []}
        with patch_db(FakeDB(players=PLAYERS, people=people, picks=picks)):
            resp = client.post(f"{BASE}/draft", json={"name": "Jane Doe", "player_id": "P2"})
        assert resp.status_code == 400
        assert "already been drafted" in resp.json()["detail"]

    def test_draft_unknown_player(self):
        with patch_db(FakeDB(players=PLAYERS, people={}, picks={})):
            resp = client.post(f"{BASE}/draft", json={"name": "Someone", "player_id": "ghost"})
        assert resp.status_code == 404
