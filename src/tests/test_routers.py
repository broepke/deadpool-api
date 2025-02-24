"""
Tests for the API router endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from ..routers.deadpool import router
from ..utils.dynamodb import DynamoDBClient
from unittest.mock import AsyncMock, patch

# Create test client
client = TestClient(router)

# Mock data for testing
MOCK_PEOPLE = [
    {
        "id": "person1",
        "name": "John Smith",
        "status": "alive",
        "metadata": {}
    },
    {
        "id": "person2",
        "name": "John Smith Jr.",
        "status": "alive",
        "metadata": {}
    },
    {
        "id": "person3",
        "name": "Jane Doe",
        "status": "deceased",
        "metadata": {"DeathDate": "2024-01-01"}
    }
]

MOCK_PLAYERS = [
    {
        "id": "player1",
        "name": "Player One",
        "draft_order": 1,
        "year": 2025
    },
    {
        "id": "player2",
        "name": "Player Two",
        "draft_order": 2,
        "year": 2025
    }
]

@pytest.fixture
def mock_db():
    """Create a mock DynamoDB client."""
    with patch("src.routers.deadpool.DynamoDBClient") as mock:
        db = AsyncMock()
        db.get_people.return_value = MOCK_PEOPLE
        db.get_players.return_value = MOCK_PLAYERS
        mock.return_value = db
        yield db

@pytest.mark.asyncio
async def test_search_people_exact(mock_db):
    """Test exact search for people."""
    response = client.get("/search?q=John+Smith&type=people&mode=exact")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Successfully retrieved search results"
    assert len(data["data"]) == 1
    assert data["data"][0]["attributes"]["name"] == "John Smith"
    assert data["metadata"]["total"] == 1

@pytest.mark.asyncio
async def test_search_people_fuzzy(mock_db):
    """Test fuzzy search for people."""
    response = client.get("/search?q=John+Smth&type=people&mode=fuzzy")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2  # Should match both John Smith and John Smith Jr.
    assert data["metadata"]["total"] == 2
    # Results should be sorted by score
    assert data["data"][0]["score"] >= data["data"][1]["score"]

@pytest.mark.asyncio
async def test_search_players(mock_db):
    """Test searching players."""
    response = client.get("/search?q=Player&type=players")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert all(result["type"] == "players" for result in data["data"])

@pytest.mark.asyncio
async def test_search_pagination(mock_db):
    """Test search pagination."""
    response = client.get("/search?q=Smith&type=people&limit=1&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["metadata"]["limit"] == 1
    assert data["metadata"]["offset"] == 1
    assert data["metadata"]["total"] > 1

@pytest.mark.asyncio
async def test_search_invalid_type(mock_db):
    """Test search with invalid entity type."""
    response = client.get("/search?q=test&type=invalid")
    assert response.status_code == 400
    assert "Entity type must be either" in response.json()["detail"]

@pytest.mark.asyncio
async def test_search_invalid_mode(mock_db):
    """Test search with invalid mode."""
    response = client.get("/search?q=test&mode=invalid")
    assert response.status_code == 400
    assert "Search mode must be either" in response.json()["detail"]

@pytest.mark.asyncio
async def test_search_empty_query(mock_db):
    """Test search with empty query."""
    response = client.get("/search?q=&type=people")
    assert response.status_code == 422  # FastAPI validation error

@pytest.mark.asyncio
async def test_search_invalid_limit(mock_db):
    """Test search with invalid limit."""
    response = client.get("/search?q=test&limit=0")
    assert response.status_code == 422  # FastAPI validation error
    response = client.get("/search?q=test&limit=101")
    assert response.status_code == 422  # FastAPI validation error

@pytest.mark.asyncio
async def test_search_invalid_offset(mock_db):
    """Test search with invalid offset."""
    response = client.get("/search?q=test&offset=-1")
    assert response.status_code == 422  # FastAPI validation error

@pytest.mark.asyncio
async def test_search_db_error(mock_db):
    """Test search when database raises an error."""
    mock_db.get_people.side_effect = Exception("Database error")
    response = client.get("/search?q=test")
    assert response.status_code == 500
    assert "error occurred while performing the search" in response.json()["detail"]