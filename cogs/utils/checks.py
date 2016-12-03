# noinspection PyUnresolvedReferences
from discord.ext import commands
import __main__


def owner_check(ctx):
    return ctx.message.author.id == __main__.liara.owner.id


def is_owner():
    return commands.check(owner_check)


def mod_or_permissions(**permissions):
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if ctx.message.channel.is_private:
            return False
        if ctx.message.author == ctx.message.server.owner:
            return True
        try:
            roles = [x.name.lower() for x in ctx.message.author.roles]
            if __main__.liara.settings['roles'][ctx.message.server.id]['mod_role'] in roles:
                return True
            if __main__.liara.settings['roles'][ctx.message.server.id]['admin_role'] in roles:
                return True
        except KeyError:
            pass
        user_permissions = dict(ctx.message.author.permissions_in(ctx.message.channel))
        for permission in permissions:
            allowed = user_permissions.get(permission, default=False)
            if allowed:
                return True
        return False
    return commands.check(predicate)


def admin_or_permissions(**permissions):
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if ctx.message.channel.is_private:
            return False
        if ctx.message.author == ctx.message.server.owner:
            return True
        try:
            roles = [x.name.lower() for x in ctx.message.author.roles]
            if __main__.liara.settings['roles'][ctx.message.server.id]['admin_role'] in roles:
                return True
        except KeyError:
            pass
        user_permissions = dict(ctx.message.author.permissions_in(ctx.message.channel))
        for permission in permissions:
            allowed = user_permissions.get(permission, default=False)
            if allowed:
                return True
        return False
    return commands.check(predicate)


def serverowner_or_permissions(**permissions):
    def predicate(ctx):
        if owner_check(ctx):
            return True
        if ctx.message.channel.is_private:
            return False
        if ctx.message.author == ctx.message.server.owner:
            return True
        user_permissions = dict(ctx.message.author.permissions_in(ctx.message.channel))
        for permission in permissions:
            allowed = user_permissions.get(permission, default=False)
            if allowed:
                return True
        return False
    return commands.check(predicate)
