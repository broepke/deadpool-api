"""Tests for the API router endpoints (search).

Mounts the full FastAPI app so the router prefix (/api/v1/deadpool) is applied,
and patches the DynamoDB client the search endpoint constructs.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from ..main import app

client = TestClient(app, raise_server_exceptions=False)

BASE = "/api/v1/deadpool"

# The search service only searches people; players search is not implemented.
MOCK_PEOPLE = [
    {"id": "person1", "name": "John Smith", "status": "alive", "metadata": {}},
    {"id": "person2", "name": "John Smith Jr.", "status": "alive", "metadata": {}},
    {"id": "person3", "name": "Jane Doe", "status": "deceased",
     "metadata": {"DeathDate": "2024-01-01"}},
]


@pytest.fixture
def mock_db():
    """Patch the DynamoDBClient used by the deadpool router."""
    with patch("src.routers.deadpool.DynamoDBClient") as mock:
        db = AsyncMock()
        db.get_people.return_value = MOCK_PEOPLE
        mock.return_value = db
        yield db


def test_search_people_exact(mock_db):
    """Exact mode matches the full name and close variants above threshold."""
    response = client.get(f"{BASE}/search?q=John+Smith&type=people&mode=exact")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Successfully retrieved search results"
    # "John Smith" (1.0) and "John Smith Jr." (0.87) both clear the 0.85 threshold.
    assert data["metadata"]["total"] == 2
    assert data["data"][0]["attributes"]["name"] == "John Smith"
    assert data["data"][0]["score"] == 1.0


def test_search_people_fuzzy(mock_db):
    """Fuzzy mode tolerates typos and matches on name parts."""
    response = client.get(f"{BASE}/search?q=John+Smth&type=people&mode=fuzzy")
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["total"] == 2  # John Smith and John Smith Jr.
    # Results are sorted by score descending.
    assert data["data"][0]["score"] >= data["data"][1]["score"]


def test_search_pagination(mock_db):
    """limit/offset paginate the match list while reporting the full total."""
    response = client.get(f"{BASE}/search?q=Smith&type=people&limit=1&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["metadata"]["limit"] == 1
    assert data["metadata"]["offset"] == 1
    assert data["metadata"]["total"] == 2


def test_search_invalid_type(mock_db):
    response = client.get(f"{BASE}/search?q=test&type=invalid")
    assert response.status_code == 400
    assert "Entity type must be either" in response.json()["detail"]


def test_search_invalid_mode(mock_db):
    response = client.get(f"{BASE}/search?q=test&mode=invalid")
    assert response.status_code == 400
    assert "Search mode must be either" in response.json()["detail"]


def test_search_missing_query(mock_db):
    """The query parameter is required."""
    response = client.get(f"{BASE}/search?type=people")
    assert response.status_code == 422


def test_search_invalid_limit(mock_db):
    assert client.get(f"{BASE}/search?q=test&limit=0").status_code == 422
    assert client.get(f"{BASE}/search?q=test&limit=101").status_code == 422


def test_search_invalid_offset(mock_db):
    assert client.get(f"{BASE}/search?q=test&offset=-1").status_code == 422


def test_search_db_error(mock_db):
    """A DB failure surfaces as a 500 with a friendly detail message."""
    mock_db.get_people.side_effect = Exception("Database error")
    response = client.get(f"{BASE}/search?q=test")
    assert response.status_code == 500
    assert "error occurred while performing the search" in response.json()["detail"]
