# Deployment Guide for Subdomain Enumeration API

## Quick Start - Railway (Recommended)

Railway is the easiest option with WebSocket support and a free tier.

### Steps:

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. **Deploy on Railway:**
   - Go to https://railway.app
   - Click "Start a New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway will auto-detect Python and deploy

3. **Access your API:**
   - HTTP: `https://your-app.railway.app`
   - WebSocket: `wss://your-app.railway.app/ws/enumerate`

### Environment Variables (Optional):
- None required for basic setup
- Add custom wordlists to the repo if needed

---

## Alternative: Render

1. **Push to GitHub** (same as above)

2. **Deploy on Render:**
   - Go to https://render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Render will use `render.yaml` automatically

3. **Access:**
   - HTTP: `https://your-app.onrender.com`
   - WebSocket: `wss://your-app.onrender.com/ws/enumerate`

---

## Alternative: Fly.io

1. **Install Fly CLI:**
   ```bash
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Login and Deploy:**
   ```bash
   fly auth login
   fly launch
   fly deploy
   ```

3. **Access:**
   - HTTP: `https://your-app.fly.dev`
   - WebSocket: `wss://your-app.fly.dev/ws/enumerate`

---

## Connecting from React

Once deployed, update your React app to use the production URL:

```javascript
// Development
const WS_URL = 'ws://localhost:8000/ws/enumerate';

// Production
const WS_URL = 'wss://your-app.railway.app/ws/enumerate';

// Or use environment variable
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/enumerate';
```

---

## CORS Configuration

The API is already configured to allow all origins (`allow_origins=["*"]`).

For production, update `api.py` to restrict origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-react-app.vercel.app",
        "https://your-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Files Included

- ✅ `Procfile` - For Railway/Heroku
- ✅ `render.yaml` - For Render
- ✅ `requirements.txt` - Python dependencies

---

## Cost Comparison

| Platform | Free Tier | WebSocket Support | Ease of Use |
|----------|-----------|-------------------|-------------|
| Railway | 500 hours/month | ✅ Yes | ⭐⭐⭐⭐⭐ |
| Render | 750 hours/month | ✅ Yes | ⭐⭐⭐⭐⭐ |
| Fly.io | 3 VMs free | ✅ Yes | ⭐⭐⭐⭐ |
| DigitalOcean | $5/month | ✅ Yes | ⭐⭐⭐ |

**Recommendation:** Start with Railway or Render for the easiest deployment.
