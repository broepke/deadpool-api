import boto3
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException

class DynamoDBClient:
    """
    Utility class for DynamoDB operations.
    """
    def __init__(self, table_name: str = "Deadpool"):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    def _transform_person(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a DynamoDB person item to match our API model.
        """
        try:
            # Extract UUID from PK (format: PERSON#uuid)
            person_id = item.get('PK', '').split('#')[1]
            
            # Handle both 'Name' and 'name' cases
            name = item.get('Name') or item.get('name')
            if not name:
                raise ValueError(f"No name found in item: {item}")
            
            # Convert any Decimal types to int/float for JSON serialization
            metadata = {}
            for key, value in item.items():
                if key.lower() not in ['pk', 'sk', 'name']:
                    if isinstance(value, Decimal):
                        metadata[key] = int(value) if value % 1 == 0 else float(value)
                    else:
                        metadata[key] = value

            return {
                "id": person_id,
                "name": name,
                "status": "deceased" if "DeathDate" in item else "active",
                "metadata": metadata
            }
        except Exception as e:
            print(f"Error transforming item {item}: {str(e)}")
            # Return a minimal valid object to prevent API errors
            return {
                "id": "unknown",
                "name": "Unknown Person",
                "status": "unknown",
                "metadata": {}
            }

    async def get_players(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get players from DynamoDB, optionally filtered by year.
        """
        # Default to current year if not specified
        target_year = year if year else 2024
        
        # First get draft order records for the year
        params = {
            'KeyConditionExpression': 'PK = :year_key',
            'ExpressionAttributeValues': {
                ':year_key': f'YEAR#{target_year}'
            }
        }
        
        # Use query instead of scan since we're using the partition key
        response = self.table.query(**params)
        draft_orders = response.get('Items', [])
        
        if not draft_orders:
            print(f"No draft orders found for year {target_year}")
            return []
            
        # Extract player IDs and draft orders
        player_info = []
        for order in draft_orders:
            # SK format: ORDER#{draft_order}#PLAYER#{player_id}
            parts = order['SK'].split('#')
            if len(parts) >= 4:
                draft_order = int(parts[1])
                player_id = parts[3]
                player_info.append((player_id, draft_order))
        
        if not player_info:
            print("No player info extracted from draft orders")
            return []
            
        # Get player details
        transformed_players = []
        for player_id, draft_order in player_info:
            try:
                # Get player details
                player_response = self.table.get_item(
                    Key={
                        'PK': f'PLAYER#{player_id}',
                        'SK': 'DETAILS'
                    }
                )
                player = player_response.get('Item')
                
                if not player:
                    print(f"No details found for player {player_id}")
                    continue
                
                # Transform player data
                transformed = {
                    "id": player_id,
                    "name": f"{player.get('FirstName', '')} {player.get('LastName', '')}".strip(),
                    "draft_order": draft_order,
                    "year": target_year,
                    "metadata": {
                        k: (int(v) if isinstance(v, Decimal) and v % 1 == 0 else 
                           float(v) if isinstance(v, Decimal) else v)
                        for k, v in player.items()
                        if k not in ['PK', 'SK', 'FirstName', 'LastName']
                    }
                }
                transformed_players.append(transformed)
            except Exception as e:
                print(f"Error processing player {player_id}: {str(e)}")
        
        # Sort by draft order
        transformed_players.sort(key=lambda x: x['draft_order'])
        return transformed_players

    async def get_people(self) -> List[Dict[str, Any]]:
        """
        Get all people from DynamoDB.
        """
        params = {
            'FilterExpression': 'SK = :details',
            'ExpressionAttributeValues': {':details': 'DETAILS'}
        }
        
        response = self.table.scan(**params)
        items = response.get('Items', [])
        return [self._transform_person(item) for item in items]

    async def get_player(self, player_id: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get a specific player from DynamoDB.
        """
        # Get player details
        try:
            # Handle case where player_id might already include the prefix
            pk = player_id if player_id.startswith('PLAYER#') else f'PLAYER#{player_id}'
            
            player_response = self.table.get_item(
                Key={
                    'PK': pk,
                    'SK': 'DETAILS'
                }
            )
            player = player_response.get('Item')
            
            if not player:
                # Try with the raw ID if it had the prefix, or with the prefix if it didn't
                alternate_pk = player_id.replace('PLAYER#', '') if player_id.startswith('PLAYER#') else f'PLAYER#{player_id}'
                player_response = self.table.get_item(
                    Key={
                        'PK': alternate_pk,
                        'SK': 'DETAILS'
                    }
                )
                player = player_response.get('Item')
                if not player:
                    return None
            
            # Get draft order for the player
            target_year = year if year else 2024
            # Extract clean player ID (without PLAYER# prefix) for draft order lookup
            clean_player_id = player_id.replace('PLAYER#', '')
            
            # Use the same query approach as get_players method
            year_response = self.table.query(
                KeyConditionExpression='PK = :year_key',
                ExpressionAttributeValues={
                    ':year_key': f'YEAR#{target_year}'
                }
            )
            
            # Process all draft orders to find the matching player
            draft_order = None
            for order in year_response.get('Items', []):
                # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                parts = order['SK'].split('#')
                if len(parts) >= 4:
                    order_player_id = parts[3]
                    if order_player_id == clean_player_id:
                        draft_order = int(parts[1])
                        break
            
            if draft_order is None:
                return None
                
            # Transform player data
            return {
                "id": clean_player_id,
                "name": f"{player.get('FirstName', '')} {player.get('LastName', '')}".strip(),
                "draft_order": draft_order,
                "year": target_year,
                "metadata": {
                    k: (int(v) if isinstance(v, Decimal) and v % 1 == 0 else 
                       float(v) if isinstance(v, Decimal) else v)
                    for k, v in player.items()
                    if k not in ['PK', 'SK', 'FirstName', 'LastName']
                }
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
                Key={
                    'PK': f'PERSON#{person_id}',
                    'SK': 'DETAILS'
                }
            )
            item = response.get('Item')
            if not item:
                return None
            return self._transform_person(item)
        except Exception as e:
            print(f"Error getting person {person_id}: {str(e)}")
            return None

    async def update_player(self, player_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a player in DynamoDB.
        """
        # Prepare update expression and attribute values
        update_expr = ['SET']
        expr_attr_values = {}
        expr_attr_names = {}
        
        # Handle name update by splitting into FirstName and LastName
        if 'name' in updates:
            names = updates['name'].split(' ', 1)
            if len(names) == 2:
                update_expr.append('#fn = :fn, #ln = :ln')
                expr_attr_values[':fn'] = names[0]
                expr_attr_values[':ln'] = names[1]
                expr_attr_names['#fn'] = 'FirstName'
                expr_attr_names['#ln'] = 'LastName'

        # Handle metadata updates
        if updates.get('metadata'):
            for key, value in updates['metadata'].items():
                update_expr.append(f'#{key} = :{key}')
                expr_attr_values[f':{key}'] = value
                expr_attr_names[f'#{key}'] = key

        # Handle draft order update
        if 'draft_order' in updates and 'year' in updates:
            # Update the draft order record
            year_key = f'YEAR#{updates["year"]}'
            order_sk = f'ORDER#{updates["draft_order"]}#PLAYER#{player_id}'
            
            try:
                self.table.put_item(
                    Item={
                        'PK': year_key,
                        'SK': order_sk,
                        'Type': 'DraftOrder'
                    }
                )
            except Exception as e:
                print(f"Error updating draft order: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to update draft order")

        # Update player details if we have any attribute updates
        if len(update_expr) > 1:
            try:
                response = self.table.update_item(
                    Key={
                        'PK': f'PLAYER#{player_id}',
                        'SK': 'DETAILS'
                    },
                    UpdateExpression=' '.join(update_expr),
                    ExpressionAttributeValues=expr_attr_values,
                    ExpressionAttributeNames=expr_attr_names,
                    ReturnValues='ALL_NEW'
                )
                updated_item = response.get('Attributes', {})
            except Exception as e:
                print(f"Error updating player: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to update player")

        # Get the updated player to return
        return (await self.get_players(updates.get('year')))[0]

    async def get_draft_order(self, year: Optional[int] = None, player_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get draft order records from DynamoDB, optionally filtered by year and/or player.
        """
        draft_orders = []
        
        if year:
            # Query by specific year
            params = {
                'KeyConditionExpression': 'PK = :year_key',
                'ExpressionAttributeValues': {
                    ':year_key': f'YEAR#{year}'
                }
            }
            
            if player_id:
                # Add player filter if specified
                params['FilterExpression'] = 'contains(SK, :player_id)'
                params['ExpressionAttributeValues'][':player_id'] = player_id
            
            response = self.table.query(**params)
            items = response.get('Items', [])
            
            for item in items:
                # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                parts = item['SK'].split('#')
                if len(parts) >= 4:
                    draft_orders.append({
                        "player_id": parts[3],
                        "draft_order": int(parts[1]),
                        "year": year
                    })
        else:
            # If no year specified, scan all years
            params = {
                'FilterExpression': 'begins_with(PK, :year_prefix)',
                'ExpressionAttributeValues': {
                    ':year_prefix': 'YEAR#'
                }
            }
            
            if player_id:
                # Add player filter if specified
                params['FilterExpression'] += ' and contains(SK, :player_id)'
                params['ExpressionAttributeValues'][':player_id'] = player_id
            
            response = self.table.scan(**params)
            items = response.get('Items', [])
            
            for item in items:
                # Extract year from PK (format: YEAR#yyyy)
                year_str = item['PK'].split('#')[1]
                # SK format: ORDER#{draft_order}#PLAYER#{player_id}
                parts = item['SK'].split('#')
                if len(parts) >= 4:
                    draft_orders.append({
                        "player_id": parts[3],
                        "draft_order": int(parts[1]),
                        "year": int(year_str)
                    })
        
        # Sort by year (descending) and draft order (ascending)
        draft_orders.sort(key=lambda x: (-x['year'], x['draft_order']))
        return draft_orders

    async def update_draft_order(self, player_id: str, year: int, draft_order: int) -> Dict[str, Any]:
        """
        Update a draft order in DynamoDB.
        """
        try:
            # Create new draft order record
            item = {
                'PK': f'YEAR#{year}',
                'SK': f'ORDER#{draft_order}#PLAYER#{player_id}',
                'Type': 'DraftOrder'
            }
            
            self.table.put_item(Item=item)
            
            return {
                "player_id": player_id,
                "draft_order": draft_order,
                "year": year
            }
        except Exception as e:
            print(f"Error updating draft order: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update draft order")

    async def get_player_picks(self, player_id: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all picks for a specific player, optionally filtered by year.
        """
        try:
            params = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {
                    ':pk': f'PLAYER#{player_id}'
                }
            }
            
            # Add year filter if specified
            if year:
                params['KeyConditionExpression'] += ' and begins_with(SK, :sk_prefix)'
                params['ExpressionAttributeValues'][':sk_prefix'] = f'PICK#{year}#'
            else:
                params['FilterExpression'] = 'begins_with(SK, :pick_prefix)'
                params['ExpressionAttributeValues'][':pick_prefix'] = 'PICK#'
            
            response = self.table.query(**params)
            items = response.get('Items', [])
            
            picks = []
            for item in items:
                # SK format: PICK#year#person_id
                parts = item['SK'].split('#')
                if len(parts) >= 3:
                    picks.append({
                        "person_id": parts[2],
                        "year": int(parts[1]),
                        "timestamp": item.get('Timestamp')
                    })
            
            # Sort by timestamp descending (most recent first)
            picks.sort(key=lambda x: x['timestamp'], reverse=True)
            return picks
            
        except Exception as e:
            print(f"Error getting picks for player {player_id}: {str(e)}")
            return []

    async def update_player_pick(self, player_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update or create a player pick in DynamoDB.
        """
        try:
            # Create new pick record with current timestamp
            item = {
                'PK': f'PLAYER#{player_id}',
                'SK': f'PICK#{updates["year"]}#{updates["person_id"]}',
                'Year': updates['year'],
                'PersonID': updates['person_id'],
                'Timestamp': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            
            return {
                "person_id": updates['person_id'],
                "year": updates['year'],
                "timestamp": item['Timestamp']
            }
        except Exception as e:
            print(f"Error updating player pick: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update player pick")

    async def update_person(self, person_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a person in DynamoDB.
        """
        # Prepare update expression and attribute values
        update_expr = ['SET']
        expr_attr_values = {}
        expr_attr_names = {}
        
        # Handle name update
        if 'name' in updates:
            update_expr.append('#name = :name')
            expr_attr_values[':name'] = updates['name']
            expr_attr_names['#name'] = 'Name'

        # Handle status update
        if updates.get('status') == 'deceased':
            update_expr.append('#dd = :dd')
            expr_attr_values[':dd'] = updates.get('metadata', {}).get('DeathDate', '')
            expr_attr_names['#dd'] = 'DeathDate'

        # Handle metadata updates
        if updates.get('metadata'):
            for key, value in updates['metadata'].items():
                if key != 'DeathDate':  # Already handled above
                    update_expr.append(f'#{key} = :{key}')
                    expr_attr_values[f':{key}'] = value
                    expr_attr_names[f'#{key}'] = key

        # Update person if we have any attribute updates
        if len(update_expr) > 1:
            try:
                response = self.table.update_item(
                    Key={
                        'PK': f'PERSON#{person_id}',
                        'SK': 'DETAILS'
                    },
                    UpdateExpression=' '.join(update_expr),
                    ExpressionAttributeValues=expr_attr_values,
                    ExpressionAttributeNames=expr_attr_names,
                    ReturnValues='ALL_NEW'
                )
                updated_item = response.get('Attributes', {})
                return self._transform_person(updated_item)
            except Exception as e:
                print(f"Error updating person: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to update person")
