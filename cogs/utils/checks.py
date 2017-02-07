import discord
from discord.ext import commands
# noinspection PyUnresolvedReferences
import __main__


def owner_check(ctx):
    return str(ctx.message.author.id) in __main__.liara.owners


def is_owner():
    return commands.check(owner_check)


def is_bot_account():
    def predicate(ctx):
        return ctx.bot.user.bot
    return commands.check(predicate)


def mod_or_permissions(**permissions):
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if not isinstance(ctx.message.author, discord.Member):
            return False
        if ctx.message.author == ctx.message.server.owner:
            return True
        # let's get the roles and compare them to
        # what we have on file (if we do)
        roles = [x.name.lower() for x in ctx.message.author.roles]
        try:
            if __main__.liara.settings['roles'][str(ctx.message.server.id)]['mod_role'].lower() in roles:
                return True
        except KeyError:
            pass
        try:
            if __main__.liara.settings['roles'][str(ctx.message.server.id)]['admin_role'].lower() in roles:
                return True
        except KeyError:
            pass
        user_permissions = dict(ctx.message.author.permissions_in(ctx.message.channel))
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
        if not isinstance(ctx.message.author, discord.Member):
            return False
        if ctx.message.author == ctx.message.server.owner:
            return True
        try:
            roles = [x.name.lower() for x in ctx.message.author.roles]
            if __main__.liara.settings['roles'][str(ctx.message.server.id)]['admin_role'].lower() in roles:
                return True
        except KeyError:
            pass
        user_permissions = dict(ctx.message.author.permissions_in(ctx.message.channel))
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
        if not isinstance(ctx.message.author, discord.Member):
            return False
        if ctx.message.author == ctx.message.server.owner:
            return True
        user_permissions = dict(ctx.message.author.permissions_in(ctx.message.channel))
        for permission in permissions:
            allowed = user_permissions.get(permission, False)
            if allowed:
                return True
        return False
    return commands.check(predicate)
