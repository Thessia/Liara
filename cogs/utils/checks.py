import discord
from discord.ext import commands


def owner_check(ctx):
    return ctx.author.id in ctx.bot.owners


async def role_check(ctx, _role):
    roles = {x.name.lower() for x in ctx.author.roles}
    settings = await ctx.bot.settings.get('guilds:{}'.format(ctx.guild.id), {})
    role_settings = settings.get('roles', {})
    role = role_settings.get(_role)
    return role in roles


def permission_check(ctx, **permission_pairs):
    if not isinstance(ctx.channel, discord.TextChannel):
        return False
    channel_permissions = dict(ctx.author.permissions_in(ctx.channel))
    for permission in permission_pairs:
        state = channel_permissions.get(permission, False)
        if state == permission_pairs[permission]:
            return True
    return False


def is_owner():
    return commands.check(owner_check)


def is_bot_account():
    def predicate(ctx):
        return ctx.bot.user.bot
    return commands.check(predicate)


def is_not_bot_account():
    def predicate(ctx):
        return not ctx.bot.user.bot
    return commands.check(predicate)


def is_selfbot():
    def predicate(ctx):
        return ctx.bot.self_bot
    return commands.check(predicate)


def is_not_selfbot():
    def predicate(ctx):
        return not ctx.bot.self_bot
    return commands.check(predicate)


def is_main_shard():
    def predicate(ctx):
        if ctx.bot.shard_id is None:
            return True
        elif ctx.bot.shard_id == 0:
            return True
        else:
            return False
    return commands.check(predicate)


def is_not_main_shard():
    def predicate(ctx):
        if ctx.bot.shard_id is None:
            return False
        elif ctx.bot.shard_id == 0:
            return False
        else:
            return True
    return commands.check(predicate)


def mod_or_permissions(**permissions):
    async def predicate(ctx):
        if owner_check(ctx):
            return True
        if not isinstance(ctx.author, discord.Member):
            return False
        if ctx.author == ctx.guild.owner:
            return True
        if await role_check(ctx, 'mod'):
            return True
        if await role_check(ctx, 'admin'):
            return True
        if permission_check(ctx, **permissions):
            return True
        return False
    return commands.check(predicate)


def admin_or_permissions(**permissions):
    async def predicate(ctx):
        if owner_check(ctx):
            return True
        if not isinstance(ctx.author, discord.Member):
            return False
        if ctx.author == ctx.guild.owner:
            return True
        if await role_check(ctx, 'admin'):
            return True
        if permission_check(ctx, **permissions):
            return True
        return False
    return commands.check(predicate)


def serverowner_or_permissions(**permissions):
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if not isinstance(ctx.author, discord.Member):
            return False
        if ctx.author == ctx.guild.owner:
            return True
        if permission_check(ctx, **permissions):
            return True
        return False
    return commands.check(predicate)


# deal with more of Red's nonsense
serverowner = serverowner_or_permissions
admin = admin_or_permissions
mod = mod_or_permissions
