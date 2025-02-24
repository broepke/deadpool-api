import boto3
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException
from .logging import cwlogger, Timer


class DynamoDBClient:
    """
    Utility class for DynamoDB operations.
    """

    def __init__(self, table_name: str = "Deadpool"):
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def _transform_person(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a DynamoDB person item to match our API model.
        """
        try:
            # Extract UUID from PK (format: PERSON#uuid)
            person_id = item.get("PK", "").split("#")[1]

            # Handle both 'Name' and 'name' cases
            name = item.get("Name") or item.get("name")
            if not name:
                raise ValueError(f"No name found in item: {item}")

            # Convert any Decimal types to int/float for JSON serialization
            metadata = {}
            for key, value in item.items():
                if key.lower() not in ["pk", "sk", "name"]:
                    if isinstance(value, Decimal):
                        metadata[key] = int(value) if value % 1 == 0 else float(value)
                    else:
                        metadata[key] = value

            return {
                "id": person_id,
                "name": name,
                "status": "deceased" if "DeathDate" in item else "active",
                "metadata": metadata,
            }
        except Exception as e:
            print(f"Error transforming item {item}: {str(e)}")
            # Return a minimal valid object to prevent API errors
            return {
                "id": "unknown",
                "name": "Unknown Person",
                "status": "unknown",
                "metadata": {},
            }

    async def get_players(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get players from DynamoDB, optionally filtered by year."""
        # Default to current year if not specified
        target_year = year if year else datetime.now().year

        with Timer() as timer:
            try:
                # First get draft order records for the year
                params = {
                    "KeyConditionExpression": "PK = :year_key",
                    "ExpressionAttributeValues": {":year_key": f"YEAR#{target_year}"},
                }

                # Use query instead of scan since we're using the partition key
                response = self.table.query(**params)
                draft_orders = response.get("Items", [])

                if not draft_orders:
                    cwlogger.info(
                        "DB_QUERY",
                        f"No draft orders found for year {target_year}",
                        data={
                            "table": self.table_name,
                            "year": target_year,
                            "elapsed_ms": timer.elapsed_ms
                        }
                    )
                    return []

                cwlogger.info(
                    "DB_QUERY",
                    f"Retrieved {len(draft_orders)} draft orders for year {target_year}",
                    data={
                        "table": self.table_name,
                        "operation": "query",
                        "year": target_year,
                        "item_count": len(draft_orders),
                        "consumed_capacity": response.get("ConsumedCapacity"),
                        "elapsed_ms": timer.elapsed_ms
                    }
                )

                # Extract player IDs and draft orders
                player_info = []
                for order in draft_orders:
                    # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                    parts = order["SK"].split("#")
                    if len(parts) >= 4:
                        draft_order = int(parts[1])
                        player_id = parts[3]
                        player_info.append((player_id, draft_order))

                if not player_info:
                    return []

                # Try batch get first, fall back to individual gets if not permitted
                all_players = {}
                try:
                    # Get all player details in one batch operation
                    player_keys = [
                        {"PK": f"PLAYER#{player_id}", "SK": "DETAILS"}
                        for player_id, _ in player_info
                    ]
                    
                    # Split into chunks of 25 (DynamoDB batch limit)
                    chunk_size = 25
                    player_chunks = [
                        player_keys[i:i + chunk_size]
                        for i in range(0, len(player_keys), chunk_size)
                    ]

                    # Batch get all players
                    for chunk in player_chunks:
                        response = self.dynamodb.batch_get_item(
                            RequestItems={
                                self.table_name: {
                                    'Keys': chunk,
                                    'ConsistentRead': True
                                }
                            }
                        )
                        
                        for item in response['Responses'][self.table_name]:
                            player_id = item['PK'].split('#')[1]
                            all_players[player_id] = item
                            
                except Exception as e:
                    cwlogger.warning(
                        "DB_BATCH_GET_FAILED",
                        "Falling back to individual GetItem operations",
                        error=e
                    )
                    # Fall back to individual GetItem operations
                    for player_id, _ in player_info:
                        try:
                            player_response = self.table.get_item(
                                Key={"PK": f"PLAYER#{player_id}", "SK": "DETAILS"}
                            )
                            player = player_response.get("Item")
                            if player:
                                all_players[player_id] = player
                        except Exception as inner_e:
                            cwlogger.error(
                                "DB_GET_ERROR",
                                f"Error getting player {player_id}",
                                error=inner_e
                            )

                # Transform players with draft order
                transformed_players = []
                for player_id, draft_order in player_info:
                    player = all_players.get(player_id)
                    if player:
                        transformed = {
                            "id": player_id,
                            "name": f"{player.get('FirstName', '')} {player.get('LastName', '')}".strip(),
                            "draft_order": draft_order,
                            "year": target_year,
                            "phone_number": player.get("PhoneNumber"),
                            "phone_verified": player.get("PhoneVerified"),
                            "sms_notifications_enabled": player.get("SmsNotificationsEnabled"),
                            "verification_code": player.get("VerificationCode"),
                            "verification_timestamp": player.get("VerificationTimestamp"),
                        }
                        transformed_players.append(transformed)

                # Sort by draft order
                transformed_players.sort(key=lambda x: x["draft_order"])
                return transformed_players

            except Exception as e:
                cwlogger.error(
                    "DB_ERROR",
                    "Error retrieving players",
                    error=e,
                    data={
                        "table": self.table_name,
                        "year": target_year,
                        "elapsed_ms": timer.elapsed_ms
                    }
                )
                return []

    async def batch_get_player_picks(
        self, player_ids: List[str], year: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get picks for multiple players in batch."""
        try:
            result = {}
            # Group by year if specified
            year_prefix = f"PICK#{year}#" if year else "PICK#"
            
            # Query picks for each player (DynamoDB doesn't support batch query)
            for player_id in player_ids:
                params = {
                    "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                    "ExpressionAttributeValues": {
                        ":pk": f"PLAYER#{player_id}",
                        ":sk_prefix": year_prefix
                    }
                }
                
                response = self.table.query(**params)
                picks = []
                
                for item in response.get("Items", []):
                    # SK format: PICK#year#person_id
                    parts = item["SK"].split("#")
                    if len(parts) >= 3:
                        picks.append({
                            "person_id": parts[2],
                            "year": int(parts[1]),
                            "timestamp": item.get("Timestamp"),
                        })
                
                # Sort by timestamp descending
                picks.sort(key=lambda x: x["timestamp"], reverse=True)
                result[player_id] = picks
            
            return result
            
        except Exception as e:
            cwlogger.error(
                "DB_ERROR",
                "Error batch getting player picks",
                error=e,
                data={"player_count": len(player_ids)}
            )
            return {}

    async def batch_get_people(self, person_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple people in batch, falling back to individual gets if batch fails."""
        result = {}
        try:
            # Create chunks of 25 keys (DynamoDB batch limit)
            chunks = [
                person_ids[i:i + 25] for i in range(0, len(person_ids), 25)
            ]
            
            # Process each chunk
            for chunk in chunks:
                try:
                    keys = [
                        {"PK": f"PERSON#{pid}", "SK": "DETAILS"}
                        for pid in chunk
                    ]
                    
                    response = self.dynamodb.batch_get_item(
                        RequestItems={
                            self.table_name: {
                                'Keys': keys,
                                'ConsistentRead': True
                            }
                        }
                    )
                    
                    # Transform and store results
                    for item in response['Responses'][self.table_name]:
                        person = self._transform_person(item)
                        result[person["id"]] = person
                        
                except Exception as batch_error:
                    cwlogger.warning(
                        "DB_BATCH_GET_FAILED",
                        "Falling back to individual GetItem operations for people",
                        error=batch_error,
                        data={"chunk_size": len(chunk)}
                    )
                    # Fall back to individual gets for this chunk
                    for person_id in chunk:
                        try:
                            response = self.table.get_item(
                                Key={"PK": f"PERSON#{person_id}", "SK": "DETAILS"}
                            )
                            item = response.get("Item")
                            if item:
                                person = self._transform_person(item)
                                result[person["id"]] = person
                        except Exception as get_error:
                            cwlogger.error(
                                "DB_GET_ERROR",
                                f"Error getting person {person_id}",
                                error=get_error
                            )
            
            return result
            
        except Exception as e:
            cwlogger.error(
                "DB_ERROR",
                "Error getting people",
                error=e,
                data={"person_count": len(person_ids)}
            )
            return result  # Return any successfully retrieved people


    async def get_people(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get people from DynamoDB with optional status filter and limit.
        Status can be 'deceased' or 'alive'.
        """
        params = {
            "FilterExpression": "SK = :details AND begins_with(PK, :person_prefix)",
            "ExpressionAttributeValues": {
                ":details": "DETAILS",
                ":person_prefix": "PERSON#"
            },
        }

        # Add status filter if specified
        if status:
            if status == "deceased":
                params["FilterExpression"] += " AND attribute_exists(DeathDate)"
            elif status == "alive":
                params["FilterExpression"] += " AND attribute_not_exists(DeathDate)"

        response = self.table.scan(**params)
        items = response.get("Items", [])
        people = [self._transform_person(item) for item in items]

        # Apply limit if specified
        if limit is not None:
            people = people[:limit]

        return people

    async def get_player(
        self, player_id: str, year: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific player from DynamoDB.
        """
        # Get player details
        try:
            # Handle case where player_id might already include the prefix
            pk = player_id if player_id.startswith("PLAYER#") else f"PLAYER#{player_id}"

            player_response = self.table.get_item(Key={"PK": pk, "SK": "DETAILS"})
            player = player_response.get("Item")

            if not player:
                # Try with the raw ID if it had the prefix, or with the prefix if it didn't
                alternate_pk = (
                    player_id.replace("PLAYER#", "")
                    if player_id.startswith("PLAYER#")
                    else f"PLAYER#{player_id}"
                )
                player_response = self.table.get_item(
                    Key={"PK": alternate_pk, "SK": "DETAILS"}
                )
                player = player_response.get("Item")
                if not player:
                    return None

            # Get draft order for the player
            target_year = year if year else datetime.now().year
            # Extract clean player ID (without PLAYER# prefix) for draft order lookup
            clean_player_id = player_id.replace("PLAYER#", "")

            # Use the same query approach as get_players method
            year_response = self.table.query(
                KeyConditionExpression="PK = :year_key",
                ExpressionAttributeValues={":year_key": f"YEAR#{target_year}"},
            )

            # Process all draft orders to find the matching player
            draft_order = None
            for order in year_response.get("Items", []):
                # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                parts = order["SK"].split("#")
                if len(parts) >= 4:
                    order_player_id = parts[3]
                    if order_player_id == clean_player_id:
                        draft_order = int(parts[1])
                        break

            if draft_order is None:
                return None

            # Transform player data
            first_name = player.get("FirstName", "")
            last_name = player.get("LastName", "")
            return {
                "id": clean_player_id,
                "name": f"{first_name} {last_name}".strip(),
                "draft_order": draft_order,
                "year": target_year,
                "phone_number": player.get("PhoneNumber"),
                "phone_verified": player.get("PhoneVerified", False),
                "sms_notifications_enabled": player.get("SmsNotificationsEnabled", True),
                "verification_code": player.get("VerificationCode"),
                "verification_timestamp": player.get("VerificationTimestamp"),
            }
        except Exception as e:
            print(f"Error getting player {player_id}: {str(e)}")
            return None

    async def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific person from DynamoDB.
        """
        try:
            response = self.table.get_item(
                Key={"PK": f"PERSON#{person_id}", "SK": "DETAILS"}
            )
            item = response.get("Item")
            if not item:
                return None
            return self._transform_person(item)
        except Exception as e:
            print(f"Error getting person {person_id}: {str(e)}")
            return None

    async def update_player(
        self, player_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update or create a player in DynamoDB.
        """
        try:
            # Get existing item first
            response = self.table.get_item(Key={"PK": f"PLAYER#{player_id}", "SK": "DETAILS"})
            item = response.get("Item", {})
            if not item:
                # New item
                item = {"PK": f"PLAYER#{player_id}", "SK": "DETAILS", "Type": "Player"}

            # Handle profile fields
            if "first_name" in updates:
                item["FirstName"] = updates["first_name"]
            if "last_name" in updates:
                item["LastName"] = updates["last_name"]
            if "phone_number" in updates:
                item["PhoneNumber"] = updates["phone_number"]
                # Reset verification status when phone number changes
                item["PhoneVerified"] = False
                # Clear any existing verification data
                if "VerificationCode" in item:
                    del item["VerificationCode"]
                if "VerificationTimestamp" in item:
                    del item["VerificationTimestamp"]
            if "phone_verified" in updates:
                item["PhoneVerified"] = updates["phone_verified"]
                # Clear verification data when verified
                if updates["phone_verified"]:
                    if "VerificationCode" in item:
                        del item["VerificationCode"]
                    if "VerificationTimestamp" in item:
                        del item["VerificationTimestamp"]
            if "sms_notifications_enabled" in updates:
                item["SmsNotificationsEnabled"] = updates["sms_notifications_enabled"]
            if "verification_code" in updates:
                item["VerificationCode"] = updates["verification_code"]
                item["VerificationTimestamp"] = updates["verification_timestamp"]

            # Handle metadata
            if updates.get("metadata"):
                for key, value in updates["metadata"].items():
                    item[key] = value

            # Create/Update player record
            self.table.put_item(Item=item)

            # Handle draft order if provided
            if "draft_order" in updates and "year" in updates:
                year_key = f'YEAR#{updates["year"]}'
                order_sk = f'ORDER#{updates["draft_order"]}#PLAYER#{player_id}'

                self.table.put_item(
                    Item={"PK": year_key, "SK": order_sk, "Type": "DraftOrder"}
                )

            # Get the updated player to return
            return (await self.get_players(updates.get("year")))[0]

        except Exception as e:
            print(f"Error updating player: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to update/create player"
            )

    async def get_draft_order(
        self, year: Optional[int] = None, player_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get draft order records from DynamoDB, optionally filtered by year and/or player.
        """
        draft_orders = []

        if year:
            # Query by specific year
            params = {
                "KeyConditionExpression": "PK = :year_key",
                "ExpressionAttributeValues": {":year_key": f"YEAR#{year}"},
            }

            if player_id:
                # Add player filter if specified
                params["FilterExpression"] = "contains(SK, :player_id)"
                params["ExpressionAttributeValues"][":player_id"] = player_id

            response = self.table.query(**params)
            items = response.get("Items", [])

            for item in items:
                # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                parts = item["SK"].split("#")
                if len(parts) >= 4:
                    draft_orders.append(
                        {
                            "player_id": parts[3],
                            "draft_order": int(parts[1]),
                            "year": year,
                        }
                    )
        else:
            # If no year specified, scan all years
            params = {
                "FilterExpression": "begins_with(PK, :year_prefix)",
                "ExpressionAttributeValues": {":year_prefix": "YEAR#"},
            }

            if player_id:
                # Add player filter if specified
                params["FilterExpression"] += " and contains(SK, :player_id)"
                params["ExpressionAttributeValues"][":player_id"] = player_id

            response = self.table.scan(**params)
            items = response.get("Items", [])

            for item in items:
                # Extract year from PK (format: YEAR#yyyy)
                year_str = item["PK"].split("#")[1]
                # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                parts = item["SK"].split("#")
                if len(parts) >= 4:
                    draft_orders.append(
                        {
                            "player_id": parts[3],
                            "draft_order": int(parts[1]),
                            "year": int(year_str),
                        }
                    )

        # Sort by year (descending) and draft order (ascending)
        draft_orders.sort(key=lambda x: (-x["year"], x["draft_order"]))
        return draft_orders

    async def update_draft_order(
        self, player_id: str, year: int, draft_order: int
    ) -> Dict[str, Any]:
        """
        Update a draft order in DynamoDB.
        """
        try:
            # Create new draft order record
            item = {
                "PK": f"YEAR#{year}",
                "SK": f"ORDER#{draft_order}#PLAYER#{player_id}",
                "Type": "DraftOrder",
            }

            self.table.put_item(Item=item)

            return {"player_id": player_id, "draft_order": draft_order, "year": year}
        except Exception as e:
            print(f"Error updating draft order: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update draft order")

    async def get_player_picks(
        self, player_id: str, year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all picks for a specific player, optionally filtered by year.
        """
        try:
            # Always use KeyConditionExpression for both PK and SK
            params = {
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "ExpressionAttributeValues": {
                    ":pk": f"PLAYER#{player_id}",
                    ":sk_prefix": f"PICK#{year}#" if year else "PICK#"
                }
            }

            response = self.table.query(**params)
            items = response.get("Items", [])

            picks = []
            for item in items:
                # SK format: PICK#year#person_id
                parts = item["SK"].split("#")
                if len(parts) >= 3:
                    picks.append(
                        {
                            "person_id": parts[2],
                            "year": int(parts[1]),
                            "timestamp": item.get("Timestamp"),
                        }
                    )

            # Sort by timestamp descending (most recent first)
            picks.sort(key=lambda x: x["timestamp"], reverse=True)
            return picks

        except Exception as e:
            print(f"Error getting picks for player {player_id}: {str(e)}")
            return []

    async def update_player_pick(
        self, player_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update or create a player pick in DynamoDB.
        """
        try:
            # Create new pick record with current timestamp
            item = {
                "PK": f"PLAYER#{player_id}",
                "SK": f'PICK#{updates["year"]}#{updates["person_id"]}',
                "Year": updates["year"],
                "PersonID": updates["person_id"],
                "Timestamp": datetime.utcnow().isoformat(),
            }

            self.table.put_item(Item=item)

            return {
                "person_id": updates["person_id"],
                "year": updates["year"],
                "timestamp": item["Timestamp"],
            }
        except Exception as e:
            print(f"Error updating player pick: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update player pick")

    async def update_person(
        self, person_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update or create a person in DynamoDB.
        """
        try:
            # Prepare person item
            item = {"PK": f"PERSON#{person_id}", "SK": "DETAILS", "Type": "Person"}

            # Handle name
            if "name" in updates:
                item["Name"] = updates["name"]
            elif not await self.get_person(person_id):
                # Name is required for new records
                raise HTTPException(
                    status_code=400, detail="Name is required for new person records"
                )

            # Handle status and metadata
            if updates.get("status") == "deceased":
                death_date = updates.get("metadata", {}).get("DeathDate", "")
                if death_date:
                    item["DeathDate"] = death_date

            # Handle other metadata
            if updates.get("metadata"):
                for key, value in updates["metadata"].items():
                    if key != "DeathDate":  # Already handled above
                        item[key] = value

            # Create/Update person record
            self.table.put_item(Item=item)

            # Get the updated person to return
            updated_person = await self.get_person(person_id)
            if not updated_person:
                raise HTTPException(
                    status_code=500, detail="Failed to retrieve updated person"
                )
            return updated_person

        except HTTPException:
            raise
        except Exception as e:
            print(f"Error updating person: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to update/create person"
            )
