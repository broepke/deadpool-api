#!/bin/bash

# Script to bulk load data into DynamoDB

# Function to load all batch files for a given section
load_section() {
    local section=$1
    for batch_file in data/dynamodb_json_files/${section}_batch_*.json; do
        if [ -f "$batch_file" ]; then
            echo "Loading $batch_file..."
            aws dynamodb batch-write-item --no-cli-pager --cli-input-json "{\"RequestItems\": $(cat $batch_file)}"
        fi
    done
}

# Load each section
echo "Loading Players..."
load_section "Players"

echo "Loading People..."
load_section "People"

echo "Loading DraftOrder..."
load_section "DraftOrder"

echo "Loading PlayerPicks..."
load_section "PlayerPicks"
