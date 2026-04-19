---
title: Telegram Auto Filter Bot
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Telegram Auto Filter Bot

A high-performance Pyrogram Telegram bot optimized for low-latency file serving at scale (6000+ groups, 200K+ users).

## Deployment on Hugging Face Spaces

### Step 1: Create a New Space
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose **Docker** as the SDK
3. Set visibility to **Private** (recommended for security)

### Step 2: Set Environment Variables
Go to **Settings → Variables and Secrets** and add:

| Secret Name | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram Bot Token from @BotFather |
| `API_ID` | ✅ | Get from https://my.telegram.org |
| `API_HASH` | ✅ | Get from https://my.telegram.org |
| `DATABASE_URI` | ✅ | MongoDB connection string |
| `ADMINS` | ✅ | Space-separated admin user IDs |
| `CHANNELS` | ✅ | Space-separated channel IDs for indexing |
| `LOG_CHANNEL` | ✅ | Channel ID for bot logs |
| `AUTH_CHANNEL` | ❌ | Force subscribe channel ID |
| `REQ_CHANNEL_1` | ❌ | Join request channel 1 ID |
| `REQ_CHANNEL_2` | ❌ | Join request channel 2 ID |
| `FILE_STORE_CHANNEL` | ❌ | File store channel ID |
| `DATABASE_NAME` | ❌ | MongoDB database name (default: Cluster0) |

### Step 3: Push Code
```bash
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
git push space main
```

### Keep Alive
Use [cron-job.org](https://cron-job.org) to ping your Space URL every 5 minutes to prevent HF from sleeping the container.
