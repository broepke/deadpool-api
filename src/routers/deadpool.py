from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
import uuid
from datetime import datetime
from ..models.deadpool import (
    PlayerResponse,
    PersonResponse,
    PlayerUpdate,
    PersonUpdate,
    SinglePlayerResponse,
    SinglePersonResponse,
    RoutesResponse,
    DraftOrderListResponse,
    PlayerPickResponse,
    PlayerPickUpdate,
    PickDetailResponse,
    NextDrafterResponse,
    LeaderboardResponse,
    LeaderboardEntry,
    DraftRequest,
    DraftResponse,
    PicksCountResponse,
    PicksCountEntry,
)
from ..utils.dynamodb import DynamoDBClient
from ..utils.logging import cwlogger, Timer
from ..utils.name_matching import names_match

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
    with Timer() as timer:
        try:
            cwlogger.info("GET_ROUTES_START", "Retrieving available API routes")

            routes = []
            for route in router.routes:
                # Skip the root endpoint itself to avoid recursion
                if route.path != "/api/v1/deadpool/":
                    routes.append(
                        {"path": f"/api/v1/deadpool{route.path}", "name": route.name}
                    )

            cwlogger.info(
                "GET_ROUTES_COMPLETE",
                f"Retrieved {len(routes)} routes",
                data={"route_count": len(routes), "elapsed_ms": timer.elapsed_ms},
            )

            return {
                "message": "Successfully retrieved available routes",
                "routes": routes,
            }

        except Exception as e:
            cwlogger.error(
                "GET_ROUTES_ERROR",
                "Error retrieving routes",
                error=e,
                data={"elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving routes"
            )


@router.get("/players", response_model=PlayerResponse)
async def get_players(
    year: Optional[int] = Query(None, description="Filter players by year"),
):
    """
    Get current players for a given year, sorted by draft order.
    Players are considered current if they have a draft order > 0.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYERS_START",
                f"Retrieving players for year {target_year}",
                data={"year": target_year},
            )

            db = DynamoDBClient()
            players = await db.get_players(target_year)

            cwlogger.info(
                "GET_PLAYERS_COMPLETE",
                f"Retrieved {len(players)} players",
                data={
                    "year": target_year,
                    "player_count": len(players),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved players", "data": players}

        except Exception as e:
            cwlogger.error(
                "GET_PLAYERS_ERROR",
                "Error retrieving players",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving players"
            )


@router.get("/players/{player_id}", response_model=SinglePlayerResponse)
async def get_player(
    player_id: str = Path(..., description="The ID of the player to get"),
    year: Optional[int] = Query(
        None, description="The year to get the player's draft order for"
    ),
):
    """
    Get a specific player's information.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYER_START",
                f"Retrieving player {player_id}",
                data={"player_id": player_id, "year": target_year},
            )

            db = DynamoDBClient()
            player = await db.get_player(player_id, target_year)

            if not player:
                cwlogger.warning(
                    "GET_PLAYER_ERROR",
                    "Player not found",
                    data={"player_id": player_id, "year": target_year},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            cwlogger.info(
                "GET_PLAYER_COMPLETE",
                f"Retrieved player {player_id}",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved player", "data": player}

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PLAYER_ERROR",
                "Error retrieving player",
                error=e,
                data={
                    "player_id": player_id,
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving player"
            )


@router.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: str = Path(..., description="The ID of the player to update or create"),
    updates: PlayerUpdate = None,
):
    """
    Update or create a player's information.

    When creating a new player, the following fields are required:
    - name: Player's full name
    - draft_order: Player's draft position
    - year: Draft year
    """
    with Timer() as timer:
        try:
            if not updates:
                cwlogger.warning(
                    "UPDATE_PLAYER_ERROR",
                    "No update data provided",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=400, detail="Update data is required")

            cwlogger.info(
                "UPDATE_PLAYER_START",
                f"{'Creating' if player_id == 'new' else 'Updating'} player {player_id}",
                data={
                    "player_id": player_id,
                    "updates": updates.dict(exclude_unset=True),
                },
            )

            # Validate required fields for new players
            existing_player = await DynamoDBClient().get_player(player_id)
            if not existing_player:
                if (
                    not updates.name
                    or updates.draft_order is None
                    or updates.year is None
                ):
                    cwlogger.warning(
                        "UPDATE_PLAYER_ERROR",
                        "Missing required fields for new player",
                        data={
                            "player_id": player_id,
                            "provided_fields": updates.dict(exclude_unset=True),
                        },
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="New players require name, draft_order, and year",
                    )

            db = DynamoDBClient()
            updated_player = await db.update_player(
                player_id, updates.dict(exclude_unset=True)
            )

            cwlogger.info(
                "UPDATE_PLAYER_COMPLETE",
                f"Successfully {'created' if not existing_player else 'updated'} player",
                data={
                    "player_id": player_id,
                    "player_name": updated_player["name"],
                    "is_new": not existing_player,
                    "year": updates.year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated player",
                "data": [updated_player],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_PLAYER_ERROR",
                "Error updating player",
                error=e,
                data={"player_id": player_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while updating player"
            )


@router.get("/people", response_model=PersonResponse)
async def get_people():
    """
    Get a list of all people in the deadpool.
    """
    with Timer() as timer:
        try:
            cwlogger.info("GET_PEOPLE_START", "Retrieving all people")

            db = DynamoDBClient()
            people = await db.get_people()

            cwlogger.info(
                "GET_PEOPLE_COMPLETE",
                f"Retrieved {len(people)} people",
                data={"total_count": len(people), "elapsed_ms": timer.elapsed_ms},
            )

            return {"message": "Successfully retrieved people", "data": people}

        except Exception as e:
            cwlogger.error(
                "GET_PEOPLE_ERROR",
                "Error retrieving people",
                error=e,
                data={"elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving people"
            )


@router.get("/people/{person_id}", response_model=SinglePersonResponse)
async def get_person(
    person_id: str = Path(..., description="The ID of the person to get"),
):
    """
    Get a specific person's information.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "GET_PERSON_START",
                f"Retrieving person {person_id}",
                data={"person_id": person_id},
            )

            db = DynamoDBClient()
            person = await db.get_person(person_id)

            if not person:
                cwlogger.warning(
                    "GET_PERSON_ERROR",
                    "Person not found",
                    data={"person_id": person_id},
                )
                raise HTTPException(status_code=404, detail="Person not found")

            cwlogger.info(
                "GET_PERSON_COMPLETE",
                f"Retrieved person {person_id}",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "status": person["status"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved person", "data": person}

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PERSON_ERROR",
                "Error retrieving person",
                error=e,
                data={"person_id": person_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving person"
            )


@router.put("/people/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: str = Path(..., description="The ID of the person to update or create"),
    updates: PersonUpdate = None,
):
    """
    Update or create a person's information.

    When creating a new person, the following field is required:
    - name: Person's full name

    Use 'new' as the person_id to automatically generate a UUID for a new person.
    """
    with Timer() as timer:
        try:
            if not updates or not updates.name:
                cwlogger.warning(
                    "UPDATE_PERSON_ERROR",
                    "Name is required",
                    data={"person_id": person_id},
                )
                raise HTTPException(status_code=400, detail="Name is required")

            # Generate UUID for new people
            is_new = person_id == "new"
            if is_new:
                person_id = str(uuid.uuid4())
                cwlogger.info(
                    "UPDATE_PERSON_START",
                    "Creating new person",
                    data={"person_id": person_id, "name": updates.name},
                )
            else:
                cwlogger.info(
                    "UPDATE_PERSON_START",
                    f"Updating person {person_id}",
                    data={
                        "person_id": person_id,
                        "updates": updates.dict(exclude_unset=True),
                    },
                )

            db = DynamoDBClient()
            updated_person = await db.update_person(
                person_id, updates.dict(exclude_unset=True)
            )

            cwlogger.info(
                "UPDATE_PERSON_COMPLETE",
                f"Successfully {'created' if is_new else 'updated'} person",
                data={
                    "person_id": person_id,
                    "person_name": updated_person["name"],
                    "is_new": is_new,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated person",
                "data": [updated_person],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_PERSON_ERROR",
                "Error updating person",
                error=e,
                data={"person_id": person_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while updating person"
            )


@router.get("/draft-order", response_model=DraftOrderListResponse)
async def get_draft_order(
    year: Optional[int] = Query(None, description="Filter draft orders by year"),
    player_id: Optional[str] = Query(
        None, description="Filter draft orders by player ID"
    ),
):
    """
    Get draft order records, optionally filtered by year and/or player.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_DRAFT_ORDER_START",
                "Retrieving draft orders",
                data={"year": target_year, "player_id": player_id},
            )

            db = DynamoDBClient()
            draft_orders = await db.get_draft_order(target_year, player_id)

            cwlogger.info(
                "GET_DRAFT_ORDER_COMPLETE",
                f"Retrieved {len(draft_orders)} draft orders",
                data={
                    "year": target_year,
                    "player_id": player_id,
                    "order_count": len(draft_orders),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved draft orders",
                "data": draft_orders,
            }

        except Exception as e:
            cwlogger.error(
                "GET_DRAFT_ORDER_ERROR",
                "Error retrieving draft orders",
                error=e,
                data={
                    "year": target_year,
                    "player_id": player_id,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving draft orders",
            )


@router.put("/draft-order/{player_id}", response_model=DraftOrderListResponse)
async def update_draft_order(
    player_id: str = Path(..., description="The ID of the player to update"),
    year: int = Query(..., description="The year for the draft order"),
    draft_order: int = Query(..., description="The new draft order position"),
):
    """
    Update a player's draft order for a specific year.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "UPDATE_DRAFT_ORDER_START",
                f"Updating draft order for player {player_id}",
                data={"player_id": player_id, "year": year, "draft_order": draft_order},
            )

            db = DynamoDBClient()

            # Verify player exists
            player = await db.get_player(player_id)
            if not player:
                cwlogger.warning(
                    "UPDATE_DRAFT_ORDER_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            updated_order = await db.update_draft_order(player_id, year, draft_order)

            cwlogger.info(
                "UPDATE_DRAFT_ORDER_COMPLETE",
                "Successfully updated draft order",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "year": year,
                    "draft_order": draft_order,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated draft order",
                "data": [updated_order],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_DRAFT_ORDER_ERROR",
                "Error updating draft order",
                error=e,
                data={
                    "player_id": player_id,
                    "year": year,
                    "draft_order": draft_order,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while updating draft order"
            )


@router.get("/player-picks/{player_id}", response_model=PlayerPickResponse)
async def get_player_picks(
    player_id: str = Path(..., description="The ID of the player to get picks for"),
    year: Optional[int] = Query(None, description="Filter picks by year"),
):
    """
    Get all picks for a specific player, optionally filtered by year.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYER_PICKS_START",
                f"Retrieving picks for player {player_id}",
                data={"player_id": player_id, "year": target_year},
            )

            db = DynamoDBClient()

            # Verify player exists
            player = await db.get_player(player_id)
            if not player:
                cwlogger.warning(
                    "GET_PLAYER_PICKS_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            picks = await db.get_player_picks(player_id, target_year)

            cwlogger.info(
                "GET_PLAYER_PICKS_COMPLETE",
                f"Retrieved {len(picks)} picks",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "year": target_year,
                    "pick_count": len(picks),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved player picks", "data": picks}

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PLAYER_PICKS_ERROR",
                "Error retrieving player picks",
                error=e,
                data={
                    "player_id": player_id,
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving player picks",
            )


@router.put("/player-picks/{player_id}", response_model=PlayerPickResponse)
async def update_player_pick(
    player_id: str = Path(..., description="The ID of the player to update picks for"),
    updates: PlayerPickUpdate = None,
):
    """
    Update or create a pick for a specific player.
    """
    with Timer() as timer:
        try:
            if not updates:
                raise HTTPException(status_code=400, detail="Update data is required")

            cwlogger.info(
                "PLAYER_PICK_START",
                f"Updating pick for player {player_id}",
                data={
                    "player_id": player_id,
                    "person_id": updates.person_id,
                    "year": updates.year,
                },
            )

            db = DynamoDBClient()

            # Verify player exists
            player = await db.get_player(player_id)
            if not player:
                cwlogger.error(
                    "PLAYER_PICK_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            # Verify person exists
            person = await db.get_person(updates.person_id)
            if not person:
                cwlogger.error(
                    "PLAYER_PICK_ERROR",
                    "Person not found",
                    data={"person_id": updates.person_id},
                )
                raise HTTPException(status_code=404, detail="Person not found")

            updated_pick = await db.update_player_pick(player_id, updates.dict())

            cwlogger.info(
                "PLAYER_PICK_COMPLETE",
                f"Successfully updated pick for player {player_id}",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "person_id": updates.person_id,
                    "person_name": person["name"],
                    "year": updates.year,
                    "timestamp": updated_pick["timestamp"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated player pick",
                "data": [updated_pick],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "PLAYER_PICK_ERROR",
                "Unexpected error updating player pick",
                error=e,
                data={"player_id": player_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while updating the player pick",
            )


@router.get("/picks", response_model=PickDetailResponse)
async def get_picks(year: int = Query(..., description="Filter picks by year")):
    """
    Get all picks for a given year with player and picked person details.
    Returns data sorted by draft order.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "GET_PICKS_START",
                f"Retrieving all picks for year {year}",
                data={"year": year},
            )

            db = DynamoDBClient()

            # Get all players for the year
            players = await db.get_players(year)

            # Build the detailed pick information
            detailed_picks = []
            for player in players:
                # Get all picks for this player in the year
                picks = await db.get_player_picks(player["id"], year)

                if picks:
                    # For each pick, get the person details and create a pick detail
                    for pick in picks:
                        picked_person = await db.get_person(pick["person_id"])

                        # Extract additional person details from metadata
                        person_metadata = (
                            picked_person.get("metadata", {}) if picked_person else {}
                        )

                        pick_detail = {
                            "player_id": player["id"],
                            "player_name": player["name"],
                            "draft_order": player["draft_order"],
                            "pick_person_id": pick["person_id"],
                            "pick_person_name": picked_person["name"]
                            if picked_person
                            else None,
                            "pick_person_age": person_metadata.get("Age"),
                            "pick_person_birth_date": person_metadata.get("BirthDate"),
                            "pick_person_death_date": person_metadata.get("DeathDate"),
                            "pick_timestamp": pick["timestamp"],
                            "year": year,
                        }
                        detailed_picks.append(pick_detail)
                else:
                    # Include player even if they have no picks
                    pick_detail = {
                        "player_id": player["id"],
                        "player_name": player["name"],
                        "draft_order": player["draft_order"],
                        "pick_person_id": None,
                        "pick_person_name": None,
                        "pick_person_age": None,
                        "pick_person_birth_date": None,
                        "pick_person_death_date": None,
                        "pick_timestamp": None,
                        "year": year,
                    }
                    detailed_picks.append(pick_detail)

            # Sort by draft order
            detailed_picks.sort(key=lambda x: x["draft_order"])

            cwlogger.info(
                "GET_PICKS_COMPLETE",
                f"Retrieved {len(detailed_picks)} picks",
                data={
                    "year": year,
                    "pick_count": len(detailed_picks),
                    "player_count": len(players),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved picks", "data": detailed_picks}

        except Exception as e:
            cwlogger.error(
                "GET_PICKS_ERROR",
                "Error retrieving picks",
                error=e,
                data={"year": year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving picks"
            )


@router.post("/draft", response_model=DraftResponse)
async def draft_person(draft_request: DraftRequest):
    """
    Draft a person for the current year.
    Rules:
    1. Cannot draft someone already picked in current year
    2. Can draft someone from previous years
    3. Creates new person entry if not found in database
    4. Creates player pick entry for the drafting player
    """
    with Timer() as timer:
        try:
            db = DynamoDBClient()
            current_year = datetime.now().year

            cwlogger.info(
                "DRAFT_START",
                f"Starting draft process for {draft_request.name}",
                data={
                    "player_id": draft_request.player_id,
                    "person_name": draft_request.name,
                    "year": current_year,
                },
            )

            # Verify player exists
            player = await db.get_player(draft_request.player_id)
            if not player:
                cwlogger.error(
                    "DRAFT_ERROR",
                    "Player not found",
                    data={
                        "player_id": draft_request.player_id,
                        "person_name": draft_request.name,
                        "year": current_year,
                    },
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Player with ID {draft_request.player_id} not found",
                )

            # Get all people to check if person already exists
            people = await db.get_people()
            
            # Use fuzzy name matching to find existing person
            existing_person = None
            best_match_score = 0
            for person in people:
                match_result = names_match(person["name"], draft_request.name)
                if match_result["match"] and match_result["similarity"] > best_match_score:
                    existing_person = person
                    best_match_score = match_result["similarity"]
                    
                    cwlogger.info(
                        "DRAFT_NAME_MATCH",
                        "Found matching person",
                        data={
                            "input_name": draft_request.name,
                            "matched_name": person["name"],
                            "normalized_input": match_result["normalized1"],
                            "normalized_match": match_result["normalized2"],
                            "similarity": match_result["similarity"],
                            "exact_match": match_result["exact_match"]
                        }
                    )

            # Get all picks for current year to check for duplicates
            players = await db.get_players(current_year)
            for player in players:
                picks = await db.get_player_picks(player["id"], current_year)
                for pick in picks:
                    picked_person = await db.get_person(pick["person_id"])
                    if picked_person:
                        match_result = names_match(picked_person["name"], draft_request.name)
                        if match_result["match"]:
                            cwlogger.warning(
                                "DRAFT_DUPLICATE",
                                "Attempted to draft already picked person",
                                data={
                                    "person_name": draft_request.name,
                                    "matched_name": picked_person["name"],
                                    "year": current_year,
                                    "similarity": match_result["similarity"],
                                    "existing_pick": {
                                        "player_id": player["id"],
                                        "player_name": player["name"],
                                        "pick_timestamp": pick.get("timestamp"),
                                    },
                                },
                            )
                            raise HTTPException(
                                status_code=400,
                                detail=f"{draft_request.name} (or similar name) has already been drafted for {current_year}",
                            )

            # If person exists in database but wasn't picked this year, use their ID
            if existing_person:
                person_id = existing_person["id"]
                cwlogger.info(
                    "DRAFT_PERSON",
                    "Using existing person record",
                    data={
                        "person_id": person_id,
                        "person_name": draft_request.name,
                        "matched_name": existing_person["name"],
                        "similarity": best_match_score,
                        "is_new": False,
                    },
                )
            else:
                # Create new person with UUID
                person_id = str(uuid.uuid4())
                await db.update_person(person_id, {"name": draft_request.name})
                cwlogger.info(
                    "DRAFT_PERSON",
                    "Created new person record",
                    data={
                        "person_id": person_id,
                        "person_name": draft_request.name,
                        "is_new": True,
                    },
                )

            # Create player pick entry
            pick_update = {"person_id": person_id, "year": current_year}
            player_pick = await db.update_player_pick(
                draft_request.player_id, pick_update
            )

            cwlogger.info(
                "DRAFT_COMPLETE",
                "Successfully completed draft",
                data={
                    "player_id": draft_request.player_id,
                    "person_id": person_id,
                    "person_name": draft_request.name,
                    "year": current_year,
                    "is_new_person": not existing_person,
                    "pick_timestamp": player_pick["timestamp"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully processed draft request",
                "data": {
                    "person_id": person_id,
                    "name": draft_request.name,
                    "is_new": not existing_person,
                    "pick_timestamp": player_pick["timestamp"],
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "DRAFT_ERROR",
                "Unexpected error during draft process",
                error=e,
                data={
                    "player_id": draft_request.player_id,
                    "person_name": draft_request.name,
                    "year": current_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while processing the draft",
            )


@router.get("/draft-next", response_model=NextDrafterResponse)
async def get_next_drafter():
    """
    Get the next player who should draft based on:
    1. Least number of picks for current year
    2. Lowest draft order number for current year
    3. Total picks not exceeding 20 for active people
    """
    with Timer() as timer:
        try:
            db = DynamoDBClient()
            year = datetime.now().year  # Current year for drafting

            cwlogger.info(
                "GET_NEXT_DRAFTER_START", "Determining next drafter", data={"year": year}
            )

            # Get all players for the current year
            players = await db.get_players(year)
            if not players:
                cwlogger.warning(
                    "GET_NEXT_DRAFTER_ERROR",
                    "No players found for current year",
                    data={"year": year},
                )
                raise HTTPException(
                    status_code=404, detail="No players found for current year"
                )

            # Get picks for each player and count active picks
            player_data = []
            for player in players:
                picks = await db.get_player_picks(player["id"], year)

                # Count picks for active people only
                active_pick_count = 0
                for pick in picks:
                    person = await db.get_person(pick["person_id"])
                    if person and "DeathDate" not in person.get("metadata", {}):
                        active_pick_count += 1

                # Log player's pick status
                cwlogger.info(
                    "GET_NEXT_DRAFTER_PLAYER",
                    f"Analyzed picks for player {player['name']}",
                    data={
                        "player_id": player["id"],
                        "player_name": player["name"],
                        "draft_order": player["draft_order"],
                        "total_picks": len(picks),
                        "active_picks": active_pick_count,
                        "year": year,
                    },
                )

                # Only include players who haven't reached 20 active picks
                if active_pick_count < 20:
                    player_data.append(
                        {
                            "id": player["id"],
                            "name": player["name"],
                            "draft_order": player["draft_order"],
                            "pick_count": len(picks),
                            "active_pick_count": active_pick_count,
                        }
                    )

            if not player_data:
                cwlogger.warning(
                    "GET_NEXT_DRAFTER_ERROR",
                    "No eligible players found",
                    data={"year": year, "total_players": len(players)},
                )
                raise HTTPException(status_code=404, detail="No eligible players found")

            # Sort by pick count first, then by draft order
            player_data.sort(key=lambda x: (x["pick_count"], x["draft_order"]))

            # Return the first player (lowest draft order and least picks)
            next_drafter = player_data[0]

            cwlogger.info(
                "GET_NEXT_DRAFTER_COMPLETE",
                f"Selected next drafter: {next_drafter['name']}",
                data={
                    "player_id": next_drafter["id"],
                    "player_name": next_drafter["name"],
                    "draft_order": next_drafter["draft_order"],
                    "pick_count": next_drafter["pick_count"],
                    "active_pick_count": next_drafter["active_pick_count"],
                    "eligible_players": len(player_data),
                    "year": year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully determined next drafter",
                "data": {
                    "player_id": next_drafter["id"],
                    "player_name": next_drafter["name"],
                    "draft_order": next_drafter["draft_order"],
                    "current_pick_count": next_drafter["pick_count"],
                    "active_pick_count": next_drafter["active_pick_count"],
                },
            }

        except HTTPException:
            # Re-raise HTTP exceptions (they're already logged)
            raise
        except Exception as e:
            cwlogger.error(
                "GET_NEXT_DRAFTER_ERROR",
                "Unexpected error determining next drafter",
                error=e,
                data={"year": year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while determining the next drafter",
            )


@router.get("/picks-counts", response_model=PicksCountResponse)
async def get_picks_counts(
    year: Optional[int] = Query(
        None,
        description="The year to get pick counts for (defaults to current year)",
    ),
):
    """
    Get pick counts for all players in a specific year.
    Returns a list of players with their pick counts, sorted by draft order.
    """
    with Timer() as timer:
        try:
            # Use current year if none specified
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PICKS_COUNTS_START",
                f"Retrieving pick counts for year {target_year}",
                data={"year": target_year},
            )

            db = DynamoDBClient()

            # Get all players for the year
            players = await db.get_players(target_year)

            # Calculate pick counts for each player
            picks_counts = []
            for player in players:
                # Get all picks for this player in the year
                picks = await db.get_player_picks(player["id"], target_year)

                picks_count_entry = PicksCountEntry(
                    player_id=player["id"],
                    player_name=player["name"],
                    draft_order=player["draft_order"],
                    pick_count=len(picks),
                    year=target_year,
                )
                picks_counts.append(picks_count_entry)

                cwlogger.info(
                    "GET_PICKS_COUNTS_PLAYER",
                    f"Calculated picks for player {player['name']}",
                    data={
                        "player_id": player["id"],
                        "player_name": player["name"],
                        "pick_count": len(picks),
                        "year": target_year,
                    },
                )

            # Sort by draft order
            picks_counts.sort(key=lambda x: x.draft_order)

            cwlogger.info(
                "GET_PICKS_COUNTS_COMPLETE",
                f"Retrieved pick counts for {len(picks_counts)} players",
                data={
                    "year": target_year,
                    "player_count": len(picks_counts),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved pick counts",
                "data": picks_counts,
            }

        except Exception as e:
            cwlogger.error(
                "GET_PICKS_COUNTS_ERROR",
                "Error retrieving pick counts",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving pick counts",
            )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    year: Optional[int] = Query(
        None,
        description="The year to get the leaderboard for (defaults to current year)",
    ),
):
    """
    Get the leaderboard for a specific year.
    Players are scored based on their dead celebrity picks:
    Score = sum of (50 + (100 - Age)) for each dead celebrity
    """
    with Timer() as timer:
        try:
            # Use current year if none specified
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "LEADERBOARD_START",
                f"Calculating leaderboard for year {target_year}",
                data={"year": target_year},
            )

            db = DynamoDBClient()

            # Get all players for the year
            players = await db.get_players(target_year)

            # Calculate scores for each player
            leaderboard_entries = []
            for player in players:
                total_score = 0
                # Get all picks for this player in the year
                picks = await db.get_player_picks(player["id"], target_year)

                # Calculate score for each pick
                dead_picks = 0
                for pick in picks:
                    person = await db.get_person(pick["person_id"])
                    metadata = person.get("metadata", {}) if person else {}
                    death_date = metadata.get("DeathDate")
                    
                    if death_date:
                        # Extract year from death date and compare to target year
                        death_year = datetime.strptime(death_date, "%Y-%m-%d").year
                        if death_year == target_year:
                            # Person died in target year, calculate score
                            age = metadata.get("Age", 0)
                            pick_score = 50 + (100 - age)
                            total_score += pick_score
                            dead_picks += 1

                # Create leaderboard entry
                entry = LeaderboardEntry(
                    player_id=player["id"],
                    player_name=player["name"],
                    score=total_score,
                )
                leaderboard_entries.append(entry)

                cwlogger.info(
                    "LEADERBOARD_PLAYER",
                    f"Calculated score for player {player['name']}",
                    data={
                        "player_id": player["id"],
                        "player_name": player["name"],
                        "score": total_score,
                        "total_picks": len(picks),
                        "dead_picks": dead_picks,
                        "year": target_year,
                    },
                )

            # Sort by score (highest first)
            leaderboard_entries.sort(key=lambda x: x.score, reverse=True)

            cwlogger.info(
                "LEADERBOARD_COMPLETE",
                f"Generated leaderboard for year {target_year}",
                data={
                    "year": target_year,
                    "player_count": len(leaderboard_entries),
                    "top_score": leaderboard_entries[0].score
                    if leaderboard_entries
                    else 0,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved leaderboard",
                "data": leaderboard_entries,
            }

        except Exception as e:
            cwlogger.error(
                "LEADERBOARD_ERROR",
                "Error generating leaderboard",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while generating the leaderboard",
            )
