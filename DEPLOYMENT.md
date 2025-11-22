# Deployment Guide

This guide will walk you through deploying your Accounts Payable Platform to GitHub and Vercel.

## Step 1: Push Code to GitHub

### 1.1 Create a GitHub Repository

1. Go to [GitHub](https://github.com) and sign in
2. Click the "+" icon in the top right corner
3. Select "New repository"
4. Name your repository (e.g., `accounts-payable-platform`)
5. Choose **Public** or **Private** (your choice)
6. **DO NOT** initialize with README, .gitignore, or license (we already have these)
7. Click "Create repository"

### 1.2 Push Your Code

Run these commands in your terminal (replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repository name):

```bash
cd "/Users/theochen/Desktop/Accounts Payable Project"

# Rename branch to main (if needed)
git branch -M main

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push your code
git push -u origin main
```

**Alternative: Using SSH (if you have SSH keys set up):**
```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

## Step 2: Deploy to Vercel

### 2.1 Connect Repository to Vercel

1. Go to [Vercel](https://vercel.com) and sign in (or create an account)
2. Click "Add New..." → "Project"
3. Import your GitHub repository:
   - Click "Import Git Repository"
   - Find and select your repository
   - Click "Import"

### 2.2 Configure Project Settings

In the Vercel project configuration:

1. **Framework Preset**: Should auto-detect as "Next.js"
2. **Root Directory**: Set to `frontend` (click "Edit" next to Root Directory)
3. **Build Command**: `npm run build` (should auto-populate)
4. **Output Directory**: `.next` (should auto-populate)
5. **Install Command**: `npm install` (should auto-populate)

### 2.3 Configure Environment Variables

Before deploying, add your environment variable:

1. In the Vercel project settings, go to **Settings** → **Environment Variables**
2. Add a new environment variable:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: Your backend API URL (e.g., `https://your-backend.railway.app` or `https://your-backend.render.com`)
   - **Environment**: Select all (Production, Preview, Development)
3. Click "Save"

**Important**: 
- If your backend is not yet deployed, you can use a placeholder URL and update it later
- Make sure your backend CORS settings allow requests from your Vercel domain
- The backend URL should NOT have a trailing slash

### 2.4 Deploy

1. Click "Deploy" button
2. Vercel will:
   - Install dependencies
   - Build your Next.js application
   - Deploy it to a production URL
3. Wait for the deployment to complete (usually 1-2 minutes)

### 2.5 Access Your Deployed App

Once deployment is complete:
- You'll get a production URL like: `https://your-project.vercel.app`
- You can also set up a custom domain in Vercel settings

## Step 3: Update Backend CORS (If Needed)

Make sure your backend allows requests from your Vercel domain. In your backend code (`backend/app/main.py`), ensure CORS is configured:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://your-project.vercel.app",  # Your Vercel domain
        "https://*.vercel.app",  # All Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Step 4: Verify Deployment

1. Visit your Vercel deployment URL
2. Check the browser console for any errors
3. Test the application functionality
4. Verify API calls are going to the correct backend URL

## Troubleshooting

### Build Fails
- Check the build logs in Vercel dashboard
- Ensure all dependencies are in `package.json`
- Verify Node.js version compatibility

### API Calls Fail
- Check that `NEXT_PUBLIC_API_URL` is set correctly
- Verify backend CORS settings
- Check backend logs for errors
- Ensure backend is deployed and accessible

### Environment Variables Not Working
- Make sure variable name starts with `NEXT_PUBLIC_` for client-side access
- Redeploy after adding environment variables
- Check that variables are set for the correct environment (Production/Preview/Development)

## Next Steps

- Set up automatic deployments (Vercel does this by default on git push)
- Configure custom domain (optional)
- Set up preview deployments for pull requests
- Deploy your backend to Railway, Render, or another platform
- Set up monitoring and error tracking

