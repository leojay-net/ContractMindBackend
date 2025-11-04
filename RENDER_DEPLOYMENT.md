# Render Deployment Fix

## Issue
```
ERROR: Error loading ASGI app. Could not import module "main".
```

## Root Cause
The start command was using `uvicorn main:app` but the FastAPI app is located at `app/main.py`, so it needs to be `uvicorn app.main:app`.

## Solution

### Quick Fix (Render Dashboard)

1. Go to your Render service dashboard
2. Click on your service
3. Go to **Settings** → **Build & Deploy**
4. Update the **Start Command** to:
   ```bash
   poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Click **Save Changes**
6. Manually trigger a new deploy

### Recommended: Update Environment Variables

In Render Dashboard → **Environment**, add these variables:

**Required:**
```bash
# Database (from your .env)
user=postgres.pzfmtujykgkrkdddxxdi
password=cg1PDLjZR1HQJGp2
host=aws-1-eu-west-1.pooler.supabase.com
port=5432
dbname=postgres

# Or as single DATABASE_URL
DATABASE_URL=postgresql://postgres.pzfmtujykgkrkdddxxdi:cg1PDLjZR1HQJGp2@aws-1-eu-west-1.pooler.supabase.com:5432/postgres

# Blockchain
SOMNIA_RPC_URL=https://dream-rpc.somnia.network
CHAIN_ID=50312
AGENT_REGISTRY_ADDRESS=0x318FFd8Fc398a3639Faa837307Ffdd0b9E1017c9
CONTRACT_MIND_HUB_ADDRESS=0x8244777FAe8F2f4AE50875405AFb34E10164C027

# AI Service
GEMINI_API_KEY=AIzaSyCSasUBkFy5C5CIO0rHekj5xUccOX2acKo
GEMINI_MODEL=gemini-2.0-flash
DEFAULT_LLM_PROVIDER=gemini

# App Config
ENVIRONMENT=production
DEBUG=false
```

### Alternative: Using render.yaml (Infrastructure as Code)

A `render.yaml` file has been created in your backend directory. To use it:

1. Push the `render.yaml` to your repository
2. In Render Dashboard:
   - Click **New +** → **Blueprint**
   - Connect your repository
   - Select the `render.yaml` file
3. Render will automatically configure everything

## Build & Start Commands

### For Manual Configuration:

**Build Command:**
```bash
pip install poetry && poetry install --no-dev
```

**Start Command:**
```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Important Notes:

1. **Always use `$PORT`** - Render provides the port via environment variable
2. **Module path is `app.main:app`** - Not just `main:app`
3. **Use poetry run** - To ensure correct virtual environment
4. **No dev dependencies** - Use `--no-dev` flag for faster builds

## Verify Deployment

Once deployed, test your endpoints:

```bash
# Health check
curl https://your-app.onrender.com/health

# Get agents
curl https://your-app.onrender.com/api/v1/agents

# Check docs
open https://your-app.onrender.com/docs
```

## Common Issues

### Issue: Module not found
**Fix:** Ensure start command is `app.main:app` not `main:app`

### Issue: Port binding failed
**Fix:** Use `$PORT` environment variable, not hardcoded port

### Issue: Database connection failed
**Fix:** Check DATABASE_URL or individual db credentials in environment variables

### Issue: Poetry not found
**Fix:** Add `pip install poetry` to build command

## Update Frontend

After successful backend deployment, update frontend `.env`:

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

## Files Created

- ✅ `render.yaml` - Automated deployment configuration
- ✅ `render-build.sh` - Build script (optional)
- ✅ This deployment guide

## Next Steps

1. Update start command in Render Dashboard
2. Add environment variables
3. Trigger new deployment
4. Test endpoints
5. Update frontend API URL
6. Deploy frontend

---

**Deployment Status:** 🚀 Ready to deploy with correct configuration
