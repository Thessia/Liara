import discord
from discord.ext import commands


def owner_check(ctx):
    return str(ctx.author.id) in ctx.bot.owners


def role_check(ctx, _role):
    roles = [x.name.lower() for x in ctx.author.roles]
    settings = ctx.bot.settings['roles']
    role = settings.get(str(ctx.guild.id), {}).get('{}_role'.format(_role))
    return role in roles


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
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if not isinstance(ctx.author, discord.Member):
            return False
        if ctx.author == ctx.guild.owner:
            return True
        if role_check(ctx, 'mod'):
            return True
        if role_check(ctx, 'admin'):
            return True
        user_permissions = dict(ctx.author.permissions_in(ctx.channel))
        for permission in permissions:
            if permissions[permission]:
                allowed = user_permissions.get(permission, False)
                if allowed:
                    return True
        return False
    return commands.check(predicate)


def admin_or_permissions(**permissions):
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if not isinstance(ctx.author, discord.Member):
            return False
        if ctx.author == ctx.guild.owner:
            return True
        if role_check(ctx, 'admin'):
            return True
        user_permissions = dict(ctx.author.permissions_in(ctx.channel))
        for permission in permissions:
            if permissions[permission]:
                allowed = user_permissions.get(permission, False)
                if allowed:
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
        user_permissions = dict(ctx.author.permissions_in(ctx.channel))
        for permission in permissions:
            allowed = user_permissions.get(permission, False)
            if allowed:
                return True
        return False
    return commands.check(predicate)


# deal with more of Red's nonsense
serverowner = serverowner_or_permissions
admin = admin_or_permissions
mod = mod_or_permissions
