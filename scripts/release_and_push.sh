#!/bin/bash
# ============================================
# EntropyGuard Release & Push Script
# ============================================
# This script performs repository cleanup and pushes changes to remote
# Usage: ./scripts/release_and_push.sh

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${GREEN}🚀 EntropyGuard Release & Push Script${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Step 1: Clean local temporary files
echo -e "${YELLOW}📦 Step 1: Cleaning local temporary files...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
echo -e "${GREEN}✅ Cleanup complete${NC}"
echo ""

# Step 2: Check git status
echo -e "${YELLOW}📊 Step 2: Checking git status...${NC}"
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${GREEN}✅ Changes detected${NC}"
    git status --short
else
    echo -e "${YELLOW}⚠️  No changes detected. Nothing to commit.${NC}"
    exit 0
fi
echo ""

# Step 3: Add all changes
echo -e "${YELLOW}📝 Step 3: Staging changes...${NC}"
git add .
echo -e "${GREEN}✅ Changes staged${NC}"
echo ""

# Step 4: Create commit
echo -e "${YELLOW}💾 Step 4: Creating commit...${NC}"
COMMIT_MSG="chore: repository cleanup & docs overhaul for v1.22.0"
git commit -m "$COMMIT_MSG"
echo -e "${GREEN}✅ Commit created: ${COMMIT_MSG}${NC}"
echo ""

# Step 5: Push to remote
echo -e "${YELLOW}🚀 Step 5: Pushing to remote...${NC}"
read -p "Push to 'origin main'? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin main
    echo -e "${GREEN}✅ Push complete${NC}"
else
    echo -e "${YELLOW}⚠️  Push cancelled by user${NC}"
    exit 0
fi
echo ""

echo -e "${GREEN}🎉 Release & push complete!${NC}"
echo -e "${GREEN}=====================================${NC}"



