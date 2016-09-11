## Set-Up Instructions:
1.  Make sure you have the Python Google App Engine SDK installed and configured
 on your machine.
2.  Update the value of application in app.yaml to a app ID you have registered
 in the App Engine admin console and would like to use to host your instance of this sample.
3.  Run the app with the devserver using dev_appserver.py DIR, and ensure it's
 running by visiting the API Explorer - by default localhost:8080/_ah/api/explorer.

##Game Description:
Hangman is a word guessing game. Each game begins with a random word, and a maximum number of
'attempts'.  The number of letters in the target word and the maximum number of attempts can
both be specified by the user (as of now, the allowed number of letters in the target word
are 5, 6, or 7). The allowed number of attempts only decreases when you make
a wrong guess. 'Guesses' are sent to the `make_move` endpoint which will reply with the
following information:

 - 'word'
    - before any guess is made, the initial state of 'word' is all blank spaces
    - letters replace the appropriate blank space(s) when a guess is correct
 - 'hit' (true if the guess was correct)
 - 'attempts_remaining'
 - 'game over' (if the maximum number of attempts is reached, or the correct word is guessed).

Many different Hangman games can be played by many different Users at any
given time. Each game can be retrieved or played by using the path parameter
`urlsafe_game_key`.

##Scoring Information:
Individual games are ranked according to its score's attempts_remaining attribute.
Note that this is different from a game's attempts_remaining attribute.  The
attribute for a game is a whole number that decrements during the course of the
game.  The attribute for a score is a decimal value calculated after the game
is over, using the game's final attempts_remaining value divided by the number of
attempts_allowed.  Ties are broken according to the number of letters of the
target word.  A longer word corresponds to a higher score, while a shorter word
corresponds to a lower score.

Users are ranked according to their number of wins relative to the total number of games
they have played (calculated as a decimal value).  Ties are broken according to a user's
average_attempts_remaining attribute.  A higher number of attempts remaining throughout
all games played corersponds to a higher score, while a lower number of attempts
remaining throughout all games played corresponds to a lower score.

##Files Included:
 - api.py: Contains endpoints and game playing logic.
 - app.yaml: App configuration.
 - cron.yaml: Cronjob configuration.
 - main.py: Handler for taskqueue handler.
 - models.py: Entity and message definitions including helper methods.
 - utils.py: Helper function for retrieving ndb.Models by urlsafe Key string.

## Basic Endpoints Included:
 - **create_user**
    - Path: 'user'
    - Method: POST
    - Parameters: user_name, email (optional)
    - Returns: Message confirming creation of the User.
    - Description: Creates a new User. user_name provided must be unique. Will
    raise a ConflictException if a User with that user_name already exists.

 - **new_game**
    - Path: 'game'
    - Method: POST
    - Parameters: user_name, number_of_letters, attempts
    - Returns: GameForm with initial game state.
    - Description: Creates a new Game. user_name provided must correspond to an
    existing user - will raise a NotFoundException if not. Also adds a task to
    a task queue to update the average moves remaining for active games.

 - **get_game**
    - Path: 'game/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: GameForm with current game state.
    - Description: Returns the current state of a game.

 - **make_move**
    - Path: 'game/{urlsafe_game_key}'
    - Method: PUT
    - Parameters: urlsafe_game_key, guess
    - Returns: GameForm with new game state and guess result.
    - Description: Accepts a 'guess' and returns the updated state of the game.
    If this causes a game to end, a corresponding Score entity will be created.

 - **get_scores**
    - Path: 'scores'
    - Method: GET
    - Parameters: None
    - Returns: ScoreForms.
    - Description: Returns all Scores in the database (unordered).

 - **get_user_scores**
    - Path: 'scores/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: ScoreForms.
    - Description: Returns all Scores recorded by the provided player (unordered).
    Will raise a NotFoundException if the User does not exist.

 - **get_average_attempts**
    - Path: 'games/average_attempts'
    - Method: GET
    - Parameters: None
    - Returns: StringMessageForm
    - Description: Gets the average number of attempts remaining for all games
    from a previously cahced memcache key.

## Additional Endpoints Included:
 - **get_user_games**
    - Path: 'games/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: GameForms
    - Description: Gets all of a user's active games.
    Will raise a NotFoundException if the User does not exist.

 - **cancel_game**
    - Path: 'cancel/game/{urlsafe_game_key}'
    - Method: DELETE
    - Parameters: urlsafe_game_key
    - Returns: StringMessageForm
    - Description: Cancels an in progress game.
    Will raise a NotFoundException if the game does not exist.
    Will raise a BadRequestException if the user tries to cancel an already
    completed game.

 - **get_high_scores**
    - Path: 'high_scores'
    - Method: GET
    - Parameters: None
    - Returns: ScoreForms
    - Description: Returns all Scores recorded.  Scores are ordered by the
    attempts_remaining attribute for scores.  Ties are broken by the
    number_of_letters attribute for scores.

 - **get_user_rankings**
    - Path: 'user_rankings'
    - Method: GET
    - Parameters: None
    - Returns: UserRankForms
    - Description: Returns all user rankings recorded.  User rankings are ordered
    by the wins attribute for users.  Ties are broken by the avg_attempts_remaining
    attribute for users.

 - **get_game_history**
    - Path: 'history/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: GuessResultForms
    - Description: Returns all guess result history for a given game.
    Will raise a NotFoundException if the game does not exist.
    Will raise a NotFoundException if no game history exists.

##Models Included:
 - **User**
    - Stores unique user_name and (optional) email address.

 - **Game**
    - Stores unique game states. Associated with User model via KeyProperty.

 - **Score**
    - Records completed games. Associated with Users model via KeyProperty.

##Forms Included:
 - **GameForm**
    - Representation of a Game's state (urlsafe_key, attempts_remaining,
    game_over flag, message, user_name).
 - **GameForms**
    - Multiple GameForm container.

 - **NewGameForm**
    - Used to create a new game (user_name, min, max, attempts)

 - **MakeMoveForm**
    - Inbound make move form (guess).

 - **GuessResultForm**
    - Representation of the results of the user's guess.
 - **GuessResultForms**
    - Multiple GuessResultForm container.

 - **ScoreForm**
    - Representation of a completed game's Score (user_name, date, won flag,
    guesses).
 - **ScoreForms**
    - Multiple ScoreForm container.

 - **UserRankForm**
    - Representation of a user's rank information.
 - **UserRankForms**
    - Multiple UserRankForm container.

 - **StringMessageForm**
    - General purpose String container.