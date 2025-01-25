import boto3
from typing import List, Optional, Dict, Any
from decimal import Decimal

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
            print(f"No player info extracted from draft orders")
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

    async def get_deadpool_entries(self) -> List[Dict[str, Any]]:
        """
        Get all deadpool entries from DynamoDB.
        """
        params = {
            'FilterExpression': 'SK = :details',
            'ExpressionAttributeValues': {':details': 'DETAILS'}
        }
        response = self.table.scan(**params)
        items = response.get('Items', [])
        return [self._transform_person(item) for item in items]
