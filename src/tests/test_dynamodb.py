"""Regression tests for DynamoDBClient bug fixes.

Covers two defects:
- update_draft_order had its `year`/`draft_order` parameters swapped relative
  to the router's positional call, writing draft records to the wrong keys.
- update_player returned get_players()[0] (whoever sorted first by draft order)
  instead of the player that was actually updated.
"""
from unittest.mock import MagicMock, patch

from ..utils.dynamodb import DynamoDBClient


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
