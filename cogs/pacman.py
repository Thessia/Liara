import asyncio
import os
import shlex
import subprocess
import sys

from discord.ext import commands

from cogs.utils import checks
from cogs.utils.storage import RedisCollection


class Pacman:
    """Liara's package manager."""  # TODO: Make this sync repositories over shards' instances
    def __init__(self, liara):
        self.liara = liara
        self.loop = self.liara.loop

        self.db = RedisCollection(liara.redis, 'liara.pacman')

        self.env = dict(os.environ)
        self.created_ssh_agent = False

        self.loop.create_task(self._setup_dot_exe())
        self._config_path()

    async def _setup_dot_exe(self):
        keys = await self.db.keys()
        if not keys:
            await self.liara.redis.delete('pacman')

        liara_dir = os.getcwd()
        data_dir = os.path.join(liara_dir, 'data')
        pacman_dir = os.path.join(data_dir, 'pacman')

        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        if not os.path.exists(pacman_dir):
            os.mkdir(pacman_dir)

    def __unload(self):
        wd = self._join_pacman_relative()
        for path in sys.path:
            if not path.startswith(wd):
                continue
            sys.path.remove(path)

    def _config_path(self):
        wd = self._join_pacman_relative()
        paths = []
        for thing in os.listdir(wd):
            fp = self._join_pacman_relative(thing)
            if not os.path.isdir(fp):
                continue
            paths.append(fp)
            if fp in sys.path:
                continue
            sys.path.append(fp)

        for path in sys.path:
            if not path.startswith(wd):
                continue
            if path in paths:
                continue
            sys.path.remove(path)

    @staticmethod
    def _join_pacman_relative(*path):
        return os.path.join(os.getcwd(), 'data', 'pacman', *path)

    async def _run_command(self, command, workdir='.') -> str:
        proc = await asyncio.create_subprocess_exec(
            *shlex.split(command),
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            cwd=workdir,
            env=self.env
        )

        out, _ = await proc.communicate()
        return out.decode().strip()

    async def _git_pull(self, wd='.'):
        if wd != '.':
            wd = self._join_pacman_relative(wd)
        else:
            wd = os.getcwd()

        return await self._run_command('git pull', wd)

    async def _git_clone(self, repository, target=None):
        wd = self._join_pacman_relative()

        if not target:
            return await self._run_command('git clone {}'.format(shlex.quote(repository)), wd)
        return await self._run_command('git clone {} {}'.format(shlex.quote(repository), shlex.quote(target)), wd)

    @commands.group(invoke_without_command=True)
    @checks.is_owner()
    async def pacman(self, ctx):
        """Main package manager command."""
        await self.liara.send_command_help(ctx)

    @pacman.command()
    @checks.is_owner()
    async def update_bot(self, ctx):
        """Updates the current bot instance."""
        async with ctx.typing():
            o = await self._git_pull()
        return await ctx.send('```\n{}\n```'.format(o))

    @pacman.command()
    @checks.is_owner()
    async def repos(self, ctx):
        """Lists configured repositories."""
        wd = self._join_pacman_relative()
        repos = [x for x in os.listdir(wd) if os.path.isdir(self._join_pacman_relative(x))]
        if not repos:
            return await ctx.send('No repositories are currently configured.')
        await ctx.send('Currently configured repositories:\n{}'.format(', '.join('`{}`'.format(x) for x in repos)))

    @pacman.command()
    @checks.is_owner()
    async def add(self, ctx, repo, name):
        """
        Adds a repository

        - repo: The repository to add.
        - name: What to call the repository internally (in Pacman).
        """
        async with ctx.typing():
            output = await self._git_clone(repo, name)
        await ctx.send('```\n{}\n```'.format(output))

    @pacman.command()
    @checks.is_owner()
    async def update(self, ctx, repo):
        """
        Updates a repository.

        - repo: The repository to update.
        """
        async with ctx.typing():
            output = await self._git_pull(repo)
        await ctx.send('```\n{}\n```'.format(output))

    @pacman.command()
    @checks.is_owner()
    async def update_repos(self, ctx):
        """Updates all repositories."""
        wd = self._join_pacman_relative()
        repos = [x for x in os.listdir(wd) if os.path.isdir(self._join_pacman_relative(x))]

        await ctx.trigger_typing()
        for repo in repos:
            out = await self._git_pull(repo)
            await ctx.send('Repo `{}` updated:\n```\n{}\n```'.format(repo, out))
            await ctx.trigger_typing()
        await ctx.send('Updated all repositories.')


def setup(liara):
    liara.add_cog(Pacman(liara))
