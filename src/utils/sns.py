import boto3
import random
from typing import Optional
from fastapi import HTTPException
from botocore.exceptions import ClientError
from ..utils.logging import cwlogger

def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return str(random.randint(100000, 999999))

def send_verification_code(phone_number: str, code: str) -> str:
    """
    Send verification code via SNS.
    
    Args:
        phone_number: Phone number in E.164 format (+1234567890)
        code: 6-digit verification code
        
    Returns:
        str: SNS message ID
        
    Raises:
        HTTPException: With appropriate status code and message for different error types
    """
    try:
        sns = boto3.client('sns')
        
        # Send the verification code
        response = sns.publish(
            PhoneNumber=phone_number,
            Message=f"Your Deadpool verification code is: {code}\nThis code will expire in 10 minutes.",
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        
        message_id = response['MessageId']
        cwlogger.info(
            "SMS_VERIFICATION_SENT",
            "Successfully sent verification code",
            data={
                "phone_number": phone_number,
                "message_id": message_id
            }
        )
        
        return message_id
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        if error_code == 'AuthorizationError':
            cwlogger.error(
                "SMS_VERIFICATION_ERROR",
                "Missing SNS permissions",
                error=e,
                data={
                    "phone_number": phone_number,
                    "error_code": error_code
                }
            )
            raise HTTPException(
                status_code=500,
                detail="Server is not properly configured to send SMS messages. Please contact support."
            )
        elif error_code == 'InvalidParameter':
            cwlogger.error(
                "SMS_VERIFICATION_ERROR",
                "Invalid phone number format",
                error=e,
                data={
                    "phone_number": phone_number,
                    "error_code": error_code
                }
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number format. Must be in E.164 format (e.g., +12345678900)"
            )
        else:
            cwlogger.error(
                "SMS_VERIFICATION_ERROR",
                "Error sending verification code",
                error=e,
                data={
                    "phone_number": phone_number,
                    "error_code": error_code
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send verification code: {error_message}"
            )

def manage_sns_subscription(phone_number: str, topic_arn: str, subscribe: bool = True) -> Optional[str]:
    """
    Manage SNS topic subscription for a phone number.
    
    Args:
        phone_number: Phone number in E.164 format (+1234567890)
        topic_arn: ARN of the SNS topic to subscribe to
        subscribe: True to subscribe, False to unsubscribe
        
    Returns:
        Optional[str]: Subscription ARN if subscribing, None if unsubscribing
        
    Raises:
        ClientError: If there's an error managing the subscription
    """
    try:
        sns = boto3.client('sns')
        
        if subscribe:
            # Subscribe the phone number to the topic
            response = sns.subscribe(
                TopicArn=topic_arn,
                Protocol='sms',
                Endpoint=phone_number
            )
            
            subscription_arn = response['SubscriptionArn']
            cwlogger.info(
                "SNS_SUBSCRIPTION_CREATED",
                "Successfully subscribed phone number to notifications",
                data={
                    "phone_number": phone_number,
                    "subscription_arn": subscription_arn
                }
            )
            
            return subscription_arn
            
        else:
            # Get all subscriptions for the topic
            paginator = sns.get_paginator('list_subscriptions_by_topic')
            for page in paginator.paginate(TopicArn=topic_arn):
                for sub in page['Subscriptions']:
                    if sub['Protocol'] == 'sms' and sub['Endpoint'] == phone_number:
                        # Unsubscribe the phone number
                        sns.unsubscribe(SubscriptionArn=sub['SubscriptionArn'])
                        
                        cwlogger.info(
                            "SNS_SUBSCRIPTION_REMOVED",
                            "Successfully unsubscribed phone number from notifications",
                            data={
                                "phone_number": phone_number,
                                "subscription_arn": sub['SubscriptionArn']
                            }
                        )
                        
                        return None
                        
            return None
            
    except ClientError as e:
        cwlogger.error(
            "SNS_SUBSCRIPTION_ERROR",
            "Error managing subscription",
            error=e,
            data={
                "phone_number": phone_number,
                "subscribe": subscribe
            }
        )
        raise

def validate_phone_number(phone_number: str) -> bool:
    """
    Validate phone number format (E.164).
    Must start with + followed by country code and number.
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not phone_number:
        return False
        
    # Basic E.164 format validation
    # Should start with + followed by 1-15 digits
    if not phone_number.startswith('+'):
        return False
        
    digits = phone_number[1:]  # Remove the +
    if not digits.isdigit():
        return False
        
    # E.164 numbers should be between 7 and 15 digits
    if len(digits) < 7 or len(digits) > 15:
        return False
        
    return True