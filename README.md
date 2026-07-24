# SafeNet

SafeNet is a production-ready Discord moderation platform designed for server security, staff workflows, automoderation, and a FastAPI dashboard backend.

## Features
- Cog-based moderation architecture
- Slash command moderation, warnings, cases, notes, and user profiles
- Ticketing, verification, voice moderation, and role administration
- Modular automoderation with link filtering, spam protection, and content checks
- MongoDB persistence with Redis caching and rate limiting
- FastAPI dashboard API with JWT authentication
- APScheduler heartbeat and presence rotation
- Structured logging and audit persistence

## Installation
1. Clone the repository.
2. Create a virtual environment: `python -m venv .venv`
3. Activate the environment:
   - Linux/macOS: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration
1. Copy `.env.example` to `.env`.
2. Fill in your Discord bot token and MongoDB/Redis connection values.
3. Set dashboard credentials and other runtime options.

## Discord Developer Portal Setup
1. Create an application and bot at https://discord.com/developers.
2. Enable `SERVER MEMBERS INTENT`, `MESSAGE CONTENT INTENT`, and `PRESENCE INTENT`.
3. Copy the bot token into `.env`.
4. Add your bot to servers with the following OAuth scope and permissions:
   - `applications.commands`
   - `bot`
   - `Administrator` (or the specific moderation permissions required)

## Database Setup
- MongoDB: ensure a MongoDB instance is available and update `MONGODB_URI`.
- Redis: ensure Redis is available and update `REDIS_URL`.

## Running the Bot
```bash
python main.py
```

## Dashboard
The FastAPI dashboard runs alongside the bot at `http://<DASHBOARD_HOST>:<DASHBOARD_PORT>`.

## Troubleshooting
- Verify `DISCORD_TOKEN` is set in `.env`.
- Confirm MongoDB and Redis are reachable.
- Check `bot/logs/safenet.log` for runtime diagnostics.
- Ensure `discord.py` intents are enabled in the developer portal.

## Project Structure
```
bot/
├── cogs/
├── dashboard/
├── database/
├── models/
├── security/
├── tasks/
├── utils/
└── ...
```

## Contribution
Pull requests are welcome for feature expansion, performance improvements, and security hardening.
