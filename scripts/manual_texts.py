"""The texts of the user manuals (Spanish), laid out by scripts/manual_pdf.py.

Screenshots are ("name", top px, bottom px, caption): name is a page captured by
scripts/make_manuals.py (pages_for), cut to those pixel rows (None: to the end). If a
screen changes, check its cut still frames the right part.
"""

URL = "https://padelscore-sorrycion.azurewebsites.net"

# --- Shared sections -------------------------------------------------------------------

INSTALL = {"title": "Instalar la app en tu teléfono", "blocks": [
    ("p", "PadelScore se puede instalar como una app: se abre a pantalla completa, con su "
          "ícono en tu pantalla de inicio y sin la barra del navegador. No ocupa espacio ni "
          "necesita la tienda de apps."),
    ("shots", [("install", 0, None, "Menú > Instalar app")]),
    ("h", "Android (Chrome)"),
    ("steps", ["Abre el sitio en **Chrome**.",
               "Toca el menú de los tres puntos (arriba a la derecha).",
               "Toca **Instalar app** (o **Agregar a la pantalla principal**) y confirma."]),
    ("warn", "Instálala desde **Chrome**. Si la instalas desde Samsung Internet, Play Protect "
             "puede bloquearla como \"app no segura\"."),
    ("h", "iPhone (Safari)"),
    ("steps", ["Abre el sitio en **Safari**.",
               "Toca el botón **Compartir** (el cuadro con la flecha hacia arriba).",
               "Elige **Agregar a inicio** y toca **Agregar**."]),
    ("p", "En la página de inicio aparece un aviso pequeño, \"Instala la app en tu teléfono\", "
          "que puedes cerrar con la X."),
]}

MENU_COMMON = [
    "**Inicio:** tus torneos y tus próximos sets.",
    "**Clasificación:** la tabla del torneo actual de la organización.",
    "**Torneos:** todos los torneos, en curso y pasados.",
    "**Sets:** todos los sets jugados y por jugar, con filtros por torneo, jornada y jugador.",
    "**Jugadores:** la lista de jugadores de la organización y la página de cada uno.",
    "**Reglamento:** las reglas de cada tipo de torneo (Liga de amigos, Americano, "
    "Mexicano, Manual).",
    "**Instalar app:** cómo poner PadelScore en tu teléfono.",
    "**Manual:** este manual, en PDF.",
    "**Tu nombre:** tu perfil (Mis datos, contraseña, emails).",
    "**Salir:** cerrar sesión.",
    "**ES / EN:** el idioma de la app.",
]

PDF_SUMMARY = [
    ("p", "Cada jornada con resultados tiene un **Resumen de la jornada** en PDF. La "
          "tarjeta aparece en la página del torneo (para la última jornada jugada) y en la "
          "página de cada jornada. El PDF trae:"),
    ("bullets", ["**Ranking** después de la jornada: puntos, puntos de esa jornada, lugares "
                 "que subió o bajó cada quien, y sus **medallas** del torneo.",
                 "**Medallas de la jornada:** el set más reñido, el más parejo, el más "
                 "aplastante, la sorpresa (ganaron con la probabilidad en contra) y el que "
                 "estaba cantado.",
                 "**Sets y resultados** por cancha, con la probabilidad que tenían los "
                 "ganadores.",
                 "**Así van los puntos:** una gráfica de línea por jugador, jornada a jornada.",
                 "**Próxima jornada**, si ya está armada, con la probabilidad de ganar de cada "
                 "pareja."]),
    ("shots", [("tournament", 1165, 1600, "La tarjeta del resumen"),
               ("jornada_pdf", 0, None, "La primera página del PDF")]),
]

# --- Admin manual ----------------------------------------------------------------------

ADMIN_MANUAL = {
    "title": "Manual del administrador",
    "subtitle": "Todo lo que hace quien organiza la liga: torneos, jornadas, canchas, "
                "resultados, jugadores, cuentas, emails y resúmenes.",
    "who": "Para el **administrador de una organización** (por ejemplo, quien organiza la "
           "liga de un club). El administrador puede hacer todo dentro de su organización; "
           "los jugadores solo registran los resultados de sus sets.",
    "sections": [
        {"title": "Conceptos básicos", "blocks": [
            ("p", "PadelScore lleva las ligas de pádel de una **organización** (un club o un "
                  "grupo). Cada organización tiene sus jugadores, sus torneos y su propio "
                  f"enlace, por ejemplo **{URL}/nene**: quien lo abre ve solo esa "
                  "organización."),
            ("table", [["Concepto", "Qué es"],
                       ["Organización", "El club o grupo. Tiene un administrador."],
                       ["Torneo", "Una liga o un evento: nombre, fecha, tipo de reglas, "
                                  "jugadores y su contraseña de jugadores."],
                       ["Jornada (o ronda)", "Un día de juego del torneo, con sus canchas."],
                       ["Cancha", "Cuatro jugadores que juegan 3 sets entre ellos (Liga)."],
                       ["Set", "Pareja A contra pareja B, con los juegos de cada una."],
                       ["Cuenta", "Una persona con usuario y contraseña. Una cuenta tiene un "
                                  "jugador en cada organización."],
                       ["Jugador", "Un nombre dentro de la organización. Puede tener cuenta "
                                   "o no (invitado)."]]),
            ("h", "Quién puede hacer qué"),
            ("table", [["Quién", "Qué puede hacer"],
                       ["Visitante", "Ver clasificaciones, torneos, jornadas, sets y jugadores."],
                       ["Jugador", "Lo mismo, y registrar el resultado de sus sets."],
                       ["Administrador", "Todo dentro de su organización: torneos, jornadas, "
                                         "canchas, resultados, jugadores, cuentas y emails."]]),
            ("tip", "Todo se calcula a partir de los sets: si corriges un resultado, la "
                    "clasificación, las estadísticas y las medallas se corrigen solas."),
        ]},
        {"title": "Entrar", "blocks": [
            ("p", f"Abre **{URL}**. La página de inicio es la entrada:"),
            ("bullets", ["**Mi cuenta:** tu usuario (o email) y tu contraseña. Es la que usa "
                         "el administrador.",
                         "**Jugadores:** para crear una cuenta de jugador, o entrar solo con la "
                         "contraseña de un torneo para anotar resultados.",
                         "**Solo mirar:** ver la clasificación de una organización sin entrar."]),
            ("shots", [("login", 0, None, "La entrada"),
                       ("admin_home", 0, None, "Inicio del administrador")]),
            ("p", "Ya adentro, **Inicio** muestra tus torneos (los de tu organización, marcados "
                  "como Admin) y, si también juegas, tus próximos sets. Arriba, bajo el nombre "
                  "PadelScore, tienes siempre tres atajos: el nombre de tu **organización**, "
                  "**Cuentas** y **Emails**."),
        ]},
        {"title": "El menú", "blocks": [
            ("p", "En el teléfono, el menú se abre con el botón de las tres rayas, arriba a la "
                  "derecha (en la computadora las opciones se ven como una fila). Estas son "
                  "sus opciones:"),
            ("shots", [("admin_menu", 0, 570, "El menú abierto")]),
            ("bullets", MENU_COMMON + [
                "**Canchas** (solo administradores): va directo a asignar las canchas de la "
                "jornada más reciente."]),
            ("h", "La barra de arriba (solo administradores)"),
            ("bullets", ["**Organización:** el nombre de tu organización; tócalo para cambiar "
                         "de organización.",
                         "**Cuentas:** las cuentas de los jugadores y del administrador "
                         "(capítulo 10).",
                         "**Emails:** qué emails se enviaron cada día (capítulo 11)."]),
        ]},
        {"title": "Torneos", "blocks": [
            ("p", "En **Torneos** están los torneos **En curso** y los **Pasados** (los "
                  "terminados). Cada tarjeta muestra el tipo de reglas, la fecha, la contraseña "
                  "de jugadores, cuántos jugadores y cuántas jornadas tiene."),
            ("h", "Crear un torneo"),
            ("steps", ["Ve a **Torneos** y toca **Crear torneo**.",
                       "Escribe el **nombre** y la **fecha** de inicio.",
                       "Elige el **tipo de reglas** (ver la tabla de abajo).",
                       "En **Jugadores del torneo**, busca y elige a cada jugador. Si escribes "
                       "un nombre nuevo, se crea el jugador.",
                       "Opcional: escribe la **contraseña de jugadores**. Si la dejas vacía, "
                       "será el nombre del torneo en minúsculas con _ entre palabras.",
                       "Toca **Agregar torneo**."]),
            ("shots", [("tournaments", 0, 1184, "Torneos, con el formulario para crear uno")]),
            ("table", [["Tipo de reglas", "Cómo se juega"],
                       ["Liga de amigos", "Jornadas con canchas de 4. Cada cancha juega 3 sets "
                                          "(cada quien juega una vez con cada uno). Por lugar en "
                                          "la cancha: 9, 6, 4 y 3 puntos, más 1 por set ganado."],
                       ["Americano", "Rondas; las parejas rotan para que todos jueguen con "
                                     "todos. Cada quien suma los puntos de su pareja. Mínimo "
                                     "4 jugadores."],
                       ["Mexicano", "Rondas; la primera se sortea y después el ranking arma "
                                    "las canchas. Mínimo 4 jugadores."],
                       ["Manual individual", "Jornadas con solo la fecha; los sets se agregan a "
                                             "mano. Cada quien suma la diferencia de juegos."]]),
            ("tip", "Puedes cambiar la lista de jugadores después, en la página del torneo."),
        ]},
        {"title": "La página del torneo", "blocks": [
            ("p", "Toca un torneo para abrirlo. De arriba hacia abajo:"),
            ("bullets", ["**Resumen:** el enlace bajo el nombre abre el resumen del torneo "
                         "(podio, lo más destacado y medallas).",
                         "**Jornadas:** un botón por jornada (con palomita si ya se jugó, con "
                         "reloj si tiene sets pendientes) y **+** para crear la siguiente.",
                         "**Agregar jornada:** elige la fecha y toca el botón.",
                         "**Clasificación:** posición, jugador, puntos y los puntos de cada "
                         "jornada (J1, J2...). Bajo cada nombre, sus medallas del torneo. Los "
                         "jugadores con cuenta se ven como \"Nombre (usuario)\"."]),
            ("shots", [("tournament", 0, 1160, "Jornadas y clasificación"),
                       ("summary", 0, 1150, "Resumen del torneo")]),
            ("h", "Jugadores del torneo"),
            ("bullets", ["**Agregar:** busca un jugador y elígelo; si escribes un nombre nuevo, "
                         "puedes crearlo ahí mismo.",
                         "**Quitar (X):** lo saca de la lista. Sus sets y puntos se conservan.",
                         "**Sobre (email) y despertador (recordatorio):** junto a los jugadores "
                         "con cuenta y email, envían de prueba su resumen o su recordatorio."]),
            ("h", "Reemplazar a un jugador"),
            ("p", "Cuando alguien deja el torneo y entra otra persona en su lugar:"),
            ("steps", ["En **Reemplazar a un jugador**, elige quién **sale**.",
                       "Elige qué pasa con los **puntos ya jugados**: **se quedan con quien "
                       "sale** (el nuevo empieza de cero) o **pasan al nuevo jugador** (toma su "
                       "lugar en todo el torneo).",
                       "Elige quién **entra** y confirma. El nuevo toma su lugar en la lista y "
                       "en todos los sets que faltan por jugar."]),
            ("shots", [("tournament", 1600, 2460, "Jugadores y reemplazo"),
                       ("tournament", 2450, None, "Contraseña, terminar y eliminar")]),
            ("h", "Contraseña de jugadores"),
            ("p", "Con ella los jugadores se unen al torneo (o anotan resultados sin cuenta). "
                  "Solo la ven los administradores. Escribe una nueva y toca **Guardar** para "
                  "cambiarla."),
            ("h", "Terminar, reabrir y eliminar"),
            ("bullets", ["**Terminar torneo:** lo pasa a Pasados. No bloquea nada: los "
                         "resultados se pueden seguir corrigiendo. **Reabrir torneo** lo regresa.",
                         "**Eliminar torneo:** borra el torneo con sus jornadas y sets (pide "
                         "confirmación). Los jugadores no se borran."]),
            ("warn", "Eliminar un torneo no se puede deshacer. Si solo terminó la temporada, "
                     "usa **Terminar torneo**."),
        ]},
        {"title": "Jornadas y canchas", "blocks": [
            ("h", "Crear una jornada"),
            ("steps", ["En la página del torneo, elige la **fecha** y toca **Agregar jornada**.",
                       "En la Liga de amigos te pregunta **cuántos jugadores suben y bajan** en "
                       "cada cancha (1 o 2), según la jornada anterior: los mejores de cada "
                       "cancha suben y los últimos bajan.",
                       "Se abre **Asignar canchas** con la propuesta ya armada."]),
            ("shots", [("new_matchday", 0, None, "Nueva jornada: cuántos suben y bajan"),
                       ("courts", 0, None, "Asignar canchas")]),
            ("h", "Asignar canchas"),
            ("steps", ["Revisa los **4 jugadores** de cada cancha y cambia los que haga falta.",
                       "**Agregar cancha** suma una cancha; **Quitar** la elimina.",
                       "Toca **Guardar y crear sets**: se crean los 3 sets de cada cancha, con "
                       "un compañero distinto en cada set."]),
            ("tip", "Si cambias los jugadores de una cancha, sus sets se crean de nuevo. Una "
                    "cancha que ya tiene resultados no se puede cambiar."),
            ("h", "La página de la jornada"),
            ("bullets", ["Cada cancha muestra sus sets. Un set pendiente muestra la "
                         "**probabilidad de ganar** de cada pareja (azul y rojo).",
                         "**Editar** abre el set para poner o corregir el resultado; **Eliminar** "
                         "lo borra.",
                         "**Set en cancha N** agrega un set a mano.",
                         "La **tabla de la cancha** muestra el lugar, los juegos, los sets "
                         "ganados y los puntos de cada jugador.",
                         "**Marcar ausente:** el jugador no vino; juega un suplente en su lugar, "
                         "pero el ausente suma 0 puntos esa jornada y queda último en su cancha.",
                         "**Reemplazar:** cambia a ese jugador en el torneo (capítulo 5).",
                         "Abajo: los **cambios de cancha** para la siguiente jornada, quién "
                         "descansa y **Eliminar jornada**."]),
            ("shots", [("matchday_admin", 0, 1080, "Una jornada: la tarjeta y los sets"),
                       ("matchday_admin", 1080, 2050, "La tabla de la cancha")]),
        ]},
        {"title": "Registrar y corregir resultados", "blocks": [
            ("p", "Los resultados se registran siempre en la página **Editar** de cada set. "
                  "Pueden hacerlo el administrador y los jugadores del set."),
            ("steps", ["Abre la jornada y toca **Editar** en el set.",
                       "Escribe los **juegos** de la pareja A y de la pareja B.",
                       "Toca **Guardar cambios**. La clasificación se actualiza al instante."]),
            ("shots", [("set_edit_admin", 0, None, "Editar set (administrador)")]),
            ("bullets", ["El administrador también puede cambiar la jornada, la cancha y los "
                         "jugadores del set.",
                         "Deja los juegos **vacíos** si el set aún no se juega (queda pendiente).",
                         "Se permite el **empate** (sin ganador).",
                         "Para corregir, entra otra vez a **Editar**: no hay límite de tiempo.",
                         "**Eliminar** un set solo lo puede hacer el administrador."]),
            ("h", "Cómo suma cada tipo de torneo"),
            ("table", [["Tipo", "Cada jugador de la pareja suma"],
                       ["Liga de amigos", "Al jugarse los 3 sets de la cancha: 9, 6, 4 o 3 "
                                          "puntos por lugar, más 1 por set ganado."],
                       ["Americano / Mexicano", "Los puntos (juegos) que ganó su pareja."],
                       ["Manual individual", "La diferencia de juegos: un 6-3 da +3 a los "
                                             "ganadores y -3 a los perdedores."]]),
        ]},
        {"title": "Resumen de la jornada (PDF)", "blocks": PDF_SUMMARY + [
            ("h", "Cómo enviarlo"),
            ("bullets", ["**Enviar por WhatsApp** (la opción principal): desde tu propio "
                         "WhatsApp. En el **celular** se abre el menú de compartir con el PDF; "
                         "eliges WhatsApp y el chat o grupo. En la **computadora** se abre "
                         "WhatsApp con el mensaje y un enlace al PDF.",
                         "**Copiar mensaje:** copia el título y el enlace al PDF, para pegarlo "
                         "donde quieras.",
                         "**Ver PDF:** abre el PDF para verlo o descargarlo.",
                         "**Enviar por email a N jugadores:** lo manda con el PDF adjunto a los "
                         "jugadores del torneo que tienen cuenta con email. La tarjeta muestra "
                         "a cuántos ya les llegó."]),
            ("tip", "El enlace al PDF funciona sin iniciar sesión, así que cualquiera del grupo "
                    "de WhatsApp lo puede abrir."),
        ]},
        {"title": "Jugadores", "blocks": [
            ("p", "En **Jugadores** está la lista de la organización. Escribe un nombre y toca "
                  "**Agregar jugador** para crear uno. **Todas las medallas** muestra el "
                  "catálogo de medallas y quién tiene cada una."),
            ("shots", [("players", 0, 700, "Jugadores"),
                       ("my_summary", 0, 1100, "La página de un jugador")]),
            ("p", "La página de cada jugador tiene cuatro pestañas: **Resumen** (sus torneos, "
                  "compañeros y sets), **Estadísticas** (gráficas y rachas), **Cara a cara** "
                  "(contra otro jugador, con la probabilidad de ganarle) y **Medallas**."),
        ]},
        {"title": "Cuentas", "blocks": [
            ("p", "**Cuentas** (en la barra de arriba) es una tabla con las cuentas de tu "
                  "organización: nombre, usuario, rol, email, celular y jugador. Arriba tienes "
                  "un **buscador** y un filtro por **rol**."),
            ("bullets", ["**Lápiz:** editar la cuenta.",
                         "**Sobre:** enviarle un email de prueba con el resumen de su última "
                         "jornada.",
                         "**Despertador:** enviarle de prueba el recordatorio de sus próximos "
                         "sets (sin importar la fecha)."]),
            ("shots", [("users", 0, None, "Cuentas"),
                       ("user_edit", 0, 1420, "Editar una cuenta")]),
            ("h", "Editar una cuenta"),
            ("bullets", ["**Datos de la cuenta:** usuario, email, celular (país y número), "
                         "nombre, apellido y nombre para mostrar. Toca **Guardar**.",
                         "**Contraseña:** escribe una nueva y toca Guardar. La persona tendrá que "
                         "entrar con la nueva.",
                         "**Jugador:** el jugador de esta organización que es esta cuenta. "
                         "**Desvincular jugador** lo separa de la cuenta.",
                         "**¿También eres tú?:** si la persona quedó registrada dos veces con "
                         "nombres distintos, elige el duplicado, marca la casilla y toca **Unir "
                         "jugadores**: sus sets pasan al jugador de la cuenta."]),
            ("warn", "Unir jugadores no se puede deshacer. No se puede unir a dos jugadores "
                     "que jugaron en el mismo set."),
        ]},
        {"title": "Emails", "blocks": [
            ("p", "PadelScore manda emails automáticos a los jugadores con cuenta y email:"),
            ("bullets", ["**Recordatorio del día de juego**, en la mañana: su cancha, su "
                         "posición, sus sets y rivales, y la probabilidad de ganar cada uno.",
                         "**Resumen de la jornada**, al día siguiente: su lugar, sus sets, la "
                         "clasificación, sus gráficas y sus medallas.",
                         "**Resumen en PDF**, cuando lo envías desde la tarjeta de la jornada."]),
            ("p", "Cada jugador puede apagar estos emails desde su perfil o con el enlace al "
                  "final de cada email."),
            ("shots", [("emails", 0, None, "Emails de un día")]),
            ("p", "La página **Emails** muestra qué se mandó cada día: cambia de día con las "
                  "flechas o el calendario, filtra por estado y por tipo, y busca por nombre. "
                  "Los totales de arriba dicen cuántos se **enviaron**, cuántos **fallaron** y "
                  "cuántos esperan por el **límite de Azure**."),
            ("tip", "El servicio gratis permite unos **10 emails por hora**. Si hay más, los "
                    "demás salen solos en las horas siguientes."),
        ]},
        {"title": "Sets, clasificación, medallas y reglamento", "blocks": [
            ("bullets", ["**Sets:** todos los sets; filtra por torneo, jornada y jugador. Cada "
                         "uno tiene **Editar** y **Eliminar**.",
                         "**Clasificación:** la tabla del torneo actual y los últimos sets.",
                         "**Medallas:** se ganan jugando y se calculan solas (Gloria, Rivalidad "
                         "y las de broma). Si corriges un resultado, se corrigen.",
                         "**Reglamento:** las reglas de cada tipo de torneo."]),
            ("shots", [("sets", 0, 1000, "Sets con filtros"),
                       ("medals", 0, 1000, "Todas las medallas")]),
        ]},
        INSTALL,
        {"title": "Preguntas frecuentes", "blocks": [
            ("h", "Un jugador no puede registrar su resultado"),
            ("p", "Debe entrar con su cuenta y estar en el torneo (unirse con la contraseña de "
                  "jugadores), o entrar sin cuenta con esa contraseña. Revisa la contraseña en "
                  "la página del torneo."),
            ("h", "Se registró mal un resultado"),
            ("p", "Abre el set, toca **Editar**, corrige los juegos y guarda. Todo se recalcula."),
            ("h", "Un jugador faltó"),
            ("p", "En la tabla de su cancha toca **Marcar ausente**. Si alguien juega en su "
                  "lugar, los resultados cuentan para los demás, pero el ausente suma 0."),
            ("h", "Entró un jugador nuevo a mitad del torneo"),
            ("p", "Usa **Reemplazar a un jugador** si toma el lugar de alguien, o agrégalo en "
                  "**Jugadores del torneo** si se suma."),
            ("h", "Alguien quedó registrado dos veces"),
            ("p", "En **Cuentas**, edita su cuenta y usa **¿También eres tú?** para unir los "
                  "dos jugadores."),
            ("h", "Un jugador olvidó su contraseña"),
            ("p", "En **Cuentas**, edita su cuenta y escríbele una contraseña nueva."),
        ]},
    ],
}

# --- Player manual ---------------------------------------------------------------------

PLAYER_MANUAL = {
    "title": "Manual del jugador",
    "subtitle": "Cómo entrar, unirte a tu torneo, registrar resultados y ver tus "
                "estadísticas, medallas y resúmenes.",
    "who": "Para los **jugadores** de una liga. Con tu cuenta registras los resultados de "
           "tus sets, ves tus próximos partidos con la probabilidad de ganar, tus "
           "estadísticas y tus medallas, y recibes recordatorios por email.",
    "sections": [
        {"title": "Crear tu cuenta y entrar", "blocks": [
            ("p", f"Abre **{URL}**. Si no tienes cuenta, en **Jugadores** toca **Crear cuenta**."),
            ("steps", ["Escribe tu **nombre**, **apellido** y el **nombre para mostrar** (el "
                       "que se verá en las clasificaciones).",
                       "Elige un **usuario** y escribe tu **email**.",
                       "Opcional: tu **celular** (elige el país y escribe el número).",
                       "Escribe una **contraseña** de al menos 8 caracteres, dos veces.",
                       "Toca **Crear cuenta**."]),
            ("shots", [("signup", 0, None, "Crear cuenta"),
                       ("login", 0, None, "Para entrar después: Mi cuenta")]),
            ("p", "Las siguientes veces entra en **Mi cuenta** con tu usuario (o email) y tu "
                  "contraseña."),
        ]},
        {"title": "Unirte a un torneo", "blocks": [
            ("p", "El organizador te da la **contraseña del torneo**. Con ella te unes:"),
            ("steps", ["En **Inicio**, en **Unirme a un torneo**, escribe la contraseña y toca "
                       "**Unirme**.",
                       "Te pregunta **¿Quién eres?** en ese torneo: elige tu nombre de la lista "
                       "(si el organizador ya te había agregado) o **Crear un jugador nuevo para "
                       "mí**.",
                       "Listo: el torneo aparece en **Mis torneos** y tus sets en **Mis "
                       "próximos sets**."]),
            ("shots", [("player_home", 0, 420, "Unirme a un torneo, en Inicio")]),
            ("tip", "Si ya tenías un jugador con otro nombre en esa organización, al elegirte "
                    "en la lista te pregunta si eres tú y une los dos."),
        ]},
        {"title": "Tu inicio", "blocks": [
            ("p", "**Inicio** es tu tablero:"),
            ("bullets", ["**Tu última jornada:** con el enlace a **Mi jornada** (tu resumen "
                         "para compartir).",
                         "**Mis próximos sets:** los sets que te faltan, del más próximo al más "
                         "lejano: fecha, torneo, jornada, cancha, tu pareja y tus rivales. La "
                         "barra muestra la **probabilidad de ganar**: en azul tu pareja (A) y en "
                         "rojo la otra. **Resultado** abre el set para registrar el marcador.",
                         "**Mis torneos:** tus torneos con tu posición y puntos."]),
            ("shots", [("player_home", 0, 760, "Inicio: tu última jornada y tus sets"),
                       ("player_home", 760, 1442, "Más sets y tus torneos")]),
            ("p", "La probabilidad se calcula con los sets que ha jugado cada jugador: el "
                  "porcentaje de sets ganados de cada pareja, comparados entre sí."),
        ]},
        {"title": "El menú", "blocks": [
            ("p", "En el teléfono, el menú se abre con el botón de las tres rayas, arriba a la "
                  "derecha:"),
            ("shots", [("player_menu", 0, 570, "El menú abierto")]),
            ("bullets", MENU_COMMON[:1] + ["**Mi resumen:** tu página de jugador (resumen, "
                                           "estadísticas, cara a cara y medallas)."]
             + MENU_COMMON[1:]),
        ]},
        {"title": "Registrar un resultado", "blocks": [
            ("p", "Cualquiera de los cuatro jugadores de un set puede registrar su resultado."),
            ("steps", ["En **Inicio**, en **Mis próximos sets**, toca **Resultado**. (O abre "
                       "la jornada y toca **Editar** en tu set.)",
                       "Escribe los **juegos** de cada pareja: la de la izquierda (A) y la de "
                       "la derecha (B).",
                       "Toca **Guardar**. Regresas a la jornada con el resultado y la "
                       "clasificación al día."]),
            ("shots", [("matchday_player", 0, 1150, "La jornada: Editar en cada set"),
                       ("set_score", 0, None, "Resultado: los juegos de cada pareja")]),
            ("bullets", ["Se permite el empate.",
                       "¿Te equivocaste? Entra otra vez a **Editar** y corrígelo.",
                       "En los torneos **Manual individual** también puedes crear sets."]),
        ]},
        {"title": "Tu torneo y tu jornada", "blocks": [
            ("p", "La página del torneo muestra las **jornadas** (palomita: jugada; reloj: "
                  "pendiente) y la **clasificación**: posición, puntos totales y puntos de "
                  "cada jornada (J1, J2...). Bajo cada nombre, sus **medallas** del torneo."),
            ("shots", [("player_tournament", 0, 1100, "Clasificación del torneo"),
                       ("recap", 0, 1253, "Mi jornada")]),
            ("h", "Mi jornada"),
            ("p", "En cada jornada, **Mi jornada** resume cómo te fue: tu lugar en la cancha, "
                  "tus puntos y sets ganados, tu posición (y cuántos lugares subiste o bajaste), "
                  "tu cancha para la próxima jornada y las medallas que ganaste ese día. "
                  "**Compartir por WhatsApp** lo manda a quien quieras."),
            ("h", "Cómo se suman los puntos (Liga de amigos)"),
            ("p", "Cuando tu cancha termina sus 3 sets, cada jugador recibe puntos por su lugar "
                  "en la cancha (9, 6, 4 y 3) más 1 punto por cada set ganado. El lugar se "
                  "decide por sets ganados, luego por diferencia de juegos. Si faltas, sumas 0 "
                  "esa jornada. Al final de cada jornada los mejores suben de cancha y los "
                  "últimos bajan. Las reglas completas están en **Reglamento**."),
        ]},
        {"title": "Tus estadísticas y medallas", "blocks": [
            ("p", "En el menú, **Mi resumen** abre tu página de jugador, con cuatro pestañas:"),
            ("bullets", ["**Resumen:** tus torneos (jornada por jornada), tus compañeros y "
                         "tus sets.",
                         "**Estadísticas:** sets, victorias, porcentaje, diferencia de juegos, "
                         "tu forma (los últimos sets), tus rachas, gráficas de puntos "
                         "acumulados, y lo más destacado: con quién juegas y ganas más, tu "
                         "rival, tu bestia negra y tu víctima favorita.",
                         "**Cara a cara:** elige a otro jugador para ver sus sets frente a "
                         "frente, como pareja, y la **probabilidad de ganarle**.",
                         "**Medallas:** las que ya ganaste y, en gris, las que te faltan."]),
            ("shots", [("my_stats", 0, 1000, "Estadísticas"),
                       ("my_medals", 0, 900, "Medallas")]),
            ("shots", [("vs", 0, 900, "Cara a cara")]),
            ("tip", "Las medallas se calculan solas a partir de tus sets. Hay de gloria (como "
                    "Bien prendido o Rey de la cancha), de rivalidad y de broma (como Salado)."),
        ]},
        {"title": "Resumen de la jornada (PDF)", "blocks": PDF_SUMMARY + [
            ("bullets", ["**Ver PDF** lo abre para verlo o descargarlo.",
                         "**Enviar por WhatsApp** lo comparte desde tu teléfono.",
                         "**Copiar mensaje** copia el enlace al PDF.",
                         "Si tienes cuenta con email, el organizador también te lo puede "
                         "mandar por email, con el PDF adjunto."]),
        ]},
        {"title": "Tu perfil y tus emails", "blocks": [
            ("p", "Toca tu nombre en el menú para abrir tu perfil:"),
            ("bullets", ["**Todo mi pádel:** tus números en todas tus organizaciones (sets, "
                         "victorias, torneos, medallas).",
                         "Por cada organización: tus torneos, tus sets por jugar y los últimos.",
                         "**Datos de la cuenta:** nombre, apellido, nombre para mostrar, usuario, "
                         "email y celular.",
                         "**Emails:** activa o apaga el **resumen de tu jornada** (al día "
                         "siguiente) y el **recordatorio el día que juegas** (cancha, rivales y "
                         "probabilidades).",
                         "**Contraseña:** escribe la actual y la nueva dos veces."]),
            ("shots", [("me", 0, 460, "Todo mi pádel"),
                       ("me", 2420, 3793, "Datos de la cuenta, emails y contraseña")]),
            ("tip", "Cada email trae al final un enlace para dejar de recibirlo."),
        ]},
        INSTALL,
        {"title": "Sin cuenta: solo anotar resultados", "blocks": [
            ("p", "Si solo quieres anotar un resultado una vez, en la entrada abre **Solo anotar "
                  "resultados, sin cuenta** y escribe la contraseña del torneo. Podrás "
                  "registrar los resultados de ese torneo desde la página de la jornada."),
            ("p", "Sin cuenta no tendrás tus próximos sets en Inicio, ni tu perfil, ni los "
                  "emails. Puedes crear tu cuenta cuando quieras y elegir tu nombre en el torneo: "
                  "tus resultados anteriores se quedan contigo."),
        ]},
        {"title": "Preguntas frecuentes", "blocks": [
            ("h", "No veo mi torneo"),
            ("p", "Únete con la contraseña del torneo en **Inicio > Unirme a un torneo**. Pídesela "
                  "al organizador."),
            ("h", "Registré mal un resultado"),
            ("p", "Abre el set, toca **Editar**, corrígelo y guarda."),
            ("h", "Aparezco dos veces en la lista"),
            ("p", "Al unirte con la contraseña, elige tu nombre y confirma que eres tú: se unen. "
                  "O pídele al organizador que los una."),
            ("h", "Olvidé mi contraseña"),
            ("p", "Pídele al organizador que te ponga una nueva desde Cuentas. Luego cámbiala en "
                  "tu perfil."),
            ("h", "No me llegan los emails"),
            ("p", "Revisa tu email en tu perfil, que los emails estén activados y tu carpeta de "
                  "spam. Llegan de una dirección DoNotReply."),
        ]},
    ],
}
