import logging
import re
from collections import defaultdict
from typing import Dict, List

import discord
from discord.ext import commands

from bot.utils.helpers import utc_now

logger = logging.getLogger("safenet.automod")

INVITE_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite|discordapp\.com/invite)/[A-Za-z0-9]+")
SHORTENER_PATTERN = re.compile(r"(?:bit\.ly|tinyurl\.com|goo\.gl|t\.co|owly\.com|buff\.ly)")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
ZALGO_PATTERN = re.compile(r"[\u0300-\u036f]|0|1")
BANNED_WORDS = {"badword", "slur", "scam"}

recent_messages: Dict[int, List[str]] = defaultdict(list)


class AutoModCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _log_action(self, message: discord.Message, reason: str) -> None:
        await self.bot.db.save_document(
            "logs",
            {
                "guild_id": message.guild.id,
                "user_id": message.author.id,
                "action": "automod_delete",
                "reason": reason,
                "content": message.content,
                "created_at": utc_now().isoformat(),
            },
        )

    def _detect_violation(self, message: discord.Message) -> List[str]:
        content = message.content.lower()
        reasons = []
        if INVITE_PATTERN.search(content):
            reasons.append("discord_invite")
        if SHORTENER_PATTERN.search(content):
            reasons.append("shortener_link")
        if IP_PATTERN.search(content):
            reasons.append("ip_address")
        if any(word in content for word in BANNED_WORDS):
            reasons.append("banned_word")
        if len(content) > 200 and content.isupper():
            reasons.append("caps_spam")
        if len(content) > 300 and content.count(" ") < 20:
            reasons.append("mass_mentions")
        if ZALGO_PATTERN.search(message.content):
            reasons.append("zalgo_text")
        return reasons

    async def _apply_filters(self, message: discord.Message) -> None:
        reasons = self._detect_violation(message)
        if reasons:
            await message.delete()
            await self._log_action(message, ", ".join(reasons))
            await message.channel.send(f"{message.author.mention}, your message violated server rules and was removed.", delete_after=5)
            return

        if len(recent_messages[message.author.id]) >= 4 and recent_messages[message.author.id][-4:] == [message.content] * 4:
            await message.delete()
            await self._log_action(message, "duplicate_message")
            await message.channel.send(f"{message.author.mention}, please stop repeating the same message.", delete_after=5)
            return

        recent_messages[message.author.id].append(message.content)
        if len(recent_messages[message.author.id]) > 8:
            recent_messages[message.author.id].pop(0)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild or not message.content:
            return
        await self._apply_filters(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.author.bot or not after.guild or not after.content:
            return
        await self._apply_filters(after)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoModCog(bot))
