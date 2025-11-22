# Railway Deployment Guide

This guide will help you deploy your FastAPI backend to Railway.

## Prerequisites

- GitHub account with your code pushed
- Railway account (sign up at https://railway.app)

## Step 1: Deploy to Railway

### 1.1 Create a New Project

1. Go to [Railway](https://railway.app) and sign in with GitHub
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Find and select your `accounts-payable-project` repository
5. Click "Deploy Now"

### 1.2 Configure the Service

1. Railway will auto-detect it's a Python app
2. Click on your service to open settings
3. Go to the **Settings** tab
4. Set the following:
   - **Root Directory**: `backend`
   - **Start Command**: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     - Or use: `bash start.sh` (if you prefer the script)

### 1.3 Add PostgreSQL Database

1. In your Railway project, click "+ New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically:
   - Create a PostgreSQL database
   - Set the `DATABASE_URL` environment variable in your service
   - Link it to your web service

### 1.4 Configure Environment Variables

Go to your service → **Variables** tab and add:

**Required:**
- `DATABASE_URL` - Automatically set by Railway when you add PostgreSQL (don't override this)

**Optional (but recommended):**
- `DEEPSEEK_OCR_API_URL` - Your OCR API endpoint (default: `https://api.deepseek.com/ocr`)
- `DEEPSEEK_OCR_API_KEY` - Your OCR API key (if required)
- `CORS_ORIGINS` - Comma-separated list of allowed origins (default includes localhost and Vercel)

**Storage (S3-compatible, optional):**
- `STORAGE_ENDPOINT_URL` - S3 endpoint URL
- `STORAGE_ACCESS_KEY_ID` - S3 access key
- `STORAGE_SECRET_ACCESS_KEY` - S3 secret key
- `STORAGE_BUCKET_NAME` - S3 bucket name (default: `ap-invoices`)
- `STORAGE_REGION` - S3 region (default: `us-east-1`)

**Matching Configuration:**
- `MATCHING_TOLERANCE` - Matching tolerance for amounts (default: `0.01` = 1%)

### 1.5 Deploy

1. Railway will automatically deploy when you:
   - Push to your GitHub repository, or
   - Click "Redeploy" in the Railway dashboard
2. Wait for the deployment to complete (usually 2-3 minutes)
3. Check the **Deployments** tab for build logs

### 1.6 Get Your Backend URL

1. Go to your service → **Settings** tab
2. Scroll down to **Domains**
3. Railway provides a default domain like: `https://your-service-name.up.railway.app`
4. You can also add a custom domain if you have one
5. **Copy this URL** - you'll need it for your Vercel frontend deployment

## Step 2: Verify Deployment

1. Visit your backend URL: `https://your-service-name.up.railway.app`
2. You should see: `{"message": "Accounts Payable Platform API", "version": "1.0.0"}`
3. Test the health endpoint: `https://your-service-name.up.railway.app/health`
4. Should return: `{"status": "healthy"}`

## Step 3: Test API Endpoints

You can test your API using curl or a tool like Postman:

```bash
# Health check
curl https://your-service-name.up.railway.app/health

# List invoices
curl https://your-service-name.up.railway.app/api/invoices

# List vendors
curl https://your-service-name.up.railway.app/api/vendors
```

## Troubleshooting

### Build Fails

- Check the **Deployments** tab for error logs
- Ensure all dependencies are in `requirements.txt`
- Verify Python version in `runtime.txt` matches Railway's supported versions

### Database Connection Issues

- Verify `DATABASE_URL` is set correctly (Railway sets this automatically)
- Check that PostgreSQL service is running
- Ensure migrations ran successfully (check deployment logs)

### Server Won't Start

- Check that the start command is correct
- Verify the port is set to `$PORT` (Railway provides this)
- Check logs in the Railway dashboard

### CORS Errors

- Your backend is already configured to allow Vercel domains
- If you have a custom domain, add it to `CORS_ORIGINS` environment variable
- Format: `http://localhost:3000,https://your-custom-domain.com`

## Next Steps

After your backend is deployed:

1. **Copy your backend URL** (e.g., `https://your-service-name.up.railway.app`)
2. **Deploy frontend to Vercel** (see `DEPLOYMENT.md`)
3. **Set environment variable in Vercel**: `NEXT_PUBLIC_API_URL=https://your-service-name.up.railway.app`
4. **Test the full application**

## Railway Free Tier Limits

- 500 hours of usage per month
- $5 credit per month
- Suitable for development and small projects
- Upgrade for production workloads

## Useful Railway Commands (CLI)

If you install Railway CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# View logs
railway logs

# Open in browser
railway open
```

