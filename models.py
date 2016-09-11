"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

from __future__ import division
from datetime import date

from protorpc import messages
from google.appengine.ext import ndb

import time
import random
import json

ALLOWED_NUM_OF_LETTERS = [5, 6, 7]

FIVE_LETTER_WORDS = ['music', 'night', 'house', 'earth', 'paper']
RESERVE = ['family', 'mother', 'father', 'school', 'friend']
SIX_LETTER_WORDS = ['school']
SEVEN_LETTER_WORDS = ['sparkle', 'firefly', 'freckle', 'stellar', 'acrobat']


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    wins = ndb.FloatProperty()
    avg_attempts_remaining = ndb.FloatProperty()

    def rank_to_form(self):
        """Returns a UserRankForm representation of user rank"""
        form = UserRankForm()
        form.user_name = self.name
        form.wins = self.wins
        form.avg_attempts_remaining = self.avg_attempts_remaining

        return form


class Game(ndb.Model):
    """Game object"""
    word = ndb.StringProperty(required=True)
    attempts_allowed = ndb.IntegerProperty(required=True)
    attempts_remaining = ndb.IntegerProperty(required=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    all_results = ndb.StringProperty(repeated=True)

    @classmethod
    def new_game(cls, user, number_of_letters, attempts):
        """Creates and returns a new game"""
        if not attempts > 0:
            raise ValueError('Number of attempts must be a positive number.')
        if number_of_letters not in ALLOWED_NUM_OF_LETTERS:
            raise ValueError('Number of letters can only be 5, 6, or 7!')

        # choose a random word based on the number of letters specified
        if number_of_letters == 5:
            words = FIVE_LETTER_WORDS
        elif number_of_letters == 6:
            words = SIX_LETTER_WORDS
        else:
            words = SEVEN_LETTER_WORDS

        game = Game(user=user,
                    word=random.choice(words),
                    attempts_allowed=attempts,
                    attempts_remaining=attempts,
                    game_over=False)
        game.put()
        return game

    def to_form(self, result={}):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.attempts_remaining = self.attempts_remaining
        form.game_over = self.game_over
        form.number_of_letters = len(self.word)
        # if there are guess results, return a form representation of
        # that too
        if result:
            result_form = Game.result_to_form(result)
            form.result = result_form

        return form

    @classmethod
    def result_to_form(cls, result):
        """Returns a GuessResultForm representation of guess results"""
        result_form = GuessResultForm()
        result_form.guess = result['guess']
        result_form.hit = result['hit']
        # only set the letter_position attribute if relevant
        if result.get('letter_pos'):
            result_form.letter_position = result['letter_pos']

        return result_form

    def end_game(self, won=False):
        """Ends the game - if won is True, the player won.
        if won is False, the player lost.  Updates the scoreboard
        and user rankings."""
        self.game_over = True
        self.put()
        # convert attempts_remaining to a ratio presented as a decimal value
        attempts_remaining = self.attempts_remaining / self.attempts_allowed
        score = Score(user=self.user, date=date.today(), won=won,
                      attempts_remaining=attempts_remaining,
                      number_of_letters=len(self.word))

        user = self.user.get()
        # get all games already played and all games already won
        prev_games_played = Score.query(Score.user == user.key)
        prev_games_won = prev_games_played.filter(Score.won == True)  # noqa
        # add one to games played, add one to games won if they won
        games_played = prev_games_played.count() + 1
        games_won = prev_games_won.count()
        if won:
            games_won = prev_games_won.count() + 1
        # update the user's ratio of wins as a decimal value
        user.wins = games_won / games_played

        all_attempts_remaining = []
        # add all previous attempts_remaining to all_attempts_remaining
        for game in prev_games_played:
            all_attempts_remaining.append(game.attempts_remaining)
        # add current attempts_remaining to all_attempts_remaining
        all_attempts_remaining.append(attempts_remaining)
        # update the average number of attempts_remaining over all games.
        user.avg_attempts_remaining = \
            sum(all_attempts_remaining) / games_played

        score.put()
        user.put()


class Score(ndb.Model):
    """Score object"""
    user = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    attempts_remaining = ndb.FloatProperty(required=True)
    number_of_letters = ndb.IntegerProperty(required=True)

    def to_form(self):
        # define attempts_remaining as a floating point number
        return ScoreForm(user_name=self.user.get().name, won=self.won,
                         date=str(self.date),
                         number_of_letters=self.number_of_letters,
                         attempts_remaining=self.attempts_remaining)


class GuessResultForm(messages.Message):
    """GuessResultForm to be used for outbound game state information"""
    guess = messages.StringField(1, required=True)
    hit = messages.BooleanField(2, required=True)
    letter_position = messages.IntegerField(3, repeated=True)


class GuessResultForms(messages.Message):
    """Return multiple GuessResultForms"""
    items = messages.MessageField(GuessResultForm, 1, repeated=True)


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    user_name = messages.StringField(5, required=True)
    number_of_letters = messages.IntegerField(6, required=True)
    result = messages.MessageField(GuessResultForm, 7)


class GameForms(messages.Message):
    """Return multiple GameForms"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)
    number_of_letters = messages.IntegerField(2, default=6)
    attempts = messages.IntegerField(3, default=6)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    attempts_remaining = messages.FloatField(4, required=True)
    number_of_letters = messages.IntegerField(5, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class UserRankForm(messages.Message):
    """UserRankForm for outbound user rank information"""
    user_name = messages.StringField(1, required=True)
    wins = messages.FloatField(2, required=True)
    avg_attempts_remaining = messages.FloatField(3, required=True)


class UserRankForms(messages.Message):
    """Return multiple UserRankForms"""
    items = messages.MessageField(UserRankForm, 1, repeated=True)


class StringMessageForm(messages.Message):
    """StringMessageForm-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
