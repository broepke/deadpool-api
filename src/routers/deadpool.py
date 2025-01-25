from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/api/v1/deadpool",
    tags=["deadpool"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def get_deadpool_data():
    """
    Get Deadpool data. This is a placeholder that will be implemented
    to fetch data from DynamoDB in production.
    """
    return {
        "message": "Deadpool data endpoint",
        "data": []
    }
