# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import User, Game, Score
from models import StringMessageForm, NewGameForm, GameForm, MakeMoveForm,\
    ScoreForms, GameForms, GuessResultForms, UserRankForms
from utils import get_by_urlsafe

from copy import deepcopy

import endpoints
import json

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
        urlsafe_game_key=messages.StringField(1),)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))

MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'


@endpoints.api(name='hangman', version='v1')
class HangmanApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessageForm,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                    'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        return StringMessageForm(message='User {} created!'.format(
                request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        try:
            game = Game.new_game(user.key, request.number_of_letters,
                                 request.attempts)
        except ValueError as e:
            raise endpoints.BadRequestException(e)

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form()

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form()
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message."""
        # make sure the game is still on
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            raise endpoints.BadRequestException('Game already over.')
        # format the guess correctly before using it for matching
        formatted_guess = request.guess.strip().lower()

        # make sure the guess does not contain any special characters
        if not formatted_guess.isalpha():
            raise endpoints.BadRequestException(
                'Your guess can only contain alphabet letters.')
        # make sure the guess is of an appropriate length
        if len(formatted_guess) not in (1, len(game.word)):
            raise endpoints.BadRequestException(
                'Your guess must either be a single letter, or a guess for the entire word.')  # noqa
        # make sure the user has not guessed this already
        if game.all_results:
            for result in game.all_results:
                if formatted_guess == (json.loads(result))['guess']:
                    raise endpoints.BadRequestException(
                        'You already guessed that!')

        result = {'guess': formatted_guess}
        # if the user guesses the whole word right, they win
        if formatted_guess == game.word:
            result['hit'] = True
            game.end_game(True)

        # if the user guesses a single letter, and they're right
        if formatted_guess in game.word:
            result['hit'] = True
            letter_pos = [pos for pos, letter in enumerate(game.word)
                          if letter == formatted_guess]
            for x in letter_pos:
                game.reveal[x] = formatted_guess
        # if they user guesses a single letter, and they're wrong
        if formatted_guess not in game.word:
            game.attempts_remaining -= 1
            result['hit'] = False

        # if the user has no more attempts remaining, they lose
        if game.attempts_remaining < 1:
            game.end_game(False)

        # add guess results to game history, committ changes,
        # return gameform representation of game state
        result['word'] = deepcopy(game.reveal)
        game.all_results.append(json.dumps(result))
        game.put()
        return game.to_form(result)

    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        return ScoreForms(items=[score.to_form() for score in Score.query()])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(response_message=StringMessageForm,
                      path='games/average_attempts',
                      name='get_average_attempts_remaining',
                      http_method='GET')
    def get_average_attempts(self, request):
        """Get the cached average moves remaining"""
        return StringMessageForm(
            message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=GameForms,
                      path='games/user/{user_name}',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """ Gets all of a user's active games"""
        # TODO: make all games descendants of a user

        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        games = Game.query(Game.user == user.key, Game.game_over == False)  # noqa

        return GameForms(items=[game.to_form() for game in games])

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessageForm,
                      path='cancel/game/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Cancels in progress games"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('Game not found!')
        if game.game_over:
            raise endpoints.BadRequestException(
                'Completed games cannot be cancelled')
        game.key.delete()

        return StringMessageForm(message='Game successfully cancelled.')

    @endpoints.method(response_message=ScoreForms,
                      path='high_scores',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """returns a list of high scores"""
        scores = Score.query().order(-Score.attempts_remaining,
                                     -Score.number_of_letters)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(response_message=UserRankForms,
                      path='user_rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """returns all users ranked by performance"""
        users = User.query().order(-User.wins,
                                   -User.avg_attempts_remaining)
        return UserRankForms(items=[user.rank_to_form() for user in users])

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GuessResultForms,
                      path='history/{urlsafe_game_key}',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Get game history"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('Game not found!')
        if not game.all_results:
            raise endpoints.NotFoundException('Game history not found!')

        return GuessResultForms(
            items=[Game.result_to_form(json.loads(result))
                   for result in game.all_results])

    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over == False).fetch()  # noqa
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining
                                            for game in games])
            average = float(total_attempts_remaining)/count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'
                         .format(average))


api = endpoints.api_server([HangmanApi])
