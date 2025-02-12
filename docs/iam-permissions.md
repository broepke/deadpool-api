# IAM Permissions Required

## Lambda Function Role (Deadpool-app-role)

The Lambda function requires the following IAM permissions to operate correctly:

### DynamoDB Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/Deadpool"
        }
    ]
}
```

### SNS Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Subscribe",
                "sns:Unsubscribe",
                "sns:ListSubscriptionsByTopic",
                "sns:GetSubscriptionAttributes",
                "sns:SetSubscriptionAttributes"
            ],
            "Resource": "arn:aws:sns:us-east-1:222975130657:deadpool-death-notifications-dev"
        }
    ]
}
```

Note: For SMS messaging, we need two separate statements:
1. A statement with `sns:Publish` and `Resource: "*"` for sending SMS messages to phone numbers
2. A statement with topic-specific permissions for managing subscriptions

## How to Update the IAM Role

1. Go to the AWS IAM Console
2. Find the role "Deadpool-app-role-3xfmpboz"
3. Add a new inline policy or attach the AWS managed policy "AWSLambdaSNSPublishPolicyExecute"
4. If creating an inline policy, use the SNS permissions JSON above
5. Save the changes

## Notes
- The `sns:Publish` permission with Resource "*" is required for sending SMS messages directly to phone numbers
- The specific Topic ARN permissions are needed for managing notification subscriptions
- Consider using AWS Organizations SCPs or resource-based policies for additional security controls