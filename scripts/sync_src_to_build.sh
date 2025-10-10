#!/bin/bash
# Helper script to sync source code changes to build directory
# Use this after making changes to src/ when you can't run the full rebuild command

set -e

echo "🔄 Syncing source code from src/ to build/services/framework/pipelines/repo_src/"

# Sync the entire src directory
rsync -av --delete \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  src/ build/services/framework/pipelines/repo_src/

echo "✅ Source code synced successfully!"
echo ""
echo "Now restarting pipelines service..."
/opt/podman/bin/podman restart pipelines

echo ""
echo "✅ Done! Your code changes are now live in the container."
