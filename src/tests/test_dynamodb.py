"""Regression tests for DynamoDBClient bug fixes.

Covers two defects:
- update_draft_order had its `year`/`draft_order` parameters swapped relative
  to the router's positional call, writing draft records to the wrong keys.
- update_player returned get_players()[0] (whoever sorted first by draft order)
  instead of the player that was actually updated.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from ..utils.dynamodb import DynamoDBClient


def bare_client():
    """A client with no boto3 wiring, for testing pure transform/parse helpers."""
    return DynamoDBClient.__new__(DynamoDBClient)


def make_client():
    """Build a DynamoDBClient backed by a MagicMock table."""
    with patch("src.utils.dynamodb.boto3") as mock_boto3:
        table = MagicMock()
        resource = MagicMock()
        resource.Table.return_value = table
        mock_boto3.resource.return_value = resource
        client = DynamoDBClient()
    return client, table


async def test_update_draft_order_writes_correct_keys():
    """year -> partition key, draft_order -> sort key (not swapped)."""
    client, table = make_client()

    result = await client.update_draft_order("player-1", 2026, 5)

    item = table.put_item.call_args.kwargs["Item"]
    assert item["PK"] == "YEAR#2026"
    assert item["SK"] == "ORDER#5#PLAYER#player-1"
    assert result == {"player_id": "player-1", "draft_order": 5, "year": 2026}


async def test_update_player_returns_the_updated_player():
    """The updated player is returned, with its draft order resolved."""
    client, table = make_client()

    existing = {"PK": "PLAYER#p1", "SK": "DETAILS", "FirstName": "John", "LastName": "Doe"}
    table.get_item.return_value = {"Item": existing}
    table.query.return_value = {"Items": [{"SK": "ORDER#3#PLAYER#p1"}]}

    result = await client.update_player("p1", {"first_name": "Jane"})

    assert result["id"] == "p1"
    assert result["name"] == "Jane Doe"
    assert result["draft_order"] == 3


class TestTransformPerson:
    def test_alive_person_and_decimal_coercion(self):
        client = bare_client()
        person = client._transform_person({
            "PK": "PERSON#abc", "SK": "DETAILS", "Name": "Jane",
            "Age": Decimal("75"), "BirthDate": "1949-01-25",
        })
        assert person["id"] == "abc"
        assert person["name"] == "Jane"
        assert person["status"] == "active"
        assert person["metadata"]["Age"] == 75
        assert isinstance(person["metadata"]["Age"], int)

    def test_deceased_detected_by_death_date(self):
        client = bare_client()
        person = client._transform_person({
            "PK": "PERSON#xyz", "SK": "DETAILS", "name": "Bob",
            "DeathDate": "2025-01-01", "Age": Decimal("60"),
        })
        assert person["status"] == "deceased"
        assert person["name"] == "Bob"  # falls back to lowercase 'name'

    def test_malformed_item_returns_safe_placeholder(self):
        client = bare_client()
        person = client._transform_person({"PK": "PERSON#abc", "SK": "DETAILS"})  # no name
        assert person["status"] == "unknown"
        assert person["name"] == "Unknown Person"


class TestBatchGetPlayerPicks:
    async def test_prefers_person_id_attr_and_handles_hash_in_sk(self):
        client = bare_client()
        client.table_name = "Deadpool"
        client.table = MagicMock()
        client.table.query.return_value = {"Items": [
            # No PersonID attribute -> person_id rejoined from SK parts[2:].
            {"SK": "PICK#2025#weird#id#123", "Timestamp": "2025-01-01T00:00:00"},
            # PersonID attribute present -> used as the source of truth.
            {"SK": "PICK#2025#plain", "Timestamp": "2025-01-02T00:00:00", "PersonID": "canonical-id"},
        ]}
        result = await client.batch_get_player_picks(["P1"], 2025)
        person_ids = {p["person_id"] for p in result["P1"]}
        assert person_ids == {"weird#id#123", "canonical-id"}
        # Sorted by timestamp descending.
        assert result["P1"][0]["person_id"] == "canonical-id"


class TestUpdatePlayerPick:
    async def test_writes_pick_keys_and_person_id_attr(self):
        client, table = make_client()
        result = await client.update_player_pick("p1", "person-9", 2026)
        item = table.put_item.call_args.kwargs["Item"]
        assert item["PK"] == "PLAYER#p1"
        assert item["SK"] == "PICK#2026#person-9"
        assert item["PersonID"] == "person-9"
        assert item["Year"] == 2026
        assert result["person_id"] == "person-9"
        assert result["year"] == 2026
        assert "timestamp" in result


class TestGetPlayer:
    async def test_returns_none_when_no_draft_order_for_year(self):
        client, table = make_client()
        table.get_item.return_value = {"Item": {"PK": "PLAYER#p1", "SK": "DETAILS",
                                                "FirstName": "John", "LastName": "Doe"}}
        table.query.return_value = {"Items": []}  # no draft order this year
        assert await client.get_player("p1", 2025) is None

    async def test_resolves_draft_order_and_strips_prefix(self):
        client, table = make_client()
        table.get_item.return_value = {"Item": {"PK": "PLAYER#p1", "SK": "DETAILS",
                                                "FirstName": "John", "LastName": "Doe"}}
        table.query.return_value = {"Items": [{"SK": "ORDER#7#PLAYER#p1"}]}
        # Accepts an id that already carries the PLAYER# prefix.
        player = await client.get_player("PLAYER#p1", 2025)
        assert player["id"] == "p1"
        assert player["draft_order"] == 7
        assert player["name"] == "John Doe"
