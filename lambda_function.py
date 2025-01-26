from mangum import Mangum
from src.main import app

# Create and export the Lambda handler with API Gateway stage configuration
lambda_handler = Mangum(app, lifespan="off", api_gateway_base_path="/default")