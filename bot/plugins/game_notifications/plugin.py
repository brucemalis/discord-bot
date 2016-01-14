import logging
import re

from discord.enums import Status
from django.conf import settings

from bot.plugins.base import BasePlugin
from bot.plugins.commands import command

from .models import GameNotification


logger = logging.getLogger(__name__)


class Plugin(BasePlugin):

    has_blocking_io = True

    def _member_active(self, member):
        statuses = [Status.online, Status.idle]
        gaming = member.game and settings.DEBUG is False
        return member.status in statuses and not member.is_afk and not gaming

    def on_member_update(self, before, after):
        if not after.game:
            return

        member = after
        game = member.game.name
        subscribers = GameNotification.objects.filter(game_name__iexact=game)
        if settings.DEBUG:
            subscribers = subscribers.filter(user=member.id)
        else:
            subscribers = subscribers.exclude(user=member.id)
        if not subscribers.exists():
            return

        ids = subscribers.values_list('user', flat=True)
        members = [m for m in member.server.members if m.id in ids and self._member_active(m)]
        if not members:
            return

        msg = '{name} started playing {game}'.format(name=member.name, game=game)
        for member in members:
            logger.info('Notifying %s for %s', member.name, game)
            yield from self.client.send_message(member, msg)

    @command(pattern=re.compile(r'(?P<game>.+)', re.IGNORECASE))
    def subscribe(self, command):
        """
        Sets up notifications for <game>
        """
        user = command.message.author.id
        game = command.args.game
        notification, created = GameNotification.objects.get_or_create(game_name=game.lower(), user=user)
        msg = 'Subscribed you to {game}' if created else 'You were already subscribed to {game}'
        yield from command.reply(msg.format(game=game))

    @command(pattern=re.compile(r'(?P<game>.+)', re.IGNORECASE))
    def unsubscribe(self, command):
        """
        Removes notification subscription for <game>
        """
        user = command.message.author.id
        game = command.args.game
        deleted, _ = GameNotification.objects.filter(user=user, game_name__iexact=game).delete()
        if deleted:
            yield from command.reply('Unsubscribed you from {game}'.format(game=game))

    @command('unsubscribe !all')
    def unsubscribe_all(self, command):
        """
        Removes all notifications subscriptions
        """
        user = command.message.author.id
        deleted, _ = GameNotification.objects.filter(user=user).delete()
        yield from command.reply('Unsubscribed you from {num} games'.format(num=deleted))

    @command()
    def list(self, command):
        """
        Lists the current notification subscriptions
        """
        user = command.message.author.id
        games = GameNotification.objects.filter(user=user).values_list('game_name', flat=True)
        msg = 'You\'re susbcribed to: {games}'.format(games=', '.join(games))
        yield from command.reply(msg)
