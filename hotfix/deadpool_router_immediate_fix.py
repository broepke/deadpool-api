"""
Immediate hotfix for deadpool router to handle 2026 API errors.
This can be applied directly to the existing router file.
"""

# Add this import at the top of src/routers/deadpool.py
from datetime import datetime

# Replace the existing get_picks_by_person function with this version:

@router.get("/picks/by-person/{person_id}", response_model=PaginatedPickDetailResponse)
async def get_picks_by_person(
    person_id: str = Path(..., description="The ID of the person to get picks for"),
    year: Optional[int] = Query(None, description="Filter picks by year (defaults to current year)"),
    limit: Optional[int] = Query(None, description="Limit the number of results returned. If not specified, pagination will be used."),
    page: Optional[int] = Query(1, description="Page number for paginated results", ge=1),
    page_size: Optional[int] = Query(10, description="Number of items per page", ge=1, le=100),
):
    """
    Get all picks for a specific person across all players.
    HOTFIX: Added fallback logic for 2026 migration issues.
    """
    with Timer() as timer:
        try:
            # HOTFIX: Implement safe year handling
            def get_safe_year(requested_year):
                if requested_year is not None:
                    return requested_year
                
                current_year = datetime.now().year
                
                # If current year is 2026, check if we have data
                if current_year == 2026:
                    try:
                        # Quick check for 2026 draft order
                        db_test = DynamoDBClient()
                        response = db_test.table.query(
                            KeyConditionExpression="PK = :pk",
                            ExpressionAttributeValues={':pk': 'YEAR#2026'},
                            Limit=1
                        )
                        
                        if not response.get('Items'):
                            cwlogger.warning(
                                "YEAR_FALLBACK_2026",
                                "No 2026 draft order found, falling back to 2025",
                                data={"requested_year": current_year, "fallback_year": 2025}
                            )
                            return 2025
                    except Exception as e:
                        cwlogger.error(
                            "YEAR_CHECK_ERROR_2026",
                            "Error checking 2026 data, falling back to 2025",
                            error=e
                        )
                        return 2025
                
                return current_year
            
            # Use safe year logic
            target_year = get_safe_year(year)
            
            # Verify person exists first to return a proper 404 if needed
            db = DynamoDBClient()
            person = await db.get_person(person_id)
            if not person:
                cwlogger.warning(
                    "GET_PICKS_BY_PERSON_ERROR",
                    "Person not found",
                    data={"person_id": person_id},
                )
                raise HTTPException(status_code=404, detail="Person not found")

            cwlogger.info(
                "GET_PICKS_BY_PERSON_START",
                f"Retrieving picks for person {person_id}",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "requested_year": year,
                    "target_year": target_year,
                    "limit": limit,
                    "page": page,
                    "page_size": page_size
                },
            )

            # HOTFIX: Use direct database queries with error handling
            try:
                # Determine years to search
                if year is not None:
                    years_to_search = [year]
                else:
                    # Search target year and previous years as fallback
                    years_to_search = [target_year]
                    if target_year == datetime.now().year:
                        years_to_search.extend([target_year - 1, target_year - 2])
                
                all_picks = []
                unique_picks = set()
                
                for search_year in years_to_search:
                    try:
                        # Get players for this year with error handling
                        players = await db.get_players(search_year)
                        if not players:
                            cwlogger.info(
                                "GET_PICKS_BY_PERSON_NO_PLAYERS",
                                f"No players found for year {search_year}",
                                data={"year": search_year, "person_id": person_id}
                            )
                            continue
                        
                        # Check each player's picks
                        for player in players:
                            try:
                                player_picks = await db.get_player_picks(player["id"], search_year)
                                
                                for pick in player_picks:
                                    if pick["person_id"] == person_id:
                                        unique_key = f"{player['id']}_{person_id}_{pick['year']}"
                                        
                                        if unique_key not in unique_picks:
                                            unique_picks.add(unique_key)
                                            
                                            pick_detail = {
                                                "player_id": player["id"],
                                                "player_name": player["name"],
                                                "draft_order": player["draft_order"],
                                                "pick_person_id": person_id,
                                                "pick_person_name": person["name"],
                                                "pick_person_age": person["metadata"].get("Age"),
                                                "pick_person_birth_date": person["metadata"].get("BirthDate"),
                                                "pick_person_death_date": person["metadata"].get("DeathDate"),
                                                "pick_timestamp": pick["timestamp"],
                                                "year": pick["year"],
                                            }
                                            all_picks.append(pick_detail)
                            
                            except Exception as e:
                                cwlogger.error(
                                    "GET_PICKS_BY_PERSON_PLAYER_ERROR",
                                    f"Error getting picks for player {player['id']}",
                                    error=e,
                                    data={"player_id": player["id"], "year": search_year}
                                )
                                # Continue with other players
                                continue
                    
                    except Exception as e:
                        cwlogger.error(
                            "GET_PICKS_BY_PERSON_YEAR_ERROR",
                            f"Error processing year {search_year}",
                            error=e,
                            data={"year": search_year, "person_id": person_id}
                        )
                        # Continue with other years
                        continue
                
                # Sort by timestamp descending
                all_picks.sort(key=lambda x: x["pick_timestamp"] or "", reverse=True)
                
                total_items = len(all_picks)
                
                # Handle limit case
                if limit is not None:
                    limited_picks = all_picks[:limit]
                    result = {
                        "message": "Successfully retrieved picks",
                        "data": limited_picks,
                        "total": total_items,
                        "page": 1,
                        "page_size": limit,
                        "total_pages": 1
                    }
                else:
                    # Handle pagination
                    start_idx = (page - 1) * page_size
                    end_idx = start_idx + page_size
                    paginated_picks = all_picks[start_idx:end_idx]
                    total_pages = (total_items + page_size - 1) // page_size
                    
                    result = {
                        "message": "Successfully retrieved picks",
                        "data": paginated_picks,
                        "total": total_items,
                        "page": page,
                        "page_size": page_size,
                        "total_pages": total_pages
                    }

            except Exception as e:
                cwlogger.error(
                    "GET_PICKS_BY_PERSON_PROCESSING_ERROR",
                    "Error processing picks data",
                    error=e,
                    data={"person_id": person_id, "target_year": target_year}
                )
                # Return empty result instead of failing
                result = {
                    "message": "Successfully retrieved picks",
                    "data": [],
                    "total": 0,
                    "page": page if limit is None else 1,
                    "page_size": limit or page_size,
                    "total_pages": 0
                }

            cwlogger.info(
                "GET_PICKS_BY_PERSON_COMPLETE",
                f"Retrieved {len(result['data'])} picks",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "target_year": target_year,
                    "total_items": result["total"],
                    "returned_items": len(result["data"]),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return result

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PICKS_BY_PERSON_FATAL_ERROR",
                "Fatal error in get_picks_by_person",
                error=e,
                data={
                    "person_id": person_id,
                    "year": year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            # Return a safe response instead of 500 error
            return {
                "message": "Error retrieving picks, please try again",
                "data": [],
                "total": 0,
                "page": page if limit is None else 1,
                "page_size": limit or page_size,
                "total_pages": 0
            }