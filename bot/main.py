import asyncio
import contextlib
import logging
import sys
from pathlib import Path
from typing import Optional, Set

import discord
import uvicorn
from discord.ext import commands

from bot.config import settings
from bot.database.manager import DatabaseManager
from bot.dashboard.api import app as dashboard_app
from bot.tasks.scheduler import SafeNetScheduler

logger = logging.getLogger("safenet")


class SafeNetBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.all()
        super().__init__(command_prefix=settings.command_prefix, intents=intents, help_command=None)
        self.db = DatabaseManager()
        self.scheduler = SafeNetScheduler()
        self._dashboard_task: Optional[asyncio.Task[None]] = None
        self._presence_task: Optional[asyncio.Task[None]] = None
        self.loaded_cogs: Set[str] = set()
        self.started = False

    async def setup_hook(self) -> None:
        await self.db.connect()
        self.scheduler.start()
        self._load_cogs()
        await self.tree.sync()
        self._dashboard_task = asyncio.create_task(self._serve_dashboard())
        self.started = True
        logger.info("Setup complete")

    def _load_cogs(self) -> None:
        from pathlib import Path

        cog_folder = Path(__file__).parent / "cogs"
        for path in sorted(cog_folder.glob("*.py")):
            if path.name.startswith("_") or path.stem == "__init__":
                continue
            extension = f"bot.cogs.{path.stem}"
            self.loaded_cogs.add(extension)
            self.load_extension(extension)

    async def _serve_dashboard(self) -> None:
        config = uvicorn.Config(
            dashboard_app,
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            log_level="warning",
            loop="asyncio",
            lifespan="on",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def on_ready(self) -> None:
        logger.info("Bot ready: %s (%s)", self.user, self.user.id)
        if self._presence_task is None or self._presence_task.done():
            self._presence_task = asyncio.create_task(self._rotate_presence())

    async def _rotate_presence(self) -> None:
        statuses = [
            "Protecting your community",
            "Moderating with SafeNet",
            "Monitoring server health",
            "Watching for abuse",
        ]
        index = 0
        while not self.is_closed():
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=statuses[index]))
            index = (index + 1) % len(statuses)
            await asyncio.sleep(30)

    async def close(self) -> None:
        if self._dashboard_task and not self._dashboard_task.done():
            self._dashboard_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._dashboard_task
        self.scheduler.stop()
        await self.db.close()
        await super().close()


async def main() -> int:
    log_dir = Path("bot/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "safenet.log", encoding="utf-8"),
        ],
    )

    if not settings.discord_token:
        logger.warning("DISCORD_TOKEN is not configured. Starting in idle health mode.")
        bot = SafeNetBot()
        await bot.db.connect()
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        finally:
            await bot.db.close()
        return 0

    bot = SafeNetBot()
    try:
        await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        await bot.close()
    return 0
