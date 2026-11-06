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
    "nav_courts": {"es": "🎾 Canchas", "en": "🎾 Courts"},

    # Shared words
    "standings": {"es": "🏆 Clasificación", "en": "🏆 Standings"},
    "tournaments": {"es": "🏟️ Torneos", "en": "🏟️ Tournaments"},
    "players": {"es": "👥 Jugadores", "en": "👥 Players"},
    "player": {"es": "Jugador", "en": "Player"},
    "sets": {"es": "🎾 Sets", "en": "🎾 Sets"},
    "matchday": {"es": "Jornada", "en": "Matchday"},
    "matchdays": {"es": "📅 Jornadas", "en": "📅 Matchdays"},
    "matchday_n": {"es": "Jornada {n}", "en": "Matchday {n}"},
    "matchday_short": {"es": "J{n}", "en": "M{n}"},
    "court": {"es": "Cancha", "en": "Court"},
    "court_n": {"es": "🎾 Cancha {n}", "en": "🎾 Court {n}"},
    "pts": {"es": "Pts", "en": "Pts"},
    "games_diff": {"es": "± Juegos", "en": "± Games"},
    "games_diff_title": {"es": "Juegos ganados menos juegos perdidos",
                         "en": "Games won minus games lost"},
    "points_diff": {"es": "± Puntos", "en": "± Points"},
    "wins": {"es": "✅ Victorias", "en": "✅ Wins"},
    "sets_won": {"es": "Sets ganados", "en": "Sets won"},
    "partners": {"es": "🤝 Compañeros", "en": "🤝 Partners"},
    "edit": {"es": "✏️ Editar", "en": "✏️ Edit"},
    "delete": {"es": "🗑️ Eliminar", "en": "🗑️ Delete"},
    "confirm_delete_set": {"es": "¿Eliminar este set?", "en": "Delete this set?"},
    "choose": {"es": "Elegir…", "en": "Choose…"},
    "save": {"es": "💾 Guardar", "en": "💾 Save"},
    "pending": {"es": "⏳ Pendiente", "en": "⏳ Pending"},
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
    "latest_sets": {"es": "🕒 Últimos sets", "en": "🕒 Latest sets"},
    "recap_title": {"es": "Mi jornada", "en": "My matchday"},
    "recap_latest": {"es": "Tu última jornada", "en": "Your latest matchday"},
    "recap_sets_won": {"es": "Sets ganados", "en": "Sets won"},
    "recap_ranking": {"es": "Clasificación", "en": "Standings"},
    "recap_next_court": {"es": "Cancha próxima jornada", "en": "Next matchday's court"},
    "recap_whatsapp": {"es": "Compartir por WhatsApp", "en": "Share on WhatsApp"},
    "recap_medals": {"es": "Medallas de la jornada", "en": "Medals of the matchday"},
    "recap_sets": {"es": "Sus sets", "en": "Their sets"},
    "recap_see_tournament": {"es": "Ver el torneo", "en": "See the tournament"},
    "recap_not_played": {"es": "No jugó esta jornada.", "en": "Didn't play this matchday."},
    "recap_share_head": {"es": "🎾 {name} · {tournament} · Jornada {n}",
                         "en": "🎾 {name} · {tournament} · Matchday {n}"},
    "recap_share_court": {"es": "🏅 {place}.º en la cancha {court} · {points} pts · "
                                "{won}/{sets} sets ganados",
                          "en": "🏅 {place} on court {court} · {points} pts · "
                                "{won}/{sets} sets won"},
    "recap_share_absent": {"es": "🚫 Ausente esta jornada", "en": "🚫 Absent this matchday"},
    "recap_share_rank": {"es": "📈 Clasificación: {n}.º", "en": "📈 Standings: #{n}"},
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
    "rule_type": {"es": "📖 Tipo de reglas", "en": "📖 Rules type"},
    "create_tournament": {"es": "➕ Crear torneo", "en": "➕ Create tournament"},
    "n_players_bold": {"es": ("<strong>{n}</strong> jugador", "<strong>{n}</strong> jugadores"),
                       "en": ("<strong>{n}</strong> player", "<strong>{n}</strong> players")},
    "n_matchdays_bold": {"es": ("<strong>{n}</strong> jornada", "<strong>{n}</strong> jornadas"),
                         "en": ("<strong>{n}</strong> matchday", "<strong>{n}</strong> matchdays")},
    "n_rounds_bold": {"es": ("<strong>{n}</strong> ronda", "<strong>{n}</strong> rondas"),
                      "en": ("<strong>{n}</strong> round", "<strong>{n}</strong> rounds")},
    "player_password": {"es": "🔑 Contraseña de jugadores", "en": "🔑 Player password"},
    "player_password_hint": {
        "es": "Con esta contraseña los jugadores entran y registran los resultados de los sets "
              "de este torneo (y en Manual individual crean sets). Nada más.",
        "en": "With this password players log in and enter the set results of this tournament "
              "(and create sets in Manual individual). Nothing else."},
    "current_password": {"es": "🔑 Contraseña actual", "en": "🔑 Current password"},
    "player_password_on": {
        "es": "✅ Solo la ven los administradores. Escribe una nueva para cambiarla, o guarda "
              "vacío para volver a la predeterminada (el nombre del torneo en minúsculas, con _ "
              "entre palabras).",
        "en": "✅ Only admins see it. Type a new one to change it, or save it empty to go back "
              "to the default (the tournament's name in lowercase, with _ between words)."},
    "new_password": {"es": "Nueva contraseña", "en": "New password"},
    "search_player": {"es": "🔍 Buscar jugador…", "en": "🔍 Search player…"},
    "add": {"es": "➕ Agregar", "en": "➕ Add"},
    "create_player_option": {"es": "➕ Crear jugador «{name}»", "en": "➕ Create player “{name}”"},
    "add_to_tournament": {"es": "➕ Agregar al torneo", "en": "➕ Add to tournament"},
    "current_tournaments": {"es": "En curso", "en": "Current"},
    "past_tournaments": {"es": "Pasados", "en": "Past"},
    "no_past_tournaments": {"es": "Todavía no hay torneos terminados.",
                            "en": "No tournaments have ended yet."},
    "tournament_ended": {"es": "🏁 Terminado", "en": "🏁 Ended"},
    "season_title": {"es": "🏁 Resumen del torneo", "en": "🏁 Tournament summary"},
    "season_link": {"es": "🏁 Resumen", "en": "🏁 Summary"},
    "season_final": {"es": "Resultado final", "en": "Final result"},
    "season_so_far": {"es": "Hasta ahora", "en": "So far"},
    "podium": {"es": "Podio", "en": "Podium"},
    "hl_best_day": {"es": "Mejor jornada", "en": "Best matchday"},
    "best_day_value": {"es": "{points} pts en la J{n}", "en": "{points} pts on M{n}"},
    "hl_streak": {"es": "Racha más larga", "en": "Longest streak"},
    "hl_sets_won": {"es": "Más sets ganados", "en": "Most sets won"},
    "hl_diff": {"es": "Mejor diferencia de juegos", "en": "Best games difference"},
    "hl_court1": {"es": "Más veces en la cancha 1", "en": "Most often on court 1"},
    "hl_pair": {"es": "Dupla del torneo", "en": "Pair of the tournament"},
    "ever_present": {"es": "No faltaron a ninguna jornada", "en": "Never missed a matchday"},
    "season_medals": {"es": "Medallas del torneo", "en": "The tournament's medals"},
    "end_tournament": {"es": "🏁 Terminar torneo", "en": "🏁 End tournament"},
    "reopen_tournament": {"es": "↩️ Reabrir torneo", "en": "↩️ Reopen tournament"},
    "end_tournament_hint": {
        "es": "Un torneo terminado pasa a Torneos pasados; sus resultados se conservan y "
              "puedes reabrirlo cuando quieras.",
        "en": "An ended tournament moves to Past tournaments; its results are kept and you "
              "can reopen it any time."},
    "replace": {"es": "🔁 Reemplazar", "en": "🔁 Replace"},
    "replace_name": {"es": "Reemplazar a {name}", "en": "Replace {name}"},
    "replace_player": {"es": "Reemplazar a un jugador", "en": "Replace a player"},
    "replace_who": {"es": "Sale", "en": "Leaves"},
    "replace_with": {"es": "Entra", "en": "Comes in"},
    "replace_hint": {
        "es": "El nuevo jugador toma su lugar en la lista y en los sets sin jugar. Elige qué "
              "pasa con los sets ya jugados y sus puntos.",
        "en": "The new player takes their place in the list and in the sets not played yet. "
              "Choose what happens to the sets already played and their points."},
    "replace_points": {"es": "🎯 Puntos ya jugados", "en": "🎯 Points already played"},
    "replace_keep": {"es": "Se quedan con quien sale; el nuevo empieza de cero",
                     "en": "They stay with the player who leaves; the new one starts from zero"},
    "replace_move": {"es": "Pasan al nuevo jugador: toma su lugar en todo el torneo",
                     "en": "They go to the new player, who takes their place in the whole "
                           "tournament"},
    "err_replace_conflict_all": {
        "es": "Ese jugador ya jugó con o contra quien sale en este torneo: no puede tomar sus "
              "puntos.",
        "en": "That player already played with or against the one leaving in this "
              "tournament: they can't take over their points."},
    "confirm_remove_player": {
        "es": "¿Quitar a este jugador del torneo? Sus resultados anteriores se conservan.",
        "en": "Remove this player from the tournament? Their results so far are kept."},
    "no_tournament_players": {
        "es": "Este torneo aún no tiene lista de jugadores: se puede elegir a cualquiera.",
        "en": "This tournament has no player list yet: anyone can be picked."},
    "tournament_players_edit_hint": {
        "es": 'Quita o agrega jugadores cuando quieras (por ejemplo, para reemplazar a alguien); '
              'los resultados anteriores se conservan. Si escribes un nombre nuevo, puedes '
              'crear al jugador desde aquí.',
        "en": 'Remove or add players any time (e.g. to replace someone); results so far are '
              'kept. Type a new name to create the player right here.'},
    "player_mode_note": {
        "es": "🔑 Entraste como jugador: con ✏️ Editar registras o corriges un resultado.",
        "en": "🔑 Logged in as a player: use ✏️ Edit to enter or correct a result."},
    "nav_home": {"es": "Inicio", "en": "Home"},
    "login_player_signup_hint": {
        "es": "¿No tienes cuenta? Créala. Ya adentro, escribe la contraseña de tu torneo "
              "para unirte a él.",
        "en": "No account? Make one. Once inside, type your tournament's password to "
              "join it."},
    "guest_login": {"es": "Solo anotar resultados, sin cuenta",
                    "en": "Just enter results, without an account"},
    "tournament_password": {"es": "🔑 Contraseña del torneo", "en": "🔑 Tournament password"},
    "signup_join_later": {"es": "Ya adentro, en Inicio, te unes a tus torneos con su contraseña.",
                          "en": "Then, on Home, you join your tournaments with their "
                                "password."},
    "join_title": {"es": "Unirme a un torneo", "en": "Join a tournament"},
    "join_hint": {"es": "¿Te invitaron? Escribe la contraseña del torneo.",
                  "en": "Were you invited? Type the tournament's password."},
    "join_tournament": {"es": "Unirme", "en": "Join"},
    "join_as": {"es": "Unirte como {name}", "en": "Join as {name}"},
    "who_in_tournament": {"es": "¿Quién eres en {name}?", "en": "Who are you in {name}?"},
    "pick_player_hint": {"es": "Si el admin ya te apuntó, elige tu nombre: sus sets y puntos "
                               "pasan a tu cuenta. Si no, entra como tú.",
                         "en": "If the admin already put you on the list, pick your name: "
                               "its sets and points become yours. If not, join as yourself."},
    "existing_players": {"es": "Jugadores del torneo", "en": "The tournament's players"},
    "or_join_as_me": {"es": "O entrar como yo", "en": "Or join as me"},
    "create_new_for_me": {"es": "Crear un jugador nuevo para mí ({name})",
                          "en": "Create a new player for me ({name})"},
    "confirm_merge_title": {"es": "¿{name} eres tú?", "en": "Are you {name}?"},
    "confirm_merge_hint": {"es": "Tu cuenta ya es {mine} en esta organización. Si {name} "
                                 "también eres tú, se unen en uno: sus sets y torneos pasan a "
                                 "{mine}. No se puede deshacer.",
                           "en": "Your account is already {mine} in this organization. If "
                                 "{name} is you too, they become one: their sets and "
                                 "tournaments move to {mine}. This can't be undone."},
    "confirm_merge_yes": {"es": "Sí, soy yo: unir", "en": "Yes, it's me: join them"},
    "join_as_hint": {"es": "Ya eres {name} en esta organización: entras a la lista del torneo "
                           "con tus sets y medallas de siempre.",
                     "en": "You're already {name} in this organization: you join the "
                           "tournament's list with your usual sets and medals."},
    "already_playing": {"es": "Ya juegas este torneo como {name}",
                        "en": "You already play this tournament as {name}"},
    "enter_result": {"es": "Resultado", "en": "Result"},
    "choose_org": {"es": "Elegir organización", "en": "Choose an organization"},
    "hello_name": {"es": "Hola, {name}", "en": "Hi, {name}"},
    "hello_guest": {"es": "Hola", "en": "Hi"},
    "my_upcoming_sets": {"es": "Mis próximos sets", "en": "My next sets"},
    "role_admin_short": {"es": "Admin", "en": "Admin"},
    "guest": {"es": "Invitado", "en": "Guest"},
    "guest_home_hint": {"es": "Entraste como invitado con la contraseña de un torneo. Crea "
                              "una cuenta para ver todos tus torneos juntos.",
                        "en": "You're a guest with a tournament's password. Make an account "
                              "to see all your tournaments together."},
    "home_login_title": {"es": "🎾 Bienvenido a PadelScore", "en": "🎾 Welcome to PadelScore"},
    "home_login_hint": {"es": "Entra para ver tus torneos y tus próximos sets.",
                        "en": "Log in to see your tournaments and your next sets."},
    "just_looking": {"es": "Solo mirar", "en": "Just looking"},
    "just_looking_org": {"es": "Sigue viendo la clasificación de {name} sin entrar.",
                         "en": "Keep viewing {name}'s standings without logging in."},
    "just_looking_hint": {"es": "Elige una organización para ver sus clasificaciones.",
                          "en": "Choose an organization to see its standings."},
    "add_tournament": {"es": "➕ Agregar torneo", "en": "➕ Add tournament"},
    "no_tournaments": {"es": "Aún no hay torneos.", "en": "No tournaments yet."},
    "no_matchdays": {"es": "Aún no hay jornadas.", "en": "No matchdays yet."},
    "add_matchday_n": {"es": "➕ Agregar jornada {n}", "en": "➕ Add matchday {n}"},
    "delete_tournament": {"es": "🗑️ Eliminar torneo", "en": "🗑️ Delete tournament"},
    "confirm_delete_tournament": {
        "es": "¿Eliminar este torneo con todas sus jornadas y sets? No se puede deshacer.",
        "en": "Delete this tournament with all its matchdays and sets? This cannot be undone."},
    "delete_matchday": {"es": "🗑️ Eliminar jornada", "en": "🗑️ Delete matchday"},
    "confirm_delete_matchday": {
        "es": "¿Eliminar esta jornada con todos sus sets? Las jornadas siguientes se renumeran. "
              "No se puede deshacer.",
        "en": "Delete this matchday with all its sets? The following matchdays are renumbered. "
              "This cannot be undone."},
    "six_matchdays": {"es": "El reglamento contempla 6 jornadas por liga.",
                      "en": "The rules plan 6 matchdays per league."},

    # Matchday
    "record_set_button": {"es": "+ Registrar set", "en": "+ Record set"},
    "places_note": {
        "es": 'Al terminar los sets de cada cancha, sus jugadores reciben su lugar: 1.º 9, '
              '2.º 6, 3.º 4 y 4.º 3 puntos, más 1 por set ganado. El lugar se decide por sets '
              'ganados, luego ± juegos, luego posición en el ranking; en la primera jornada, '
              'por sorteo. ⏳ = cancha sin terminar (solo cuentan los sets ganados). '
              '<a href="{url}">Reglamento</a>',
        "en": 'When a court has played all its sets, its players get their place: 1st 9, '
              '2nd 6, 3rd 4, 4th 3 points, plus 1 per set won. Places go by sets won, then '
              '± games, then league position; on the first matchday, by a draw. ⏳ = court '
              'not finished (only sets won count). <a href="{url}">Rules</a>'},
    "absent": {"es": "🚫 Ausente", "en": "🚫 Absent"},
    "mark_absent": {"es": "🚫 Marcar ausente", "en": "🚫 Mark absent"},
    "mark_present": {"es": "✅ Quitar ausencia", "en": "✅ Mark present"},
    "absent_note": {
        "es": "Un jugador ausente conserva sus sets (juega un suplente), pero suma 0 puntos "
              "en la jornada, gane o pierda.",
        "en": "An absent player keeps their sets (a substitute plays), but scores 0 points "
              "on the matchday, win or lose."},
    "add_set_on_court": {"es": "➕ Set en cancha {n}", "en": "➕ Set on court {n}"},
    "sets_recorded": {"es": "{n} de 3 sets registrados.", "en": "{n} of 3 sets recorded."},
    "court_changes": {"es": "🔀 Cambios de cancha", "en": "🔀 Court changes"},
    "per_draw_move": {"es": "🎲 Según el sorteo, cambian", "en": "🎲 Per the draw, move"},
    "move_up": {"es": "⬆️ a cancha {n}:", "en": "⬆️ to court {n}:"},
    "move_down": {"es": "⬇️ a cancha {n}:", "en": "⬇️ to court {n}:"},
    "no_changes": {"es": "➖ sin cambios", "en": "➖ no changes"},

    "no_courts_yet": {
        "es": 'Aún no hay canchas. <a href="{url}">Asigna los jugadores a las canchas</a>.',
        "en": 'No courts yet. <a href="{url}">Assign the players to courts</a>.'},

    "all_matchdays": {"es": "📅 Todas las jornadas", "en": "📅 All matchdays"},
    "completed": {"es": "completa", "en": "completed"},

    # Americano / Mexicano rounds and manual tournaments
    "round_n": {"es": "Ronda {n}", "en": "Round {n}"},
    "round_short": {"es": "R{n}", "en": "R{n}"},
    "rounds": {"es": "🔁 Rondas", "en": "🔁 Rounds"},
    "new_round_n": {"es": "🆕 Nueva ronda {n}", "en": "🆕 New round {n}"},
    "add_round_n": {"es": "➕ Agregar ronda {n}", "en": "➕ Add round {n}"},
    "new_round_button": {"es": "➕ Nueva ronda {n}", "en": "➕ New round {n}"},
    "save_round": {"es": "💾 Guardar ronda", "en": "💾 Save round"},
    "points_per_match": {"es": "🎯 Puntos por partido", "en": "🎯 Points per match"},
    "tournament_players": {"es": "👥 Jugadores del torneo", "en": "👥 Tournament players"},
    "tournament_players_hint": {
        "es": "Elige quiénes juegan; podrás cambiar la lista después. En Americano y Mexicano "
              "(mínimo 4) las rondas se sortean entre ellos.",
        "en": "Choose who plays; you can change the list later. In Americano and Mexicano "
              "(at least 4) the rounds are drawn among them."},
    "courts_available": {"es": "🎾 Canchas disponibles", "en": "🎾 Courts available"},
    "who_rests": {"es": "🛋️ ¿Quién descansa esta ronda?", "en": "🛋️ Who rests this round?"},
    "who_rests_hint": {
        "es": "Marca a quien pidió descansar. Si sobran jugadores, el resto de descansos se "
              "reparte según las reglas: descansa primero quien menos ha descansado.",
        "en": "Tick whoever asked to rest. If players are left over, the other rests follow "
              "the rules: whoever has rested least rests first."},
    "update_suggestion": {"es": "🔄 Actualizar sugerencia", "en": "🔄 Update suggestion"},
    "resting": {"es": "🛋️ Descansan", "en": "🛋️ Resting"},
    "round_hint": {
        "es": "En cada cancha, los dos de arriba juegan contra los dos de abajo: se crea un "
              "partido por cancha. Revisa la sugerencia y cambia lo que haga falta.",
        "en": "On each court the top two play the bottom two: one match per court is "
              "created. Review the suggestion and change what you need."},
    "americano_note": {
        "es": "🇺🇸 Americano: las parejas rotan para que juegues con todos. Cada jugador suma "
              "los puntos que gana su pareja.",
        "en": "🇺🇸 Americano: partners rotate so you play with everyone. Each player scores "
              "the points their pair wins."},
    "mexicano_note": {
        "es": "🇲🇽 Mexicano: la ronda 1 es un sorteo; después manda la clasificación: en cada "
              "cancha 1.º y 3.º contra 2.º y 4.º. Cada jugador suma los puntos que gana su pareja.",
        "en": "🇲🇽 Mexicano: round 1 is a draw; after that the ranking decides: on each court "
              "1st and 3rd against 2nd and 4th. Each player scores the points their pair wins."},
    "points_ranking_note": {
        "es": "Clasificación por puntos, luego diferencia de puntos y victorias.",
        "en": "Ranked by points, then points difference and wins."},
    "manual_note": {
        "es": "✍️ Manual: crea cada set a mano, con su cancha y sus parejas. Cada jugador suma "
              "la diferencia de juegos de cada set (6-3: +3 los ganadores, −3 los perdedores), "
              "así que los puntos pueden ser negativos.",
        "en": "✍️ Manual: create each set by hand, with its court and pairs. Each player scores "
              "the games difference of each set (6-3: +3 for the winners, −3 for the losers), "
              "so points can be negative."},
    "manual_new_hint": {
        "es": "Guarda la jornada y luego agrega cada set con su cancha y parejas.",
        "en": "Save the matchday, then add each set with its court and pairs."},

    # Courts of a matchday
    "assign_courts": {"es": "🎾 Asignar canchas", "en": "🎾 Assign courts"},
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
    "add_court": {"es": "➕ Agregar cancha", "en": "➕ Add court"},
    "remove_court": {"es": "✖️ Quitar", "en": "✖️ Remove"},
    "save_courts": {"es": "💾 Guardar y crear sets", "en": "💾 Save and create sets"},
    "new_matchday_n": {"es": "🆕 Nueva jornada {n}", "en": "🆕 New matchday {n}"},
    "new_matchday_button": {"es": "➕ Nueva jornada {n}", "en": "➕ New matchday {n}"},
    "new_matchday_hint": {
        "es": ("Con estos cambios ({n} jugador por cancha); podrás revisar las canchas antes de guardar.",
               "Con estos cambios ({n} jugadores por cancha); podrás revisar las canchas antes de guardar."),
        "en": ("With these changes ({n} player per court); you can review the courts before saving.",
               "With these changes ({n} players per court); you can review the courts before saving.")},
    "save_matchday": {"es": "💾 Guardar jornada", "en": "💾 Save matchday"},
    "nothing_saved_yet": {
        "es": "La jornada aún no está guardada: revisa las canchas y pulsa «Guardar jornada».",
        "en": "The matchday isn't saved yet: review the courts and press “Save matchday”."},
    "nothing_saved_round": {
        "es": "La ronda aún no está guardada: revisa las canchas y pulsa «Guardar ronda».",
        "en": "The round isn't saved yet: review the courts and press “Save round”."},
    "move_question": {"es": "¿Cuántos jugadores suben y bajan en cada cancha?",
                      "en": "How many players move up and down on each court?"},
    "move_note": {
        "es": "Según la jornada {n}. En la cancha 1 los mejores se quedan (no pueden subir) y "
              "en la última cancha los últimos se quedan (no pueden bajar). Luego podrás mover "
              "a los jugadores.",
        "en": "From matchday {n}. On court 1 the best stay (they can't go up) and on the last "
              "court the last ones stay (they can't go down). You can move players afterwards."},
    "moves_per_court": {"es": "Suben y bajan por cancha:", "en": "Moving per court:"},
    "cancel": {"es": "↩️ Cancelar", "en": "↩️ Cancel"},
    "date": {"es": "📅 Fecha", "en": "📅 Date"},

    # Sets list
    "all_tournaments": {"es": "🏟️ Todos los torneos", "en": "🏟️ All tournaments"},
    "all_players": {"es": "👥 Todos los jugadores", "en": "👥 All players"},
    "filter": {"es": "🔍 Filtrar", "en": "🔍 Filter"},
    "clear": {"es": "✖️ Limpiar", "en": "✖️ Clear"},
    "no_sets_filter": {"es": "Ningún set coincide con este filtro.",
                       "en": "No sets match this filter."},
    "no_sets_yet": {
        "es": 'Aún no hay sets. <a href="{url}">Registra el primero</a>.',
        "en": 'No sets yet. <a href="{url}">Record the first one</a>.'},

    # Set form
    "new_set": {"es": "➕ Nuevo set", "en": "➕ New set"},
    "edit_set": {"es": "✏️ Editar set", "en": "✏️ Edit set"},
    "record_set": {"es": "➕ Registrar un set", "en": "➕ Record a set"},
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
    "save_set": {"es": "💾 Guardar set", "en": "💾 Save set"},
    "save_changes": {"es": "💾 Guardar cambios", "en": "💾 Save changes"},
    "games_later": {"es": "Deja los juegos vacíos si el set aún no se ha jugado.",
                    "en": "Leave the games empty if the set hasn't been played yet."},

    # Players
    "player_name": {"es": "Nombre del jugador", "en": "Player name"},
    "add_player": {"es": "➕ Agregar jugador", "en": "➕ Add player"},
    "no_players": {"es": "Aún no hay jugadores.", "en": "No players yet."},
    "rename": {"es": "✏️ Cambiar nombre", "en": "✏️ Rename"},
    "delete_player": {"es": "🗑️ Eliminar jugador", "en": "🗑️ Delete player"},
    "confirm_delete_player": {"es": "¿Eliminar este jugador?", "en": "Delete this player?"},
    "no_matchdays_played": {"es": "Aún no ha jugado ninguna jornada.",
                            "en": "No matchdays played yet."},

    # Login
    "login": {"es": "🔐 Entrar", "en": "🔐 Log in"},
    "logout": {"es": "🚪 Salir", "en": "🚪 Log out"},
    "login_title": {"es": "🔐 Entrar para editar", "en": "🔐 Log in to edit"},
    "username": {"es": "👤 Usuario", "en": "👤 User"},
    "login_player": {"es": "🎾 Jugadores", "en": "🎾 Players"},
    "login_player_hint": {"es": "Escribe la contraseña de jugadores de tu torneo para "
                                "registrar sus resultados.",
                          "en": "Type your tournament's player password to enter its results."},
    "login_account": {"es": "👤 Mi cuenta", "en": "👤 My account"},
    "login_account_hint": {"es": "Tu usuario o email y tu contraseña: administradores y "
                                 "jugadores con cuenta.",
                           "en": "Your username or email and your password: admins and "
                                 "players with an account."},
    "username_or_email": {"es": "👤 Usuario o email", "en": "👤 Username or email"},

    # Organizations
    "enter_title": {"es": "🏢 Entrar a una organización", "en": "🏢 Enter an organization"},
    "enter_hint": {"es": "Elige tu organización para ver sus torneos, clasificaciones y "
                         "jugadores.",
                   "en": "Choose your organization to see its tournaments, standings and "
                         "players."},
    "enter_login_hint": {"es": '¿Eres administrador o jugador con contraseña? <a href="{url}">Entra aquí</a>.',
                         "en": 'An admin, or a player with a password? <a href="{url}">Log in here</a>.'},
    "org_name": {"es": "🏢 Organización", "en": "🏢 Organization"},
    "enter_other": {"es": "¿No está en la lista? Escribe su nombre:",
                    "en": "Not in the list? Type its name:"},
    "enter": {"es": "➡️ Entrar", "en": "➡️ Enter"},
    "change_org": {"es": "Cambiar de organización", "en": "Change organization"},
    "current_org": {"es": "Actual", "en": "Current"},
    "err_unknown_org": {"es": "No hay ninguna organización con ese nombre.",
                        "en": "There's no organization with that name."},
    "nav_orgs": {"es": "Organizaciones", "en": "Organizations"},
    "orgs_hint": {"es": "Como super administrador puedes crear organizaciones con su "
                        "administrador, entrar a cualquiera y administrar todos sus torneos.",
                  "en": "As a super admin you can create organizations with their admin, enter "
                        "any of them and manage all their tournaments."},
    "create_org": {"es": "➕ Crear organización", "en": "➕ Create organization"},
    "admin_user": {"es": "👤 Usuario administrador", "en": "👤 Admin user"},
    "admin_password": {"es": "🔑 Contraseña del administrador", "en": "🔑 Admin password"},
    "new_admin_password": {"es": "Nueva contraseña del administrador",
                           "en": "New admin password"},
    "change_admin": {"es": "Cambiar usuario o contraseña", "en": "Change user or password"},
    "keep_password": {"es": "Vacío = no cambiarla", "en": "Empty = keep it"},
    "password_unknown": {"es": "No se conoce (se guardó antes); cámbiala para verla.",
                         "en": "Unknown (saved earlier); change it to see it."},
    # Player statistics
    "tab_summary": {"es": "📋 Resumen", "en": "📋 Summary"},
    "tab_stats": {"es": "📊 Estadísticas", "en": "📊 Statistics"},
    "tab_h2h": {"es": "⚔️ Cara a cara", "en": "⚔️ Head to head"},
    "h2h_against": {"es": "Contra", "en": "Against"},
    "show": {"es": "Ver", "en": "Show"},
    "h2h_sets_against": {"es": "Sets frente a frente", "en": "Sets against each other"},
    "h2h_won_by": {"es": "Ganó {name}", "en": "Won by {name}"},
    "h2h_games": {"es": "Juegos: {mine} a {theirs}", "en": "Games: {mine} to {theirs}"},
    "h2h_tied": {"es": "{n} empatados", "en": "{n} tied"},
    "h2h_results": {"es": "Resultados frente a frente", "en": "Results against each other"},
    "h2h_never_against": {"es": "Nunca han jugado contra {name}.",
                          "en": "Never played against {name}."},
    "h2h_together": {"es": "Como pareja", "en": "As partners"},
    "h2h_never_together": {"es": "Nunca han jugado juntos con {name}.",
                           "en": "Never played together with {name}."},
    "h2h_their_sets": {"es": "Sus sets", "en": "Their sets"},
    "no_stats": {"es": "Todavía no hay sets jugados.", "en": "No sets played yet."},
    "won": {"es": "Ganados", "en": "Won"},
    "lost": {"es": "Perdidos", "en": "Lost"},
    "tied": {"es": "Empatados", "en": "Tied"},
    "win_pct": {"es": "Victorias", "en": "Win rate"},
    "current_streak": {"es": "Racha actual", "en": "Current streak"},
    "best_streak": {"es": "Mejor racha", "en": "Best streak"},
    "worst_streak": {"es": "Peor racha", "en": "Worst streak"},
    "form": {"es": "📈 Forma", "en": "📈 Form"},
    "last_n_sets": {"es": ("Último set", "Últimos {n} sets"), "en": ("Last set", "Last {n} sets")},
    "sets_won_lost": {"es": "Sets ganados y perdidos", "en": "Sets won and lost"},
    "rolling_win_pct": {"es": "🎯 % de victorias (últimos 10 sets)",
                        "en": "🎯 Win rate (last 10 sets)"},
    "cumulative_points": {"es": "📈 Puntos acumulados", "en": "📈 Points over time"},
    "highlights": {"es": "✨ Lo más destacado", "en": "✨ Highlights"},
    "hl_most_partner": {"es": "Con quién juegas más", "en": "Most frequent partner"},
    "hl_best_partner": {"es": "Con quién ganas más", "en": "Wins most with"},
    "hl_worst_partner": {"es": "Con quién pierdes más", "en": "Loses most with"},
    "hl_rival": {"es": "Tu rival (el que más enfrentas)", "en": "Your rival (faced most)"},
    "hl_nemesis": {"es": "Tu bestia negra (te gana más)", "en": "Your nemesis (beats you most)"},
    "hl_victim": {"es": "Tu víctima favorita (le ganas más)", "en": "Your favorite victim (you beat most)"},
    "n_wins": {"es": ("{n} victoria", "{n} victorias"), "en": ("{n} win", "{n} wins")},
    "n_losses": {"es": ("{n} derrota", "{n} derrotas"), "en": ("{n} loss", "{n} losses")},
    "wins_with": {"es": "Victorias juntos", "en": "Wins together"},
    "opponents": {"es": "Rivales", "en": "Opponents"},
    "faced": {"es": "Enfrentados", "en": "Faced"},
    "sets_per_month": {"es": "Sets por mes", "en": "Sets per month"},

    # Medals
    "tab_medals": {"es": "🏅 Medallas", "en": "🏅 Medals"},
    "all_medals": {"es": "Todas las medallas", "en": "All medals"},
    "medals_hint": {"es": "Se ganan jugando: se calculan con los sets, así que cambian si "
                          "se corrige un resultado. Las de la vergüenza son de broma. 🤡",
                    "en": "Won by playing: they're worked out from the sets, so they change "
                          "if a result is corrected. The shame ones are a joke. 🤡"},
    "n_medals": {"es": ("{n} medalla", "{n} medallas"), "en": ("{n} medal", "{n} medals")},
    "no_medals_yet": {"es": "Todavía ninguna medalla. ¡A jugar!",
                      "en": "No medals yet. Go play!"},
    "medals_to_win": {"es": "Por ganar", "en": "Still to win"},
    "medal": {"es": "Medalla", "en": "Medal"},
    "how_to_win": {"es": "Cómo se gana", "en": "How to win it"},
    "holders": {"es": "La tienen", "en": "Held by"},
    "kind_glory": {"es": "🥇 Gloria", "en": "🥇 Glory"},
    "kind_rival": {"es": "⚔️ Rivalidad", "en": "⚔️ Rivalry"},
    "kind_shame": {"es": "🤡 Vergüenza (de broma)", "en": "🤡 Shame (just for fun)"},
    "tier_bronze": {"es": "Bronce", "en": "Bronze"},
    "tier_silver": {"es": "Plata", "en": "Silver"},
    "tier_gold": {"es": "Oro", "en": "Gold"},

    # From guest to account, and the profile
    "welcome_title": {"es": "👋 ¡Bienvenido/a!", "en": "👋 Welcome!"},
    "welcome_hint": {"es": "Ya puedes registrar los resultados de este torneo. ¿Quieres "
                           "una cuenta? Con ella tienes tu perfil, tus torneos y tus sets en "
                           "un solo lugar, sin la contraseña del torneo.",
                     "en": "You can now enter this tournament's results. Want an account? "
                           "It gives you your profile, your tournaments and your sets in one "
                           "place, without the tournament password."},
    "create_account": {"es": "Crear cuenta", "en": "Create account"},
    "create_account_hint": {"es": "Elige cuál de los jugadores eres (o si eres nuevo/a) y "
                                  "crea tu usuario.",
                            "en": "Pick which of the players you are (or that you're new) "
                                  "and create your user."},
    "have_account": {"es": "Ya tengo cuenta", "en": "I have an account"},
    "have_account_hint": {"es": "Entra con tu usuario o email para vincular tu jugador de "
                                "este torneo.",
                          "en": "Log in with your username or email to link your player in "
                                "this tournament."},
    "continue_guest": {"es": "Seguir como invitado", "en": "Continue as a guest"},
    "continue_guest_hint": {"es": "Sin cuenta: solo registras los resultados de este torneo.",
                            "en": "No account: you just enter this tournament's results."},
    "welcome_link": {"es": "Vincula tu jugador", "en": "Link your player"},
    "welcome_link_hint": {"es": "Estás dentro como {name}. ¿Cuál de los jugadores de este "
                                "torneo eres?",
                          "en": "You're logged in as {name}. Which of this tournament's "
                                "players are you?"},
    "who_are_you": {"es": "🎾 ¿Quién eres?", "en": "🎾 Who are you?"},
    "who_hint": {"es": "Tus sets y puntos de antes pasan a tu cuenta. Si no estás en la "
                       "lista, elige «Soy nuevo/a».",
                 "en": "Your earlier sets and points become your account's. If you're not "
                       "in the list, choose \"I'm new\"."},
    "i_am_new": {"es": "Soy nuevo/a", "en": "I'm new"},
    "no_free_players": {"es": "Todos los jugadores de este torneo ya tienen cuenta.",
                        "en": "Every player of this tournament already has an account."},
    "signup_hint": {"es": "Luego entras con tu usuario o tu email y tu contraseña.",
                    "en": "Then you log in with your username or email and your password."},
    "display_name_hint": {"es": "Es tu nombre en las clasificaciones y los sets.",
                          "en": "It's your name in the standings and sets."},
    "password_again": {"es": "🔑 Repite la contraseña", "en": "🔑 Password again"},
    "change_password": {"es": "Cambiar contraseña", "en": "Change password"},
    "saved": {"es": "Guardado.", "en": "Saved."},
    "my_profile": {"es": "Mi perfil", "en": "My profile"},
    "install_title": {"es": "PadelScore en tu pantalla de inicio",
                      "en": "PadelScore on your home screen"},
    "install_hint": {"es": "Instálala como app: se abre a pantalla completa, con su ícono, "
                           "sin la barra del navegador.",
                     "en": "Install it as an app: it opens full screen, with its icon, "
                           "without the browser bar."},
    "install_app": {"es": "Instalar app", "en": "Install the app"},
    "manual": {"es": "Manual", "en": "Manual (Spanish)"},
    "install_banner": {"es": "Instala la app en tu teléfono", "en": "Install the app on your phone"},
    "close": {"es": "Cerrar", "en": "Close"},
    "install_now": {"es": "Instalar", "en": "Install"},
    "install_samsung": {"es": "Estás en Samsung Internet: ahí Google Play Protect bloquea la app "
                              "instalada («app no segura»). Copia el enlace y ábrelo en Chrome "
                              "para instalarla.",
                        "en": "You're on Samsung Internet: Google Play Protect blocks apps "
                              "installed from it (\"unsafe app\"). Copy the link and open it in "
                              "Chrome to install it."},
    "install_done": {"es": "Ya la tienes instalada", "en": "It's already installed"},
    "install_done_hint": {"es": "Ábrela desde su ícono en tu pantalla de inicio.",
                          "en": "Open it from its icon on your home screen."},
    "install_android_steps": {"es": "En Chrome: abre el menú ⋮ (arriba a la derecha) y toca "
                                    "«Instalar app» (o «Agregar a la pantalla principal»).",
                              "en": "In Chrome: open the ⋮ menu (top right) and tap \"Install "
                                    "app\" (or \"Add to Home screen\")."},
    "install_android_or": {"es": "O desde el menú ⋮ de Chrome, «Instalar app»:",
                           "en": "Or from Chrome's ⋮ menu, \"Install app\":"},
    "install_android_step1": {"es": "Menú ⋮ → «Instalar app», y confirma.",
                              "en": "⋮ menu → \"Install app\", then confirm."},
    "install_android_menu_tab": {"es": "Nueva pestaña", "en": "New tab"},
    "install_android_menu_history": {"es": "Historial", "en": "History"},
    "install_android_menu_install": {"es": "Instalar app", "en": "Install app"},
    "install_iphone_safari": {"es": "En Safari (en otros navegadores del iPhone, ábrela primero "
                                    "en Safari):",
                              "en": "In Safari (from another iPhone browser, open it in Safari "
                                    "first):"},
    "install_iphone_step1": {"es": "Toca Compartir ⬆️, en la barra de abajo.",
                             "en": "Tap Share ⬆️, in the bottom bar."},
    "install_iphone_step2": {"es": "Baja en la lista y toca «Agregar a inicio».",
                             "en": "Scroll down the list and tap \"Add to Home Screen\"."},
    "install_iphone_step3": {"es": "Toca «Agregar». El ícono de PadelScore queda en tu pantalla "
                                   "de inicio.",
                             "en": "Tap \"Add\". PadelScore's icon is now on your home screen."},
    "install_iphone_copy": {"es": "Copiar", "en": "Copy"},
    "install_iphone_favorite": {"es": "Agregar a favoritos", "en": "Add to Favorites"},
    "install_iphone_add": {"es": "Agregar a inicio", "en": "Add to Home Screen"},
    "install_iphone_find": {"es": "Buscar en la página", "en": "Find on Page"},
    "install_iphone_confirm": {"es": "Agregar", "en": "Add"},
    "cancel_plain": {"es": "Cancelar", "en": "Cancel"},
    "my_summary": {"es": "Mi resumen", "en": "My summary"},
    "my_tournaments": {"es": "Mis torneos", "en": "My tournaments"},
    "no_my_tournaments": {"es": "Todavía no juegas ningún torneo.",
                          "en": "You're not in any tournament yet."},
    "my_pending_sets": {"es": "Mis sets por jugar", "en": "My sets to play"},
    "no_pending_sets": {"es": "No tienes sets pendientes.", "en": "No sets to play."},
    "my_recent_sets": {"es": "Mis últimos sets", "en": "My latest sets"},
    "no_my_players": {"es": "Tu cuenta aún no tiene jugador. Entra con la contraseña de "
                            "un torneo para vincularlo.",
                      "en": "Your account has no player yet. Log in with a tournament's "
                            "password to link one."},
    "err_choose_player": {"es": "Elige quién eres.", "en": "Choose who you are."},
    "err_display_required": {"es": "Escribe tu nombre para mostrar.",
                             "en": "Type your display name."},
    "err_password_short": {"es": "La contraseña necesita al menos 8 caracteres.",
                           "en": "The password needs at least 8 characters."},
    "err_passwords_differ": {"es": "Las contraseñas no coinciden.",
                             "en": "The passwords don't match."},

    # Accounts
    "account": {"es": "Cuenta", "en": "Account"},
    "guest_player": {"es": "👻 Jugador invitado: no tiene cuenta.",
                     "en": "👻 Guest player: no account."},
    "nav_users": {"es": "Cuentas", "en": "Accounts"},
    "users_hint": {"es": "Las cuentas de los administradores y de los jugadores de la "
                         "organización. Puedes cambiar sus datos y su contraseña cuando quieras.",
                   "en": "The accounts of the organization's admins and players. You can change "
                         "their details and password any time."},
    "no_users": {"es": "Todavía no hay cuentas.", "en": "No accounts yet."},
    "role": {"es": "Rol", "en": "Role"},
    "role_super": {"es": "⭐ Super administrador", "en": "⭐ Super admin"},
    "role_org_admin": {"es": "🏢 Administrador", "en": "🏢 Admin"},
    "role_player": {"es": "🎾 Jugador", "en": "🎾 Player"},
    "role_hint": {"es": "Un administrador necesita su organización.",
                  "en": "An admin needs their organization."},
    "account_details": {"es": "Datos de la cuenta", "en": "Account details"},
    "email": {"es": "📧 Email", "en": "📧 Email"},
    "first_name": {"es": "Nombre", "en": "First name"},
    "last_name": {"es": "Apellido", "en": "Last name"},
    "display_name": {"es": "Nombre para mostrar", "en": "Display name"},
    "full_name": {"es": "Nombre", "en": "Name"},
    "reset_password_hint": {"es": "La cuenta tendrá que volver a entrar con la nueva contraseña.",
                            "en": "The account will have to log in again with the new password."},
    "link_player": {"es": "🔗 Vincular jugador", "en": "🔗 Link player"},
    "unlink_player": {"es": "Desvincular jugador", "en": "Unlink player"},
    "link_player_hint": {"es": "El jugador de esta organización que es esta cuenta: sus sets "
                               "y torneos aparecen en su perfil.",
                         "en": "This account's player in this organization: their sets and "
                               "tournaments show on the profile."},
    "err_username_invalid": {"es": "Escribe un usuario sin espacios ni «@».",
                             "en": "Type a username without spaces or \"@\"."},
    "err_username_taken": {"es": "Ese usuario ya existe.", "en": "That username is taken."},
    "err_email_invalid": {"es": "Ese email no es válido.", "en": "That email isn't valid."},
    "phone": {"es": "📱 Celular", "en": "📱 Cell phone"},
    "email_recaps_label": {"es": "Recibir por email el resumen de mi jornada (al día siguiente)",
                           "en": "Get my matchday recap by email (the next day)"},
    "recap_email_subject": {"es": "🎾 Tu jornada {n} · {tournament}",
                            "en": "🎾 Your matchday {n} · {tournament}"},
    "recap_email_whatsapp": {"es": "Compártelo por WhatsApp", "en": "Share it on WhatsApp"},
    "recap_email_standings": {"es": "Clasificación del torneo", "en": "Tournament standings"},
    "recap_email_my_tournament": {"es": "Tu torneo", "en": "Your tournament"},
    "recap_email_points_per_day": {"es": "Puntos por jornada", "en": "Points per matchday"},
    "recap_email_form": {"es": "Tus últimos sets", "en": "Your latest sets"},
    "recap_email_form_legend": {"es": "🟩 ganado · 🟥 perdido · ⬜ empate, del más viejo al más nuevo",
                                "en": "🟩 won · 🟥 lost · ⬜ tied, oldest to newest"},
    "recap_email_medals": {"es": "Tus medallas del torneo", "en": "Your medals in the tournament"},
    "recap_email_new": {"es": "¡nueva!", "en": "new!"},
    "email_reminders_label": {"es": "Recordarme por email el día que juego (cancha, rivales y "
                                    "probabilidades)",
                              "en": "Remind me by email on game day (court, rivals and chances)"},
    "reminder_subject": {"es": "⏰ Hoy juegas · {tournament} · Jornada {n} · Cancha {court}",
                         "en": "⏰ You play today · {tournament} · Matchday {n} · Court {court}"},
    "reminder_title": {"es": "¡Hoy juegas, {name}!", "en": "You play today, {name}!"},
    "reminder_position": {"es": "Vas {n}.º con {points} pts", "en": "You're #{n} with {points} pts"},
    "reminder_first": {"es": "Primera jornada: todos empiezan en cero.",
                       "en": "First matchday: everyone starts at zero."},
    "reminder_streak_win": {"es": "Llegas con {n} sets ganados seguidos",
                            "en": "You come in with {n} sets won in a row"},
    "reminder_streak_loss": {"es": "Llegas con {n} sets perdidos seguidos: ¡hoy se rompe!",
                             "en": "You come in with {n} sets lost in a row: today it ends!"},
    "reminder_sets": {"es": "Tus sets de hoy", "en": "Your sets today"},
    "reminder_with": {"es": "Con {name}", "en": "With {name}"},
    "reminder_already_played": {"es": "ya jugado", "en": "already played"},
    "reminder_chance": {"es": "{n}% de ganar", "en": "{n}% to win"},
    "chance_fav": {"es": "Van de favoritos", "en": "You're the favorites"},
    "chance_hint": {"es": "Probabilidad de ganar el set según los sets jugados: el % ganado de "
                          "cada jugador (suavizado) y el promedio de cada pareja.",
                    "en": "Chance of winning the set from the sets played: each player's "
                          "(smoothed) share won and each pair's average."},
    "h2h_chance": {"es": "Probabilidad de ganarle a {name} en un set",
                   "en": "Chance of beating {name} in a set"},
    "chance_even": {"es": "Parejo", "en": "Even"},
    "chance_hard": {"es": "Cuesta arriba", "en": "Uphill"},
    "reminder_h2h": {"es": "contra {name}: {won}-{lost}", "en": "against {name}: {won}-{lost}"},
    "reminder_h2h_none": {"es": "primera vez contra {name}", "en": "first time against {name}"},
    "reminder_how": {"es": "La probabilidad sale de los sets jugados: el % de sets ganados de "
                           "cada jugador (suavizado) y el promedio de cada pareja, comparados. "
                           "Es un cálculo, no un pronóstico.",
                     "en": "Chances come from the sets played: each player's (smoothed) share "
                           "of sets won and each pair's average, compared. It's a calculation, "
                           "not a forecast."},
    "reminder_open": {"es": "Abrir la jornada", "en": "Open the matchday"},
    "email_reminder_now": {"es": "Enviarle el recordatorio de su próxima jornada por email",
                           "en": "Email them the reminder of their next matchday"},
    "confirm_email_reminder": {"es": "¿Enviar a {name} el recordatorio de su próxima jornada?",
                               "en": "Email {name} the reminder of their next matchday?"},
    "err_no_jornada_yet": {"es": "Ese jugador aún no tiene jornadas en este torneo.",
                           "en": "That player has no matchdays in this tournament yet."},
    "email_recap_now": {"es": "Enviarle el resumen de su última jornada por email",
                        "en": "Email them the recap of their latest matchday"},
    "confirm_email_recap": {"es": "¿Enviar a {name} el resumen de su última jornada por email?",
                            "en": "Email {name} the recap of their latest matchday?"},
    "recap_email_sent": {"es": "Email enviado.", "en": "Email sent."},
    "test_reminder": {"es": "Probar recordatorio", "en": "Test reminder"},
    "nav_emails": {"es": "Emails", "en": "Emails"},
    "emails_hint": {"es": "Los emails que se mandaron (o se intentaron) a las cuentas de esta "
                          "organización ese día: automáticos y de prueba.",
                    "en": "The emails sent (or tried) to this organization's accounts that day: "
                          "automatic and test ones."},
    "previous_day": {"es": "Día anterior", "en": "Previous day"},
    "next_day": {"es": "Día siguiente", "en": "Next day"},
    "email_status": {"es": "Estado", "en": "Status"},
    "email_kind": {"es": "Tipo", "en": "Kind"},
    "email_to": {"es": "Para", "en": "To"},
    "email_subject": {"es": "Asunto", "en": "Subject"},
    "time": {"es": "Hora", "en": "Time"},
    "all_statuses": {"es": "Todos los estados", "en": "All statuses"},
    "all_kinds": {"es": "Todos los tipos", "en": "All kinds"},
    "all_roles": {"es": "Todos los roles", "en": "All roles"},
    "filter_search": {"es": "🔍 Filtrar…", "en": "🔍 Filter…"},
    "email_status_sent": {"es": "✅ Enviado", "en": "✅ Sent"},
    "email_status_failed": {"es": "❌ Falló", "en": "❌ Failed"},
    "email_status_throttled": {"es": "⏳ Límite de Azure", "en": "⏳ Azure's limit"},
    "email_kind_recap": {"es": "📊 Resumen", "en": "📊 Recap"},
    "email_kind_reminder": {"es": "⏰ Recordatorio", "en": "⏰ Reminder"},
    "email_kind_test_recap": {"es": "🧪 Prueba: resumen", "en": "🧪 Test: recap"},
    "email_kind_test_reminder": {"es": "🧪 Prueba: recordatorio", "en": "🧪 Test: reminder"},
    "email_kind_test": {"es": "🧪 Prueba", "en": "🧪 Test"},
    "email_kind_summary": {"es": "📄 Resumen de jornada (PDF)", "en": "📄 Matchday summary (PDF)"},
    # 📄 Jornada summary (PDF; no emoji in pdf_* texts: the PDF's fonts can't draw them)
    "pdf_card_title": {"es": "📄 Resumen de la {label}", "en": "📄 {label} summary"},
    "pdf_card_note": {"es": "Un PDF con el ranking y sus medallas, los sets, las medallas de "
                            "la jornada, cómo van los puntos y la próxima jornada.",
                      "en": "A PDF with the ranking and its medals, the sets, the matchday's "
                            "medals, how the points are going and the next matchday."},
    "pdf_download": {"es": "⬇️ Ver PDF", "en": "⬇️ View PDF"},
    "pdf_whatsapp": {"es": "📲 Enviar por WhatsApp", "en": "📲 Send on WhatsApp"},
    "pdf_whatsapp_note": {"es": "Desde tu WhatsApp: en el celular se manda el PDF al chat o grupo "
                                "que elijas; en la computadora, se abre WhatsApp con un enlace "
                                "al PDF. O copia el mensaje con el enlace y pégalo donde quieras.",
                          "en": "From your WhatsApp: on a phone the PDF goes to the chat or "
                                "group you pick; on a computer, WhatsApp opens with a link to "
                                "the PDF. Or copy the message with the link and paste it "
                                "anywhere."},
    "pdf_copy": {"es": "📋 Copiar mensaje", "en": "📋 Copy message"},
    "pdf_copied": {"es": "✅ Copiado", "en": "✅ Copied"},
    "pdf_copy_manual": {"es": "Copia este mensaje:", "en": "Copy this message:"},
    "pdf_whatsapp_text": {"es": "📄 Resumen de la {label} · {tournament}",
                          "en": "📄 {label} summary · {tournament}"},
    "pdf_or_email": {"es": "O por email, a los jugadores del torneo con cuenta:",
                     "en": "Or by email, to the tournament's players with an account:"},
    "pdf_send": {"es": ("📧 Enviar por email a {n} jugador", "📧 Enviar por email a {n} jugadores"),
                 "en": ("📧 Email {n} player", "📧 Email {n} players")},
    "pdf_send_confirm": {"es": "¿Enviar el resumen por email a los jugadores del torneo con cuenta "
                               "y email?",
                         "en": "Email the summary to the tournament's players with an account "
                               "and email?"},
    "pdf_no_audience": {"es": "Nadie del torneo tiene cuenta con email todavía.",
                        "en": "Nobody in the tournament has an account with email yet."},
    "pdf_queued": {"es": "✅ Enviando por email. Azure deja 10 emails por hora: si son más, los demás "
                         "salen en las siguientes horas.",
                   "en": "✅ Sending by email. Azure allows 10 emails an hour: if there are more, the "
                         "rest go out over the next hours."},
    "pdf_sent_status": {"es": "📧 Enviado a {sent} de {to}.", "en": "📧 Sent to {sent} of {to}."},
    "pdf_title": {"es": "Resumen", "en": "Summary"},
    "pdf_ranking": {"es": "Ranking", "en": "Ranking"},
    "pdf_ranking_note": {"es": "Después de la {label}. Medallas: las ganadas en el torneo.",
                         "en": "After {label}. Medals: those won in the tournament."},
    "pdf_points": {"es": "Pts", "en": "Pts"},
    "pdf_moved": {"es": "Lugares", "en": "Places"},
    "pdf_medals": {"es": "Medallas", "en": "Medals"},
    "pdf_set_medals": {"es": "Medallas de la jornada", "en": "Medals of the matchday"},
    "pdf_vs": {"es": "a", "en": "to"},
    "pdf_sets": {"es": "Sets y resultados", "en": "Sets and results"},
    "pdf_sets_note": {"es": "En negritas, los ganadores. Debajo, la probabilidad que tenían de "
                            "ganar antes de la jornada.",
                      "en": "Winners in bold. Below, the chance they had of winning before "
                            "the matchday."},
    "pdf_court": {"es": "Cancha {n}", "en": "Court {n}"},
    "pdf_had": {"es": "Los ganadores tenían {n}% de probabilidad",
                "en": "The winners had a {n}% chance"},
    "pdf_evolution": {"es": "Así van los puntos, jornada a jornada",
                      "en": "The points, matchday by matchday"},
    "pdf_evolution_note": {"es": "Los puntos acumulados de cada jugador (en azul), sobre los de "
                                 "todos los demás (en gris). Todos en la misma escala.",
                           "en": "Each player's total points (blue) over everyone else's "
                                 "(gray). All on the same scale."},
    "pdf_next": {"es": "Próxima", "en": "Next"},
    "pdf_start": {"es": "Inicio", "en": "Start"},
    "pdf_next_note": {"es": "La probabilidad de ganar de cada pareja (azul y rojo), según los "
                            "resultados de todos hasta hoy.",
                      "en": "Each pair's chance of winning (blue and red), from everyone's "
                            "results so far."},
    "set_medal_renido": {"es": "El más reñido", "en": "The hardest fought"},
    "set_medal_renido_how": {"es": "El set más largo: {games} games, ¡qué partidazo!",
                             "en": "The longest set: {games} games, what a match!"},
    "set_medal_parejo": {"es": "El más parejo", "en": "The closest"},
    "set_medal_parejo_how": {"es": "Por {gap} game de diferencia, parejito, parejito",
                             "en": "Only {gap} game apart, neck and neck"},
    "set_medal_aplastante": {"es": "El más aplastante", "en": "The biggest win"},
    "set_medal_aplastante_how": {"es": "Por {gap} games: ¡los barrieron!",
                                 "en": "By {gap} games: a clean sweep!"},
    "set_medal_sorpresa": {"es": "La sorpresa", "en": "The upset"},
    "set_medal_sorpresa_how": {"es": "¡Batacazo! Ganaron con solo {n}% de probabilidad",
                               "en": "They won with only a {n}% chance"},
    "set_medal_cantado": {"es": "Estaba cantado", "en": "As expected"},
    "set_medal_cantado_how": {"es": "Tenían {n}% de probabilidad y cumplieron",
                              "en": "They had a {n}% chance and delivered"},
    "summary_email_subject": {"es": "📄 Resumen de la {label} · {tournament}",
                              "en": "📄 {label} summary · {tournament}"},
    "summary_email_hi": {"es": "¡Hola, {name}!", "en": "Hi, {name}!"},
    "summary_email_intro": {"es": "Te mandamos el resumen de la {label} de {tournament}: va en "
                                  "el PDF adjunto.",
                            "en": "Here's the {label} summary of {tournament}: it's in the "
                                  "attached PDF."},
    "summary_email_leader": {"es": "🥇 Va en primer lugar {name}, con {points} puntos.",
                             "en": "🥇 {name} leads with {points} points."},
    "summary_email_open": {"es": "Ver el torneo", "en": "See the tournament"},
    "no_emails_day": {"es": "Ese día no se mandó ningún email.", "en": "No emails that day."},
    "confirm_test_reminder": {"es": "¿Enviar a {name} el recordatorio de su próxima jornada (sea "
                                    "el día que sea)?",
                              "en": "Send {name} the reminder of their next matchday (whatever "
                                    "its date)?"},
    "confirm_test_email": {"es": "¿Enviar a {name} un email de prueba (el resumen de su última "
                                 "jornada, si tiene)?",
                           "en": "Send {name} a test email (the recap of their latest matchday, "
                                 "if any)?"},
    "err_no_player_email": {"es": "Ese jugador no tiene cuenta con email.",
                            "en": "That player has no account with an email."},
    "err_no_recap_yet": {"es": "Ese jugador aún no tiene sets jugados en este torneo.",
                         "en": "That player has no played sets in this tournament yet."},
    "recap_email_why": {"es": "Te llega porque juegas en PadelScore.",
                        "en": "You get this because you play on PadelScore."},
    "recap_email_unsubscribe": {"es": "No recibir más estos emails",
                                "en": "Stop these emails"},
    "unsubscribed_title": {"es": "Listo, ya no te llegarán", "en": "Done, no more emails"},
    "unsubscribed_hint": {"es": "Ya no recibirás esos emails. Puedes volver a activarlos en tu "
                                "perfil.",
                          "en": "You won't get those emails anymore. You can turn them back on "
                                "in your profile."},
    "test_email": {"es": "Probar email", "en": "Test email"},
    "test_email_hint": {"es": "Te manda un email de prueba a tu dirección.",
                        "en": "Sends a test email to your address."},
    "test_email_subject": {"es": "✅ PadelScore ya manda emails", "en": "✅ PadelScore can send email"},
    "test_email_body": {"es": "Si lees esto, el email de PadelScore (Azure Communication "
                              "Services) funciona.",
                        "en": "If you're reading this, PadelScore's email (Azure "
                              "Communication Services) works."},
    "mail_sent": {"es": "Email de prueba enviado: revisa tu bandeja (y el spam).",
                  "en": "Test email sent: check your inbox (and spam)."},
    "err_no_email": {"es": "Tu cuenta no tiene email: agrégalo en tu perfil.",
                     "en": "Your account has no email: add it in your profile."},
    "err_mail_off": {"es": "El email está apagado: faltan ACS_CONNECTION_STRING y MAIL_SENDER "
                           "en Azure (docs/processes/EMAIL.md).",
                     "en": "Email is off: ACS_CONNECTION_STRING and MAIL_SENDER are missing "
                           "in Azure (docs/processes/EMAIL.md)."},
    "err_mail_throttled": {"es": "Azure no dejó enviarlo: con su dominio gratis permite 10 emails "
                                 "por hora (y 5 por minuto) en total. Inténtalo en un rato.",
                           "en": "Azure refused it: its free domain allows 10 emails an hour (and "
                                 "5 a minute) in total. Try again in a while."},
    "err_mail_failed": {"es": "Azure no aceptó el email: revisa la configuración y el log.",
                        "en": "Azure didn't accept the email: check the setup and the log."},
    "phone_country": {"es": "País (lada)", "en": "Country (code)"},
    "phone_number": {"es": "Número", "en": "Number"},
    "phone_hint": {"es": "Opcional. Elige el país y escribe el número sin la lada del país. "
                         "Solo lo ven tú y los administradores.",
                   "en": "Optional. Choose the country and type the number without the "
                         "country code. Only you and the admins see it."},
    "err_phone_invalid": {"es": "Ese celular no es válido: elige el país y escribe de 6 a 14 "
                                "dígitos.",
                          "en": "That cell phone isn't valid: choose the country and type 6 "
                                "to 14 digits."},
    "err_email_taken": {"es": "Ya hay una cuenta con ese email.",
                        "en": "There's already an account with that email."},
    "err_email_required": {"es": "Los jugadores necesitan un email.",
                           "en": "Players need an email."},
    "err_password_required": {"es": "Escribe una contraseña.", "en": "Type a password."},
    "err_role": {"es": "Ese rol no es válido (un administrador necesita su organización).",
                 "en": "That role isn't valid (an admin needs their organization)."},
    "err_own_role": {"es": "No puedes cambiar tu propio rol.", "en": "You can't change your own role."},
    "err_player_claimed": {"es": "Ese jugador ya tiene una cuenta.",
                           "en": "That player already has an account."},
    "err_already_linked": {"es": "Esta cuenta ya tiene un jugador en esta organización.",
                           "en": "This account already has a player in this organization."},
    "menu": {"es": "Menú", "en": "Menu"},
    "merge_title": {"es": "¿También eres tú?", "en": "Is this you too?"},
    "merge_hint": {"es": "Tu cuenta ya es {name} en esta organización. Si alguien te apuntó "
                         "otra vez con otro nombre, únelos: sus sets y torneos pasan a {name}.",
                   "en": "Your account is already {name} in this organization. If someone "
                         "entered you again under another name, join them: their sets and "
                         "tournaments move to {name}."},
    "merge_confirm": {"es": "Es la misma persona que {name}. Se unen en uno (no se puede "
                            "deshacer).",
                      "en": "It's the same person as {name}. They become one (this can't be "
                            "undone)."},
    "merge_player": {"es": "🧩 Unir jugadores", "en": "🧩 Join players"},
    "err_merge_same_set": {"es": "Esos dos jugadores jugaron en el mismo set: son personas "
                                 "distintas.",
                           "en": "Those two players played in the same set: they're different "
                                 "people."},
    "err_merge_invalid": {"es": "Esos jugadores no se pueden unir.",
                          "en": "Those players can't be joined."},
    "my_career": {"es": "Todo mi pádel", "en": "All my padel"},
    "my_career_hint": {"es": "Tus números en todas tus organizaciones.",
                       "en": "Your numbers across all your organizations."},
    "no_orgs": {"es": "Todavía no hay organizaciones.", "en": "No organizations yet."},
    "err_org_fields": {"es": "Escribe el nombre, el usuario y la contraseña.",
                       "en": "Type the name, the user and the password."},
    "err_org_exists": {"es": "Ya existe una organización con ese nombre.",
                       "en": "There's already an organization with that name."},
    "err_admin_user_exists": {"es": "Ese usuario administrador ya existe.",
                              "en": "That admin user already exists."},
    "password": {"es": "🔑 Contraseña", "en": "🔑 Password"},
    "club_password": {"es": "Contraseña del club", "en": "Club password"},
    "err_wrong_password": {"es": "Contraseña incorrecta.", "en": "Wrong password."},

    # Rules
    "rules_spanish_only": {"es": "", "en": "The rules are only available in Spanish."},

    # Errors
    "err_name_required": {"es": "El nombre es obligatorio.", "en": "Name is required."},
    "err_player_exists": {"es": "Ese jugador ya existe.", "en": "That player already exists."},
    "err_choose_leaving": {"es": "Elige qué jugador sale.", "en": "Choose which player leaves."},
    "err_replace_same": {"es": "Elige a otro jugador para entrar.",
                         "en": "Choose a different player to come in."},
    "err_replace_conflict": {
        "es": "Ese jugador ya está en un set sin jugar con quien sale; cambia ese set primero.",
        "en": "That player is already in a pending set with the one leaving; change that set first."},
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
    "err_rule_type": {"es": "Elige un tipo de reglas.", "en": "Pick a rules type."},
    "err_round_players": {"es": "Elige al menos 4 jugadores para Americano o Mexicano.",
                          "en": "Pick at least 4 players for Americano or Mexicano."},
    "err_unknown_player": {"es": "No hay ningún jugador con ese nombre: elígelo de la lista.",
                           "en": "There's no player with that name: pick one from the list."},
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
