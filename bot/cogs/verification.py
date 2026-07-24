import logging
import random
import string
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import settings
from bot.utils.helpers import utc_now

logger = logging.getLogger("safenet.verification")


class VerificationView(discord.ui.View):
    def __init__(self, bot: commands.Bot, role: discord.Role) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.role = role

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="safenet_verify")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Verification must happen in a server.", ephemeral=True)
            return
        if self.role in interaction.user.roles:
            await interaction.response.send_message("You are already verified.", ephemeral=True)
            return
        await interaction.user.add_roles(self.role)
        await self.bot.db.save_document(
            "verification",
            {
                "guild_id": interaction.guild.id,
                "user_id": interaction.user.id,
                "role_id": self.role.id,
                "verified_at": utc_now().isoformat(),
            },
        )
        await interaction.response.send_message("Verification complete.", ephemeral=True)


class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="verify_setup", description="Create a verification button for your server")
    @app_commands.describe(channel="Channel to send the verification prompt", role="Role to assign when verified")
    async def verify_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role: discord.Role,
    ) -> None:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You do not have permission to setup verification.", ephemeral=True)
            return
        view = VerificationView(self.bot, role)
        await channel.send("Click the button to verify your account.", view=view)
        await interaction.response.send_message(f"Verification prompt created in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="verify", description="Start the verification check")
    async def verify(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        verification_role = discord.utils.get(interaction.guild.roles, name=settings.verification_role)
        if verification_role is None:
            await interaction.response.send_message("Verification role is not configured.", ephemeral=True)
            return
        view = VerificationView(self.bot, verification_role)
        await interaction.response.send_message("Click below to verify your account.", view=view, ephemeral=True)

    @app_commands.command(name="verify_status", description="Check your verification status")
    async def verify_status(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        verification_role = discord.utils.get(interaction.guild.roles, name=settings.verification_role)
        if verification_role and verification_role in interaction.user.roles:
            await interaction.response.send_message("You are verified.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not verified yet.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerificationCog(bot))
