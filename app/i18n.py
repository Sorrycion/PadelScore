"""UI texts in Spanish (default) and English.

Templates call `_("key", **values)`. A text can be a (singular, plural) pair, picked
by the `n` value. Texts are trusted HTML (some contain links); the values are
escaped when they are filled in.
"""
from markupsafe import Markup, escape

LANGS = ("es", "en")
DEFAULT_LANG = "es"
COOKIE = "lang"

TEXT = {
    # Navigation
    "nav_standings": {"es": "Clasificación", "en": "Standings"},
    "nav_tournaments": {"es": "Torneos", "en": "Tournaments"},
    "nav_sets": {"es": "Sets", "en": "Sets"},
    "nav_players": {"es": "Jugadores", "en": "Players"},
    "nav_rules": {"es": "Reglamento", "en": "Rules"},
    "nav_courts": {"es": "+ Canchas", "en": "+ Courts"},

    # Shared words
    "standings": {"es": "Clasificación", "en": "Standings"},
    "tournaments": {"es": "Torneos", "en": "Tournaments"},
    "players": {"es": "Jugadores", "en": "Players"},
    "player": {"es": "Jugador", "en": "Player"},
    "sets": {"es": "Sets", "en": "Sets"},
    "matchday": {"es": "Jornada", "en": "Matchday"},
    "matchdays": {"es": "Jornadas", "en": "Matchdays"},
    "matchday_n": {"es": "Jornada {n}", "en": "Matchday {n}"},
    "matchday_short": {"es": "J{n}", "en": "M{n}"},
    "court": {"es": "Cancha", "en": "Court"},
    "court_n": {"es": "Cancha {n}", "en": "Court {n}"},
    "pts": {"es": "Pts", "en": "Pts"},
    "games_diff": {"es": "± Juegos", "en": "± Games"},
    "games_diff_title": {"es": "Juegos ganados menos juegos perdidos",
                         "en": "Games won minus games lost"},
    "sets_won": {"es": "Sets ganados", "en": "Sets won"},
    "partners": {"es": "Compañeros", "en": "Partners"},
    "edit": {"es": "Editar", "en": "Edit"},
    "delete": {"es": "Eliminar", "en": "Delete"},
    "confirm_delete_set": {"es": "¿Eliminar este set?", "en": "Delete this set?"},
    "choose": {"es": "Elegir…", "en": "Choose…"},
    "save": {"es": "Guardar", "en": "Save"},
    "pending": {"es": "Pendiente", "en": "Pending"},
    "latest": {"es": "última", "en": "latest"},
    "n_sets": {"es": ("{n} set", "{n} sets"), "en": ("{n} set", "{n} sets")},
    "n_courts": {"es": ("{n} cancha", "{n} canchas"), "en": ("{n} court", "{n} courts")},
    "n_matchdays": {"es": ("{n} jornada", "{n} jornadas"),
                    "en": ("{n} matchday", "{n} matchdays")},
    "n_players": {"es": ("{n} jugador", "{n} jugadores"), "en": ("{n} player", "{n} players")},
    "n_points": {"es": ("{n} punto", "{n} puntos"), "en": ("{n} point", "{n} points")},
    "n_sets_won": {"es": ("{n} set ganado", "{n} sets ganados"),
                   "en": ("{n} set won", "{n} sets won")},
    "n_matchdays_played": {"es": ("{n} jornada jugada", "{n} jornadas jugadas"),
                           "en": ("{n} matchday played", "{n} matchdays played")},
    "position_n": {"es": "Posición {n}", "en": "Position {n}"},

    # Home
    "latest_sets": {"es": "Últimos sets", "en": "Latest sets"},
    "all_sets_tournament": {"es": "Todos los sets de este torneo →",
                            "en": "All sets in this tournament →"},
    "no_tournaments_start": {
        "es": 'Aún no hay torneos. <a href="{url}">Crea un torneo</a> para empezar.',
        "en": 'No tournaments yet. <a href="{url}">Create a tournament</a> to get started.'},
    "no_matchdays_add": {
        "es": 'Aún no hay jornadas. <a href="{url}">Agrega la primera jornada</a>.',
        "en": 'No matchdays yet. <a href="{url}">Add the first matchday</a>.'},
    "no_sets_record": {
        "es": 'Aún no hay sets registrados. <a href="{url}">Registra el primero</a>.',
        "en": 'No sets recorded yet. <a href="{url}">Record the first one</a>.'},

    # Standings
    "no_results": {"es": "Aún no hay resultados en este torneo.",
                   "en": "No results in this tournament yet."},

    # Tournaments
    "tournament_name": {"es": "Nombre del torneo", "en": "Tournament name"},
    "add_tournament": {"es": "Agregar torneo", "en": "Add tournament"},
    "no_tournaments": {"es": "Aún no hay torneos.", "en": "No tournaments yet."},
    "no_matchdays": {"es": "Aún no hay jornadas.", "en": "No matchdays yet."},
    "add_matchday_n": {"es": "Agregar jornada {n}", "en": "Add matchday {n}"},
    "delete_tournament": {"es": "Eliminar torneo", "en": "Delete tournament"},
    "confirm_delete_tournament": {
        "es": "¿Eliminar este torneo con todas sus jornadas y sets? No se puede deshacer.",
        "en": "Delete this tournament with all its matchdays and sets? This cannot be undone."},
    "six_matchdays": {"es": "El reglamento contempla 6 jornadas por liga.",
                      "en": "The rules plan 6 matchdays per league."},

    # Matchday
    "record_set_button": {"es": "+ Registrar set", "en": "+ Record set"},
    "places_note": {
        "es": 'Puntos por set, sin importar la cancha: la pareja ganadora 9 + 1 por set ganado '
              '(10 cada uno), la perdedora 6; un set empatado da 9 a los cuatro. El orden en '
              'la cancha (puntos, diferencia de juegos, posición en el ranking) solo decide '
              'los cambios de cancha. <a href="{url}">Reglamento</a>',
        "en": 'Points per set, whatever the court: the winning pair 9 + 1 for the set won '
              '(10 each), the losing pair 6; a tied set gives 9 to all four. The order on '
              'the court (points, games difference, league position) only decides court '
              'changes. <a href="{url}">Rules</a>'},
    "add_set_on_court": {"es": "+ Set en cancha {n}", "en": "+ Set on court {n}"},
    "sets_recorded": {"es": "{n} de 3 sets registrados.", "en": "{n} of 3 sets recorded."},
    "court_changes": {"es": "Cambios de cancha", "en": "Court changes"},
    "per_draw_move": {"es": "Según el sorteo, cambian", "en": "Per the draw, move"},
    "move_up": {"es": "↑ a cancha {n}:", "en": "↑ to court {n}:"},
    "move_down": {"es": "↓ a cancha {n}:", "en": "↓ to court {n}:"},
    "no_changes": {"es": "sin cambios", "en": "no changes"},

    "no_courts_yet": {
        "es": 'Aún no hay canchas. <a href="{url}">Asigna los jugadores a las canchas</a>.',
        "en": 'No courts yet. <a href="{url}">Assign the players to courts</a>.'},

    # Courts of a matchday
    "assign_courts": {"es": "Asignar canchas", "en": "Assign courts"},
    "assign_courts_hint": {
        "es": "Pon 4 jugadores en cada cancha. Al guardar se crean los 3 sets de cada cancha, "
              "con un compañero distinto en cada set. Los resultados se registran después en "
              "la página de la jornada.",
        "en": "Put 4 players on each court. Saving creates each court's 3 sets, with a "
              "different partner in each set. Results are entered afterwards on the "
              "matchday page."},
    "suggested_from": {
        "es": "Sugerencia según la jornada {n}; cámbiala si hace falta.",
        "en": "Suggested from matchday {n}; change it as needed."},
    "courts_change_warning": {
        "es": "Si cambias los jugadores de una cancha, sus sets se crean de nuevo. Una cancha "
              "que ya tiene resultados no se puede cambiar.",
        "en": "Changing a court's players creates its sets again. A court that already has "
              "results can't be changed."},
    "add_court": {"es": "+ Agregar cancha", "en": "+ Add court"},
    "remove_court": {"es": "Quitar", "en": "Remove"},
    "save_courts": {"es": "Guardar y crear sets", "en": "Save and create sets"},
    "new_matchday_n": {"es": "Nueva jornada {n}", "en": "New matchday {n}"},
    "save_matchday": {"es": "Guardar jornada", "en": "Save matchday"},
    "nothing_saved_yet": {
        "es": "La jornada aún no está guardada: revisa las canchas y pulsa «Guardar jornada».",
        "en": "The matchday isn't saved yet: review the courts and press “Save matchday”."},
    "move_question": {"es": "¿Cuántos jugadores suben y bajan en cada cancha?",
                      "en": "How many players move up and down on each court?"},
    "move_note": {
        "es": "Según la jornada {n}. En la cancha 1 los mejores se quedan (no pueden subir) y "
              "en la última cancha los últimos se quedan (no pueden bajar). Luego podrás mover "
              "a los jugadores.",
        "en": "From matchday {n}. On court 1 the best stay (they can't go up) and on the last "
              "court the last ones stay (they can't go down). You can move players afterwards."},
    "moves_per_court": {"es": "Suben y bajan por cancha:", "en": "Moving per court:"},
    "cancel": {"es": "Cancelar", "en": "Cancel"},
    "date": {"es": "Fecha", "en": "Date"},

    # Sets list
    "all_tournaments": {"es": "Todos los torneos", "en": "All tournaments"},
    "all_players": {"es": "Todos los jugadores", "en": "All players"},
    "filter": {"es": "Filtrar", "en": "Filter"},
    "clear": {"es": "Limpiar", "en": "Clear"},
    "no_sets_filter": {"es": "Ningún set coincide con este filtro.",
                       "en": "No sets match this filter."},
    "no_sets_yet": {
        "es": 'Aún no hay sets. <a href="{url}">Registra el primero</a>.',
        "en": 'No sets yet. <a href="{url}">Record the first one</a>.'},

    # Set form
    "new_set": {"es": "Nuevo set", "en": "New set"},
    "edit_set": {"es": "Editar set", "en": "Edit set"},
    "record_set": {"es": "Registrar un set", "en": "Record a set"},
    "need_4_players": {
        "es": 'Necesitas al menos 4 jugadores. <a href="{url}">Agrega jugadores</a>.',
        "en": 'You need at least 4 players. <a href="{url}">Add players</a>.'},
    "need_matchday": {
        "es": 'Primero agrega una jornada: abre un <a href="{url}">torneo</a> y agrega una jornada.',
        "en": 'Add a matchday first: open a <a href="{url}">tournament</a> and add a matchday.'},
    "where": {"es": "Dónde", "en": "Where"},
    "team_a": {"es": "Pareja A", "en": "Team A"},
    "team_b": {"es": "Pareja B", "en": "Team B"},
    "player_1": {"es": "Jugador 1", "en": "Player 1"},
    "player_2": {"es": "Jugador 2", "en": "Player 2"},
    "games_legend": {"es": "Juegos", "en": "Games"},
    "save_set": {"es": "Guardar set", "en": "Save set"},
    "save_changes": {"es": "Guardar cambios", "en": "Save changes"},
    "games_later": {"es": "Deja los juegos vacíos si el set aún no se ha jugado.",
                    "en": "Leave the games empty if the set hasn't been played yet."},

    # Players
    "player_name": {"es": "Nombre del jugador", "en": "Player name"},
    "add_player": {"es": "Agregar jugador", "en": "Add player"},
    "no_players": {"es": "Aún no hay jugadores.", "en": "No players yet."},
    "rename": {"es": "Cambiar nombre", "en": "Rename"},
    "delete_player": {"es": "Eliminar jugador", "en": "Delete player"},
    "confirm_delete_player": {"es": "¿Eliminar este jugador?", "en": "Delete this player?"},
    "no_matchdays_played": {"es": "Aún no ha jugado ninguna jornada.",
                            "en": "No matchdays played yet."},

    # Login
    "login": {"es": "Entrar", "en": "Log in"},
    "logout": {"es": "Salir", "en": "Log out"},
    "login_title": {"es": "Entrar para editar", "en": "Log in to edit"},
    "login_hint": {"es": "Cualquiera puede ver los resultados. Para registrar o cambiar datos "
                         "se necesita la contraseña del club.",
                   "en": "Anyone can see the results. Recording or changing data needs the "
                         "club password."},
    "club_password": {"es": "Contraseña del club", "en": "Club password"},
    "err_wrong_password": {"es": "Contraseña incorrecta.", "en": "Wrong password."},

    # Rules
    "rules_spanish_only": {"es": "", "en": "The rules are only available in Spanish."},

    # Errors
    "err_name_required": {"es": "El nombre es obligatorio.", "en": "Name is required."},
    "err_player_exists": {"es": "Ese jugador ya existe.", "en": "That player already exists."},
    "err_invalid_date": {"es": "Ingresa una fecha válida.", "en": "Enter a valid date."},
    "err_four_players": {"es": "Elige cuatro jugadores diferentes.",
                         "en": "Pick four different players."},
    "err_pick_matchday": {"es": "Elige una jornada.", "en": "Pick a matchday."},
    "err_court": {"es": "La cancha debe ser 1 o mayor.", "en": "Court must be 1 or higher."},
    "err_both_games": {"es": "Ingresa los juegos de las dos parejas, o deja ambos vacíos.",
                       "en": "Enter both teams' games, or leave both empty."},
    "err_need_court": {"es": "Agrega al menos una cancha con 4 jugadores.",
                       "en": "Add at least one court with 4 players."},
    "err_court_four": {"es": "Cancha {n}: elige 4 jugadores diferentes.",
                       "en": "Court {n}: pick 4 different players."},
    "err_player_two_courts": {"es": "{name} está en más de una cancha.",
                              "en": "{name} is on more than one court."},
    "err_court_has_scores": {
        "es": "La cancha {n} ya tiene resultados. Para cambiar sus jugadores, primero elimina "
              "esos sets.",
        "en": "Court {n} already has results. To change its players, delete those sets "
              "first."},
    "err_player_has_sets": {
        "es": "No se puede eliminar: este jugador tiene sets en alguna jornada.",
        "en": "Can't delete: this player has sets on a matchday."},
    "err_set": {"es": "Los juegos no pueden ser negativos.",
                "en": "Games can't be negative."},
}


def get_lang(request) -> str:
    lang = request.cookies.get(COOKIE)
    return lang if lang in LANGS else DEFAULT_LANG


def translator(lang: str):
    def _(key, n=None, **values):
        entry = TEXT.get(key)
        if entry is None:
            return escape(key)
        text = entry[lang]
        if isinstance(text, tuple):
            text = text[0] if n == 1 else text[1]
        return Markup(text).format(n=n, **values)
    return _


def i18n_context(request) -> dict:
    """Jinja context processor: the `_` translator and current `lang` for every page."""
    lang = get_lang(request)
    return {"_": translator(lang), "lang": lang, "langs": LANGS}
