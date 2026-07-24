import logging
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import settings
from bot.utils.helpers import generate_case_id, utc_now

logger = logging.getLogger("safenet.moderation")


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _create_case(
        self,
        guild: discord.Guild,
        user: discord.Member | discord.User,
        moderator: discord.Member,
        action: str,
        reason: str,
        duration: Optional[int] = None,
        evidence: Optional[str] = None,
    ) -> dict:
        case_id = generate_case_id()
        payload = {
            "case_id": case_id,
            "guild_id": guild.id,
            "user_id": user.id,
            "moderator_id": moderator.id,
            "action": action,
            "reason": reason,
            "evidence": evidence,
            "created_at": utc_now().isoformat(),
            "duration": duration,
            "expires_at": (utc_now() + timedelta(seconds=duration)).isoformat() if duration else None,
            "appeal_status": "pending",
        }
        await self.bot.db.save_document("cases", payload)
        return payload

    async def _check_guild_permission(self, interaction: discord.Interaction, permission: str) -> bool:
        if not getattr(interaction.user.guild_permissions, permission, False):
            await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
            return False
        return True

    def _can_act_on(self, interaction: discord.Interaction, target: discord.Member) -> bool:
        if target == interaction.user:
            return False
        if target.top_role >= interaction.user.top_role:
            return False
        return True

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(user="The member to ban", reason="Reason for the ban", evidence="Optional evidence link")
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided",
        evidence: Optional[str] = None,
    ) -> None:
        if not await self._check_guild_permission(interaction, "ban_members"):
            return
        if not self._can_act_on(interaction, user):
            await interaction.response.send_message("Unable to perform action against this member.", ephemeral=True)
            return
        await user.ban(reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "ban", reason, evidence=evidence)
        await interaction.response.send_message(f"Banned {user.mention}. Case created.", ephemeral=False)

    @app_commands.command(name="tempban", description="Temporarily ban a member")
    @app_commands.describe(user="The member to tempban", duration="Duration in seconds", reason="Reason", evidence="Optional evidence link")
    async def tempban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: int,
        reason: str = "No reason provided",
        evidence: Optional[str] = None,
    ) -> None:
        if not await self._check_guild_permission(interaction, "ban_members"):
            return
        if not self._can_act_on(interaction, user):
            await interaction.response.send_message("Unable to perform action against this member.", ephemeral=True)
            return
        await user.ban(reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "tempban", reason, duration=duration, evidence=evidence)
        await interaction.response.send_message(f"Temporarily banned {user.mention} for {duration} seconds.", ephemeral=False)

    @app_commands.command(name="softban", description="Softban a member to clear messages")
    @app_commands.describe(user="The member to softban", reason="Reason", evidence="Optional evidence link")
    async def softban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided",
        evidence: Optional[str] = None,
    ) -> None:
        if not await self._check_guild_permission(interaction, "ban_members"):
            return
        if not self._can_act_on(interaction, user):
            await interaction.response.send_message("Unable to perform action against this member.", ephemeral=True)
            return
        await user.ban(reason=reason)
        await user.unban(reason="Softban message cleanup")
        await self._create_case(interaction.guild, user, interaction.user, "softban", reason, evidence=evidence)
        await interaction.response.send_message(f"Softbanned {user.mention} and cleared recent messages.", ephemeral=False)

    @app_commands.command(name="unban", description="Unban a user from the server")
    @app_commands.describe(user_id="The ID of the banned user", reason="Reason for unbanning")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided") -> None:
        if not await self._check_guild_permission(interaction, "ban_members"):
            return
        user = discord.Object(id=int(user_id))
        await interaction.guild.unban(user, reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "unban", reason)
        await interaction.response.send_message(f"Unbanned <@{user_id}>.", ephemeral=False)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(user="The member to kick", reason="Reason for the kick", evidence="Optional evidence link")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided", evidence: Optional[str] = None) -> None:
        if not await self._check_guild_permission(interaction, "kick_members"):
            return
        if not self._can_act_on(interaction, user):
            await interaction.response.send_message("Unable to perform action against this member.", ephemeral=True)
            return
        await user.kick(reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "kick", reason, evidence=evidence)
        await interaction.response.send_message(f"Kicked {user.mention}.", ephemeral=False)

    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(user="The member to timeout", duration="Duration in seconds", reason="Reason", evidence="Optional evidence link")
    async def timeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: int,
        reason: str = "No reason provided",
        evidence: Optional[str] = None,
    ) -> None:
        if not await self._check_guild_permission(interaction, "moderate_members"):
            return
        until = utc_now() + timedelta(seconds=duration)
        await user.timeout(until, reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "timeout", reason, duration=duration, evidence=evidence)
        await interaction.response.send_message(f"Timed out {user.mention} for {duration}s.", ephemeral=False)

    @app_commands.command(name="untimeout", description="Remove a member timeout")
    @app_commands.describe(user="The member to untimeout")
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._check_guild_permission(interaction, "moderate_members"):
            return
        await user.timeout(None)
        await self._create_case(interaction.guild, user, interaction.user, "untimeout", "Timeout removed")
        await interaction.response.send_message(f"Removed timeout from {user.mention}.", ephemeral=False)

    @app_commands.command(name="mute", description="Mute a member in voice")
    @app_commands.describe(user="The member to mute", reason="Reason")
    async def mute(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided") -> None:
        if not await self._check_guild_permission(interaction, "mute_members"):
            return
        await user.edit(mute=True, reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "mute", reason)
        await interaction.response.send_message(f"Voice-muted {user.mention}.", ephemeral=False)

    @app_commands.command(name="tempmute", description="Temporarily mute a member in voice")
    @app_commands.describe(user="The member to tempmute", duration="Duration in seconds", reason="Reason")
    async def tempmute(self, interaction: discord.Interaction, user: discord.Member, duration: int, reason: str = "No reason provided") -> None:
        if not await self._check_guild_permission(interaction, "mute_members"):
            return
        await user.edit(mute=True, reason=reason)
        await self._create_case(interaction.guild, user, interaction.user, "tempmute", reason, duration=duration)
        await interaction.response.send_message(f"Temporarily voice-muted {user.mention} for {duration}s.", ephemeral=False)

    @app_commands.command(name="unmute", description="Unmute a voice member")
    @app_commands.describe(user="The member to unmute")
    async def unmute(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._check_guild_permission(interaction, "mute_members"):
            return
        await user.edit(mute=False)
        await self._create_case(interaction.guild, user, interaction.user, "unmute", "Voice unmute")
        await interaction.response.send_message(f"Unmuted {user.mention}.", ephemeral=False)

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(user="The member to warn", reason="Reason", category="Warning category", severity="Warning severity")
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided",
        category: str = "general",
        severity: int = 1,
    ) -> None:
        if not await self._check_guild_permission(interaction, "moderate_members"):
            return
        payload = {
            "case_id": generate_case_id(),
            "guild_id": interaction.guild_id,
            "user_id": user.id,
            "moderator_id": interaction.user.id,
            "reason": reason,
            "category": category,
            "severity": severity,
            "created_at": utc_now().isoformat(),
        }
        await self.bot.db.save_document("warnings", payload)
        await self._create_case(interaction.guild, user, interaction.user, "warn", reason)
        await interaction.response.send_message(f"Warned {user.mention}. Severity {severity}.", ephemeral=False)

    @app_commands.command(name="warnings", description="Show warnings for a target")
    @app_commands.describe(user="The member to inspect")
    async def warnings(self, interaction: discord.Interaction, user: discord.Member) -> None:
        docs = await self.bot.db.get_documents("warnings", {"guild_id": interaction.guild_id, "user_id": user.id})
        embed = discord.Embed(title="Warnings", color=discord.Color.orange())
        embed.description = f"{user.mention} has {len(docs)} warning(s)."
        for warning in docs[-10:]:
            embed.add_field(
                name=f"Case {warning['case_id']}",
                value=f"{warning['reason']} (severity {warning['severity']})",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Clear warnings for a user")
    @app_commands.describe(user="The member to clear warnings for")
    async def clearwarnings(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._check_guild_permission(interaction, "moderate_members"):
            return
        await self.bot.db.delete_document("warnings", {"guild_id": interaction.guild_id, "user_id": user.id})
        await interaction.response.send_message(f"Cleared warnings for {user.mention}.", ephemeral=False)

    @app_commands.command(name="history", description="Show moderation history for a user")
    @app_commands.describe(user="The member to view history for")
    async def history(self, interaction: discord.Interaction, user: discord.Member) -> None:
        cases = await self.bot.db.get_documents("cases", {"guild_id": interaction.guild_id, "user_id": user.id})
        embed = discord.Embed(title=f"History for {user.display_name}", color=discord.Color.blue())
        for case in cases[-10:]:
            embed.add_field(
                name=f"{case['action'].title()} ({case['case_id']})",
                value=f"{case['reason']} on {case['created_at']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="case", description="View a moderation case by ID")
    @app_commands.describe(case_id="Case ID to view")
    async def case(self, interaction: discord.Interaction, case_id: str) -> None:
        case_doc = await self.bot.db.find_one("cases", {"case_id": case_id})
        if not case_doc:
            await interaction.response.send_message("Case not found.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Case {case_id}", color=discord.Color.red())
        for key in ["action", "reason", "evidence", "duration", "expires_at", "appeal_status"]:
            if case_doc.get(key) is not None:
                embed.add_field(name=key.title(), value=str(case_doc[key]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cases", description="List recent moderation cases")
    async def cases(self, interaction: discord.Interaction) -> None:
        cases = await self.bot.db.get_documents("cases", {"guild_id": interaction.guild_id})
        embed = discord.Embed(title="Recent Cases", color=discord.Color.purple())
        for case in cases[-10:]:
            embed.add_field(
                name=f"{case['action'].title()} ({case['case_id']})",
                value=f"User <@{case['user_id']}> by <@{case['moderator_id']}>",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="note", description="Add a staff note to a user")
    @app_commands.describe(user="The member to note", note="Staff note text")
    async def note(self, interaction: discord.Interaction, user: discord.Member, note: str) -> None:
        if not await self._check_guild_permission(interaction, "manage_messages"):
            return
        await self.bot.db.save_document("notes", {"guild_id": interaction.guild_id, "user_id": user.id, "moderator_id": interaction.user.id, "note": note, "created_at": utc_now().isoformat()})
        await interaction.response.send_message(f"Note added for {user.mention}.", ephemeral=False)

    @app_commands.command(name="notes", description="View staff notes for a user")
    @app_commands.describe(user="The member to inspect")
    async def notes(self, interaction: discord.Interaction, user: discord.Member) -> None:
        notes = await self.bot.db.get_documents("notes", {"guild_id": interaction.guild_id, "user_id": user.id})
        embed = discord.Embed(title=f"Notes for {user.display_name}", color=discord.Color.green())
        for note in notes[-10:]:
            embed.add_field(name=note["created_at"], value=note["note"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="userinfo", description="Show a user's profile in the server")
    @app_commands.describe(user="The member to inspect")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member) -> None:
        embed = discord.Embed(title=f"User Info — {user.display_name}", color=discord.Color.teal())
        embed.add_field(name="ID", value=str(user.id), inline=True)
        embed.add_field(name="Joined", value=user.joined_at.isoformat() if user.joined_at else "Unknown", inline=True)
        embed.add_field(name="Created", value=user.created_at.isoformat(), inline=True)
        embed.add_field(name="Roles", value=", ".join(role.name for role in user.roles[1:]) or "None", inline=False)
        warnings = await self.bot.db.get_documents("warnings", {"guild_id": interaction.guild_id, "user_id": user.id})
        embed.add_field(name="Warnings", value=str(len(warnings)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purge", description="Bulk delete messages")
    @app_commands.describe(limit="Number of messages to delete", user="Optional user to target", filter="Optional message filter")
    @app_commands.choices(filter=[
        app_commands.Choice(name="all", value="all"),
        app_commands.Choice(name="bots", value="bots"),
        app_commands.Choice(name="links", value="links"),
        app_commands.Choice(name="images", value="images"),
        app_commands.Choice(name="embeds", value="embeds"),
        app_commands.Choice(name="attachments", value="attachments"),
    ])
    async def purge(
        self,
        interaction: discord.Interaction,
        limit: int,
        user: Optional[discord.Member] = None,
        filter: Optional[str] = None,
    ) -> None:
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You do not have permission to purge messages.", ephemeral=True)
            return
        if limit < 1 or limit > 200:
            await interaction.response.send_message("Choose a value between 1 and 200.", ephemeral=True)
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)

        def check(message: discord.Message) -> bool:
            if user and message.author.id != user.id:
                return False
            if filter == "bots" and not message.author.bot:
                return False
            if filter == "links" and not any(value in message.content.lower() for value in ["http://", "https://", "discord.gg", "discord.com"]):
                return False
            if filter == "images" and not any(message.content.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
                return False
            if filter == "embeds" and not message.embeds:
                return False
            if filter == "attachments" and not message.attachments:
                return False
            return True

        deleted = await channel.purge(limit=limit, check=check)
        await interaction.response.send_message(f"Deleted {len(deleted)} messages.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
