import discord
import typing
import asyncio


class Paginator:
    def __init__(self, client: discord.Client, message: discord.Message, predicate, pages: typing.Iterable,
                 *, embed=None, timeout=60, delete_message=False):
        if message.author.id != client.user.id:
            raise RuntimeError('Cannot use message the client doesn\'t own as pagination message.')

        self.client = client
        self.pages = list(pages)
        self.predicate = predicate
        self.timeout = timeout
        self.message = message
        self.delete_msg = delete_message
        self.stopped = False

        self.navigation = {
            '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}': self.first_page,
            '\N{BLACK LEFT-POINTING TRIANGLE}': self.previous_page,
            '\N{BLACK RIGHT-POINTING TRIANGLE}': self.next_page,
            '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}': self.last_page,
            '\N{BLACK SQUARE FOR STOP}': self.stop
        }
        self.embed = discord.Embed(description='Please wait, pages are loading...') if embed is None else embed

        self._page = None

    async def begin(self):
        """Starts pagination"""
        await self.message.edit(embed=self.embed)
        for button in self.navigation:
            await self.message.add_reaction(button)
        await self.first_page()
        while not self.stopped:
            try:
                reaction, user = await self.client.wait_for('reaction_add', check=self.predicate, timeout=self.timeout)
            except asyncio.TimeoutError:
                await self.stop(delete=False)
                continue

            reaction = reaction.emoji

            if reaction not in self.navigation:
                continue  # not worth our time

            try:
                await self.message.remove_reaction(reaction, user)
            except discord.Forbidden:
                pass  # oh well, we tried

            await self.navigation[reaction]()

    async def stop(self, *, delete=None):
        """Aborts pagination."""
        if delete is None:
            delete = self.delete_msg

        if delete:
            await self.message.delete()
        else:
            await self._clear_reactions()
        self.stopped = True

    async def _clear_reactions(self):
        try:
            await self.message.clear_reactions()
        except discord.Forbidden:
            for button in self.navigation:
                await self.message.remove_reaction(button, self.message.author)

    async def format_page(self):
        self.embed.description = self.pages[self._page]
        self.embed.set_footer(text='Page {} of {}'.format(self._page+1, len(self.pages)))
        await self.message.edit(embed=self.embed)

    async def first_page(self):
        self._page = 0
        await self.format_page()

    async def next_page(self):
        self._page += 1
        if self._page == len(self.pages):  # avoid the inevitable IndexError
            self._page = 0
        await self.format_page()

    async def previous_page(self):
        self._page -= 1
        if self._page < 0:  # ditto
            self._page = len(self.pages) - 1
        await self.format_page()

    async def last_page(self):
        self._page = len(self.pages) - 1
        await self.format_page()
