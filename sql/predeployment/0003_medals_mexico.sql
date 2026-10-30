-- Medals in Mexican Spanish: the names and texts of 0002 used expressions from Spain
-- (pastelero, gafe, farolillo rojo, rosco...). Same codes and rules; only the words
-- change. The English names follow the new meaning.

UPDATE medal_types SET name_es = 'Bien prendido', name_en = 'On fire',
  how_es = '3, 5 o 10 sets ganados seguidos (bronce, plata, oro).'
  WHERE code = 'racha';
UPDATE medal_types SET name_es = 'Rey de la cancha', name_en = 'King of the court'
  WHERE code = 'rey_pista';
UPDATE medal_types SET name_es = 'Pa'' arriba', name_en = 'Moving on up',
  how_es = 'Subir de cancha 3 veces (Liga).'
  WHERE code = 'escalador';
UPDATE medal_types SET name_es = 'Zapatero', name_en = 'Shutout',
  how_es = 'Ganar un set 6-0: le pusiste zapato.', how_en = 'Win a set 6-0.'
  WHERE code = 'rosco';
UPDATE medal_types SET name_es = 'La Muralla', name_en = 'The Wall',
  how_es = 'Ganar un set dejando al rival en 1 juego o menos.'
  WHERE code = 'muro';
UPDATE medal_types SET name_es = 'De infarto', name_en = 'Nail-biter',
  how_es = 'Ganar un set 7-6.'
  WHERE code = 'infarto';
UPDATE medal_types SET name_es = 'Dupla dorada', name_en = 'Golden duo',
  how_es = '5 victorias con la misma pareja.'
  WHERE code = 'pareja_oro';
UPDATE medal_types SET name_es = 'Asistencia perfecta', name_en = 'Perfect attendance',
  how_es = 'Jugar todas las jornadas de un torneo terminado.'
  WHERE code = 'asistencia';
UPDATE medal_types SET name_es = 'Colmilludo', name_en = 'Old fox',
  how_es = '25, 50 o 100 sets jugados (bronce, plata, oro).'
  WHERE code = 'veterano';
UPDATE medal_types SET name_es = 'El Clásico', name_en = 'The Derby',
  how_es = 'El rival con el que más has jugado en contra (3 sets o más).',
  how_en = 'The opponent you have played against most (3 sets or more).'
  WHERE code = 'rival';
UPDATE medal_types SET name_es = 'Es su papá', name_en = 'Their daddy',
  how_es = 'Ganarle 3 sets o más al mismo rival.',
  how_en = 'Beat the same opponent in 3 sets or more.'
  WHERE code = 'verdugo';
UPDATE medal_types SET name_es = 'Salado', name_en = 'Jinxed',
  how_es = '3, 5 u 8 sets perdidos seguidos (bronce, plata, oro).'
  WHERE code = 'gafe';
UPDATE medal_types SET name_es = 'Le pusieron zapato', name_en = 'Got shut out',
  how_es = 'Perder un set 0-6.', how_en = 'Lose a set 0-6.'
  WHERE code = 'comio_rosco';
UPDATE medal_types SET name_es = 'Sotanero', name_en = 'Basement dweller',
  how_es = 'Último lugar en un torneo terminado.', how_en = 'Last in an ended tournament.'
  WHERE code = 'farolillo';
UPDATE medal_types SET name_es = 'Jornada pa'' olvidar', name_en = 'Day to forget',
  how_es = 'Perder los 3 sets de una jornada de Liga.'
  WHERE code = 'jornada_negra';
UPDATE medal_types SET name_es = 'Cuesta abajo', name_en = 'Going down',
  how_es = 'Bajar de cancha 3 veces (Liga).'
  WHERE code = 'paracaidas';
UPDATE medal_types SET name_es = 'Ya tiene papá', name_en = 'Has a daddy',
  how_es = 'Que el mismo rival te gane 5 sets o más.',
  how_en = 'The same opponent beats you in 5 sets or more.'
  WHERE code = 'bestia_negra';
UPDATE medal_types SET name_es = 'Se lo tragó la tierra', name_en = 'Vanished',
  how_es = 'Faltar a 2 jornadas o más.'
  WHERE code = 'fantasma';
