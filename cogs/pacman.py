from cogs.utils import checks
from cogs.utils import dataIO
from discord.ext import commands
from hashlib import sha256
import aiohttp
import json
import re
import asyncio


class Pacman:
    """Liara's package manager."""
    def __init__(self, liara):
        self.liara = liara
        self.db = dataIO.load('pacman')
        self.indexing = False
        self.log = None
        self.crawled = None
        self.urlmatch = re.compile(r'^https?://')
        self.pkgmatch = re.compile(r'^[a-z_]+\.[a-z_\-.]+$')

        if self.db.get('indexes') is None:
            self.db['indexes'] = {}

    @staticmethod
    async def create_gist(content, filename='output.md'):
        github_file = {'files': {filename: {'content': str(content)}}}
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.github.com/gists', data=json.dumps(github_file)) as response:
                return await response.json()

    @staticmethod
    def remove_markdown(string):
        return (string.replace('\\', '\\\\').replace('`', '\\`').replace('*', '\\*').replace('|', '&#124;')
                .replace('<', '&#60;').replace('>', '&#62;'))

    async def trigger_crawl(self, urls):
        self.indexing = True
        self.log = ''
        self.crawled = set()

        for url in urls:
            await self.crawl_index(url)
        self.log += 'Done.'
        self.indexing = False
        return self.log

    async def crawl_index(self, url, inherited='root', depth=0):
        if not isinstance(url, str):  # because I bet some moron will put an integer in there
            url = str(url)
        _hash = sha256(url.encode()).hexdigest()  # just for identifying indexes, nothing more really

        try:
            assert url not in self.crawled, 'URL already crawled'
            self.crawled.add(url)
            assert self.urlmatch.match(url), 'URL (`{}`) is invalid'.format(url.replace('`', ''))

            async with aiohttp.ClientSession() as sess:
                text = ''  # make pycharm shut up
                try:
                    async with sess.get(url, timeout=5) as resp:
                        text = await resp.text()
                except aiohttp.errors.TimeoutError:
                    raise AssertionError('Connection error, timed out')
                except aiohttp.errors.ClientError:
                    raise AssertionError('Connection error')
                except:
                    raise AssertionError('Unknown error')

            try:
                _json = json.loads(text)
            except json.JSONDecodeError:
                raise AssertionError('Unable to decode JSON')

            index_name = _json.get('name')
            assert index_name is not None, 'Missing name'
            assert isinstance(index_name, str), 'Index name is not a string'
            index_description = _json.get('description', 'No index description')
            assert isinstance(index_description, str), 'Index description is not a string'
            indexes = _json.get('indexes', [])
            assert isinstance(indexes, list), 'Indexes is not a list'
            cogs = _json.get('cogs', [])
            assert isinstance(cogs, list), 'Cogs is not a list'

            _cogs = []
            for cog in cogs:
                num = cogs.index(cog) + 1
                assert isinstance(cog, dict), 'Cog {} is not a dict'.format(num)
                cog_name = cog.get('name')
                assert cog_name is not None, 'Cog {} has no name'.format(num)
                assert isinstance(cog_name, str), 'Cog {}\'s name is not a string'.format(num)
                cog_package = cog.get('package')
                assert cog_package is not None, 'Cog {} has no package'.format(num)
                assert isinstance(cog_package, str), 'Cog {}\'s package is not a string'.format(num)
                assert self.pkgmatch.match(cog_package), 'Cog {}\'s package contains invalid characters'
                cog_description = cog.get('description', 'No description given')
                assert isinstance(cog_description, str), 'Cog {}\'s description is not a string'.format(num)
                cog_url = cog.get('url')
                assert cog_url is not None, 'Cog {} has no URL'.format(num)
                assert isinstance(cog_url, str), 'Cog {}\'s URL is not a string'.format(num)
                assert self.urlmatch.match(cog_url), 'Cog {}\'s URL is not a valid URL'.format(num)
                version = cog.get('version', 'stable')
                assert isinstance(version, str), 'Cog {}\'s version is not a string'.format(num)
                # cleaning up, we're taking nothing straight from JSON into our database here
                _cogs.append({'name': cog_name, 'package': cog_package, 'description': cog_description, 'url': cog_url,
                              'version': version})

            self.db['indexes'][_hash] = {  # again, same thing applies here
                'name': index_name,
                'description': index_description,
                'url': url,
                'root_index': inherited,  # tells us if the index was inherited or is root
                'cogs': _cogs
            }

            self.log += '`{}`: `{}`: Indexed `{}`\n'.format(inherited[0:7], _hash[0:7],
                                                            self.remove_markdown(index_name))

            if depth > 2:  # too much recursion
                return
            for index in indexes:
                await self.crawl_index(index, inherited=_hash, depth=depth+1)
        except AssertionError as e:
            self.log += '`{}`: `{}`: {}\n'.format(inherited[0:7], _hash[0:7], e)  # AssertionErrors are nice

    def list_cogs(self):
        cogs = {}
        for _hash, index in self.db['indexes'].items():
            for cog in index['cogs']:
                cog['index'] = _hash
                cogs[cog['package']] = cog
        return cogs

    @commands.group(invoke_without_command=True)
    async def pacman(self, ctx):
        """Main pacman command."""
        await self.liara.send_command_help(ctx)

    @pacman.command('add-index', aliases=['ai', 'add'])
    @checks.is_owner()
    async def add_index(self, ctx, url):
        """Adds an index."""
        message = await ctx.send('Indexing...')
        log = await self.trigger_crawl([url])
        await message.edit(content='Indexing...\n'+log)

    @pacman.command('remove-index', aliases=['ri'])
    @checks.is_owner()
    async def remove_index(self, ctx, _hash: str):
        """Removes an index."""
        if _hash in self.db['indexes']:
            self.db['indexes'].pop(_hash)
            await ctx.send('Index removed.')
        else:
            await ctx.send('That index has not been added.')

    @pacman.command('list-indexes', aliases=['li'])
    @checks.is_owner()
    async def list_indexes(self, ctx):
        """Lists all indexes in a nicely-formatted gist."""
        if len(self.db['indexes']) == 0:
            await ctx.send('You have no indexes.')
            return
        msg = 'Index | Description | Hashes\n--- | --- | ---\n'
        for _hash, index in self.db['indexes'].items():
            name = self.remove_markdown(index['name'])
            description = self.remove_markdown(index['description'])
            url = self.remove_markdown(index['url'])
            # using details tags, we can make expandable tags for our hashes, which is nice
            # it also might convince some people to remove Internet Explorer
            msg += ('[{}]({}) | {} | <details><summary>Hash</summary>`{}`</details><details><summary>Relationship'
                    '</summary>`{}`</details>\n'.format(name, url, description, _hash, index['root_index']))

        await ctx.trigger_typing()
        gist = await self.create_gist(msg, 'indexes.md')
        await ctx.send(gist['html_url'])

    @pacman.command('update-indexes', aliases=['ui', 'update'])
    @checks.is_owner()
    async def update_indexes(self, ctx):
        """Updates all root indexes.
        Will remove inherited indexes that were removed from the parent index."""
        message = await ctx.send('Updating indexes...')
        urls = [v['url'] for k, v in self.db['indexes'].items() if v['root_index'] == 'root']
        self.db['indexes_backup'] = self.db['indexes']
        self.db['indexes'] = {}
        log = await self.trigger_crawl(urls)
        await message.edit(content='Updating indexes...\n'+log)

    @pacman.command('restore-indexes', hidden=True)
    @checks.is_owner()
    async def restore_indexes(self, ctx):
        """Restores indexes to the state before the last index update."""
        self.db['indexes'] = self.db['indexes_backup']
        await ctx.send('Indexes restored to the state before the last update.')

    @pacman.command('list-cogs', aliases=['lc'])
    @checks.is_owner()
    async def list_cogs_cmd(self, ctx):
        """Lists all cogs in a nicely-formatted gist."""
        cogs = self.list_cogs()
        if len(cogs) == 0:
            await ctx.send('Your current indexes have no cogs.')
            return
        msg = 'Name | Description | Hashes\n--- | --- | ---\n'
        for package, cog in cogs.items():
            name = self.remove_markdown(cog['name'])
            description = self.remove_markdown(cog['description'])
            url = self.remove_markdown(cog['url'])
            version = self.remove_markdown(cog['version'])
            name_field = '[{}]({}) - `{}`'.format(name, url, version)
            msg += ('{}<br>`{}` | {} | <details><summary>Index</summary>`{}`</details>\n'
                    .format(name_field, package, self.remove_markdown(description), cog['index']))

        await ctx.trigger_typing()
        gist = await self.create_gist(msg, 'cogs.md')
        await ctx.send(gist['html_url'])

    @pacman.command('install-cog', aliases=['ic', 'install'])
    @checks.is_owner()
    async def install_cog(self, ctx, package):
        """Installs a cog by its hash."""
        if not self.pkgmatch.match(package):
            await ctx.send('That isn\'t a valid package.')
            return
        cogs = self.list_cogs()
        if package not in cogs:
            await ctx.send('That cog doesn\'t exist.')
            return
        # get the cog from the URL
        cog = cogs[package]
        # noinspection PyBroadException
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(cog['url']) as resp:
                    if resp.status != 200:
                        await ctx.send('That cog appears to have a broken URL.')
                        return
                    cog_content = await resp.read()
        except aiohttp.errors.ClientError:
            await ctx.send('A client error occured connectiong to the URL. This is usually the sign of a dead URL.')
            return
        except:
            await ctx.send('An unknown error occured while retrieving the cog.')
            return
        # load the cog into Redis
        self.liara.redis.set('cogfiles.cogs.pkg.{}'.format(package), cog_content)
        # finally invoke the load command so we load the thing
        self.liara.get_cog('Core').load_cog('cogs.pkg.{}'.format(package))
        await ctx.send('Cog successfully loaded! Use `{}unload pkg.{}` to unload it.'.format(ctx.prefix, package))

    @pacman.command('update-cogs', aliases=['uc', 'upgrade'])
    @checks.is_owner()
    async def update_cogs(self, ctx):
        """Updates all cogs"""
        log = 'Updating cogs...\n'
        fail = False  # keeping track if the install failed or not, suggesting users to run an update first
        cogs = self.list_cogs()
        cogs_to_reload = []
        message = await ctx.send(log)
        for package, cog in cogs.items():
            if 'cogs.pkg.{}'.format(package) in self.liara.extensions:
                cogs_to_reload.append(package)
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(cog['url']) as resp:
                            assert resp.status == 200, 'Cog URL didn\'t return 200'
                            cog_content = await resp.read()
                except Exception as e:
                    log += '**{}:** {}\n'.format(package, e)
                    fail = True
                    continue
                self.liara.redis.set('cogfiles.cogs.pkg.{}'.format(package), cog_content)
                log += '**`{}`:** Updated successfully\n'.format(package)
        if fail:
            log += 'Some cogs were unable to be updated. Have you tried updating your indexes first?\n'
        log += 'Reloading all cogs now...\n'
        await message.edit(content=log)
        for cog in cogs_to_reload:
            self.liara.get_cog('Core').settings['cogs'].remove('cogs.pkg.{}'.format(cog))
        await asyncio.sleep(2)
        for cog in cogs_to_reload:
            # if anything breaks at this point, we'll let core.py deal with it
            self.liara.get_cog('Core').settings['cogs'].append('cogs.pkg.{}'.format(cog))
        log += 'Cogs reloaded.'
        await message.edit(content=log)


def setup(liara):
    liara.add_cog(Pacman(liara))
