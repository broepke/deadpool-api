from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
from ..models.deadpool import (
    PlayerResponse, PersonResponse,
    PlayerUpdate, PersonUpdate, SinglePlayerResponse,
    SinglePersonResponse, RouteInfo, RoutesResponse,
    DraftOrder, DraftOrderListResponse, PlayerPickResponse,
    PlayerPickUpdate
)
from ..utils.dynamodb import DynamoDBClient

router = APIRouter(
    prefix="/api/v1/deadpool",
    tags=["deadpool"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=RoutesResponse)
async def get_routes():
    """
    Get all available API routes.
    """
    routes = []
    for route in router.routes:
        # Skip the root endpoint itself to avoid recursion
        if route.path != "/api/v1/deadpool/":
            routes.append({
                "path": f"/api/v1/deadpool{route.path}",
                "name": route.name
            })
    return {
        "message": "Successfully retrieved available routes",
        "routes": routes
    }

@router.get("/players", response_model=PlayerResponse)
async def get_players(year: Optional[int] = Query(None, description="Filter players by year")):
    """
    Get current players for a given year, sorted by draft order.
    Players are considered current if they have a draft order > 0.
    """
    db = DynamoDBClient()
    players = await db.get_players(year)
    return {
        "message": "Successfully retrieved players",
        "data": players
    }

@router.get("/players/{player_id}", response_model=SinglePlayerResponse)
async def get_player(
    player_id: str = Path(..., description="The ID of the player to get"),
    year: Optional[int] = Query(None, description="The year to get the player's draft order for")
):
    """
    Get a specific player's information.
    """
    db = DynamoDBClient()
    player = await db.get_player(player_id, year)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {
        "message": "Successfully retrieved player",
        "data": player
    }

@router.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: str = Path(..., description="The ID of the player to update"),
    updates: PlayerUpdate = None
):
    """
    Update a player's information.
    """
    db = DynamoDBClient()
    updated_player = await db.update_player(player_id, updates.dict(exclude_unset=True))
    return {
        "message": "Successfully updated player",
        "data": [updated_player]  # Wrap in list to match response model
    }

@router.get("/people", response_model=PersonResponse)
async def get_people():
    """
    Get a list of all people in the deadpool.
    """
    db = DynamoDBClient()
    people = await db.get_people()
    return {
        "message": "Successfully retrieved people",
        "data": people
    }

@router.get("/people/{person_id}", response_model=SinglePersonResponse)
async def get_person(
    person_id: str = Path(..., description="The ID of the person to get")
):
    """
    Get a specific person's information.
    """
    db = DynamoDBClient()
    person = await db.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return {
        "message": "Successfully retrieved person",
        "data": person
    }

@router.put("/people/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: str = Path(..., description="The ID of the person to update"),
    updates: PersonUpdate = None
):
    """
    Update a person's information.
    """
    db = DynamoDBClient()
    updated_person = await db.update_person(person_id, updates.dict(exclude_unset=True))
    return {
        "message": "Successfully updated person",
        "data": [updated_person]  # Wrap in list to match response model
    }

@router.get("/draft-order", response_model=DraftOrderListResponse)
async def get_draft_order(
    year: Optional[int] = Query(None, description="Filter draft orders by year"),
    player_id: Optional[str] = Query(None, description="Filter draft orders by player ID")
):
    """
    Get draft order records, optionally filtered by year and/or player.
    """
    db = DynamoDBClient()
    draft_orders = await db.get_draft_order(year, player_id)
    return {
        "message": "Successfully retrieved draft orders",
        "data": draft_orders
    }

@router.put("/player-picks/{player_id}", response_model=PlayerPickResponse)
async def update_player_pick(
    player_id: str = Path(..., description="The ID of the player to update picks for"),
    updates: PlayerPickUpdate = None
):
    """
    Update or create a pick for a specific player.
    """
    db = DynamoDBClient()
    updated_pick = await db.update_player_pick(player_id, updates.dict())
    return {
        "message": "Successfully updated player pick",
        "data": [updated_pick]  # Wrap in list to match response model
    }

@router.get("/player-picks/{player_id}", response_model=PlayerPickResponse)
async def get_player_picks(
    player_id: str = Path(..., description="The ID of the player to get picks for"),
    year: Optional[int] = Query(None, description="Filter picks by year")
):
    """
    Get all picks for a specific player, optionally filtered by year.
    """
    db = DynamoDBClient()
    picks = await db.get_player_picks(player_id, year)
    return {
        "message": "Successfully retrieved player picks",
        "data": picks
    }

@router.put("/draft-order/{player_id}", response_model=DraftOrderListResponse)
async def update_draft_order(
    player_id: str = Path(..., description="The ID of the player to update"),
    year: int = Query(..., description="The year for the draft order"),
    draft_order: int = Query(..., description="The new draft order position")
):
    """
    Update a player's draft order for a specific year.
    """
    db = DynamoDBClient()
    updated_order = await db.update_draft_order(player_id, year, draft_order)
    return {
        "message": "Successfully updated draft order",
        "data": [updated_order]  # Wrap in list to match response model
    }
