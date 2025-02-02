#!/bin/bash

# Script to bulk load 2025 picks data into DynamoDB

# Function to load all batch files for 2025 picks
load_2025_picks() {
    for batch_file in data/dynamodb_json_files/Picks2025_batch_*.json; do
        if [ -f "$batch_file" ]; then
            echo "Loading $batch_file..."
            aws dynamodb batch-write-item --no-cli-pager --cli-input-json "{\"RequestItems\": $(cat $batch_file)}"
        fi
    done
}

echo "Loading 2025 Picks..."
load_2025_picks