import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.helpers import generate_case_id, utc_now

logger = logging.getLogger("safenet.tickets")


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _save_ticket(self, channel: discord.TextChannel, owner: discord.Member, category_id: Optional[int] = None) -> None:
        await self.bot.db.save_document(
            "tickets",
            {
                "ticket_id": generate_case_id(),
                "guild_id": channel.guild.id,
                "channel_id": channel.id,
                "owner_id": owner.id,
                "category_id": category_id,
                "created_at": utc_now().isoformat(),
                "status": "open",
            },
        )

    @app_commands.command(name="ticket", description="Create a support ticket")
    @app_commands.describe(category="Optional ticket category channel", reason="Reason for opening the ticket")
    async def ticket(self, interaction: discord.Interaction, reason: str, category: Optional[discord.CategoryChannel] = None) -> None:
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        category = category or discord.utils.get(interaction.guild.categories, name="Tickets")
        if category is None:
            category = await interaction.guild.create_category("Tickets")
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.display_name}", category=category, topic="Support ticket channel"
        )
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True, add_reactions=True)
        await channel.set_permissions(interaction.guild.default_role, send_messages=False, read_messages=False)
        await self._save_ticket(channel, interaction.user, category.id)
        await channel.send(f"{interaction.user.mention} opened a ticket: {reason}")
        await interaction.response.send_message(f"Created ticket {channel.mention}", ephemeral=True)

    @app_commands.command(name="ticket_close", description="Close the current ticket")
    async def ticket_close(self, interaction: discord.Interaction) -> None:
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command must be used inside a ticket channel.", ephemeral=True)
            return
        await interaction.response.send_message("Closing this ticket...")
        await interaction.channel.edit(topic="Ticket closed")
        await self.bot.db.update_document("tickets", {"channel_id": interaction.channel.id}, {"status": "closed"})

    @app_commands.command(name="ticket_claim", description="Claim a ticket as staff")
    async def ticket_claim(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You do not have permission to claim tickets.", ephemeral=True)
            return
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command must be used inside a ticket channel.", ephemeral=True)
            return
        await self.bot.db.update_document("tickets", {"channel_id": interaction.channel.id}, {"claimed_by": interaction.user.id})
        await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.", ephemeral=False)

    @app_commands.command(name="ticket_add", description="Add a member to the ticket")
    @app_commands.describe(member="Member to add")
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command must be used inside a ticket channel.", ephemeral=True)
            return
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"Added {member.mention} to the ticket.", ephemeral=False)

    @app_commands.command(name="ticket_remove", description="Remove a member from the ticket")
    @app_commands.describe(member="Member to remove")
    async def ticket_remove(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command must be used inside a ticket channel.", ephemeral=True)
            return
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"Removed {member.mention} from the ticket.", ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketCog(bot))
