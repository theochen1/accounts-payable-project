#!/bin/bash

# Script to push code to GitHub
# Replace YOUR_USERNAME and YOUR_REPO_NAME with your actual values

echo "🚀 Pushing Accounts Payable Platform to GitHub..."
echo ""
echo "⚠️  IMPORTANT: Before running this script, make sure you:"
echo "   1. Created a repository on GitHub"
echo "   2. Replaced YOUR_USERNAME and YOUR_REPO_NAME below"
echo ""
read -p "Have you created the GitHub repository? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please create a repository on GitHub first, then run this script again."
    exit 1
fi

# Replace these with your actual values
GITHUB_USERNAME="YOUR_USERNAME"
REPO_NAME="YOUR_REPO_NAME"

# Rename branch to main (if not already)
git branch -M main

# Add remote (remove if exists first)
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push -u origin main

echo ""
echo "✅ Successfully pushed to GitHub!"
echo ""
echo "Next steps:"
echo "1. Go to https://vercel.com and sign in"
echo "2. Click 'Add New...' → 'Project'"
echo "3. Import your GitHub repository"
echo "4. Set Root Directory to 'frontend'"
echo "5. Add environment variable: NEXT_PUBLIC_API_URL = your-backend-url"
echo "6. Click Deploy"
echo ""
echo "📖 See DEPLOYMENT.md for detailed instructions"

