#!/bin/bash

# Exit on error
set -e

echo "🧹 Cleaning up previous deployment artifacts..."
rm -rf package lambda_function.zip lvenv

echo "🐍 Creating virtual environment..."
python3.13 -m venv lvenv
source lvenv/bin/activate

echo "📦 Creating package directory..."
mkdir -p package

echo "📥 Installing base dependencies..."
pip install --upgrade pip wheel setuptools

echo "📥 Installing Lambda dependencies..."
pip install \
    --platform manylinux2014_aarch64 \
    --implementation cp \
    --python-version 3.13 \
    --only-binary=:all: \
    --target ./package \
    -r requirements-lambda.txt

echo "📂 Adding source files..."
cp -r src package/
cp lambda_function.py package/

echo "🗜️ Creating deployment package..."
cd package && zip -r ../lambda_function.zip . && cd ..

echo "🧹 Cleaning up build artifacts..."
deactivate
rm -rf lvenv package

echo "🚀 Deploying to AWS Lambda..."
# Adding --no-cli-pager to prevent interactive paging that requires pressing Q to exit
aws lambda update-function-code --function-name Deadpool-app --zip-file fileb://lambda_function.zip --no-cli-pager --output json

echo "✅ Deployment complete!"