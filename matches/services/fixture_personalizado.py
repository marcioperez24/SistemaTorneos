import datetime
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone
from matches.models import Torneo, GrupoTorneo, EquipoGrupoTorneo, Partido, BitacoraTorneo
from teams.models import Equipo
from django.contrib.auth import get_user_model

User = get_user_model()


def generar_algoritmo_round_robin(equipos_list):
    """
    Genera la estructura Round-Robin (Sistema Berger) para una lista de equipos.
    Soporta cantidades pares e impares (agrega un BYE / descanso implícito para impares).
    Retorna una lista de rondas con partidos y descansos.
    """
    equipos = list(equipos_list)
    es_impar = len(equipos) % 2 != 0
    if es_impar:
        equipos.append(None)  # None representa el descanso (BYE)

    n = len(equipos)
    total_rondas = n - 1
    partidos_por_ronda = n // 2
    rondas = []

    # Copia de trabajo para rotación
    rotated = list(equipos)

    for r in range(total_rondas):
        ronda_jornada = r + 1
        partidos_ronda = []
        descanso_equipo = None

        for i in range(partidos_por_ronda):
            eq1 = rotated[i]
            eq2 = rotated[n - 1 - i]

            if eq1 is None:
                descanso_equipo = eq2
            elif eq2 is None:
                descanso_equipo = eq1
            else:
                # Alternar localía por ronda e índice para equilibrar partidos de local/visitante
                if (r + i) % 2 == 0:
                    partidos_ronda.append((eq1, eq2))
                else:
                    partidos_ronda.append((eq2, eq1))

        rondas.append({
            'jornada': ronda_jornada,
            'partidos': partidos_ronda,
            'descanso': descanso_equipo
        })

        # Rotar elementos conservando el primer elemento fijo
        rotated = [rotated[0]] + [rotated[-1]] + rotated[1:-1]

    return rondas


def generar_fixture_grupo_completo(grupo, equipos_list, formato='una_vuelta'):
    """
    Genera todos los enfrentamientos para un grupo (1 o 2 vueltas).
    """
    equipos_ordenados = sorted(list(equipos_list), key=lambda x: x.id)
    rondas_v1 = generar_algoritmo_round_robin(equipos_ordenados)

    fixture_final = []

    # Primera Vuelta
    for r in rondas_v1:
        for local, visitante in r['partidos']:
            fixture_final.append({
                'grupo': grupo,
                'jornada': r['jornada'],
                'equipo_local': local,
                'equipo_visitante': visitante,
                'numero_vuelta': 1,
                'descanso': None
            })
        if r['descanso']:
            fixture_final.append({
                'grupo': grupo,
                'jornada': r['jornada'],
                'equipo_local': None,
                'equipo_visitante': None,
                'numero_vuelta': 1,
                'descanso': r['descanso']
            })

    # Segunda Vuelta (Ida y Vuelta)
    if formato == 'ida_vuelta':
        num_jornadas_v1 = len(rondas_v1)
        for r in rondas_v1:
            jornada_v2 = r['jornada'] + num_jornadas_v1
            for local, visitante in r['partidos']:
                # Invertir localía en la segunda vuelta
                fixture_final.append({
                    'grupo': grupo,
                    'jornada': jornada_v2,
                    'equipo_local': visitante,
                    'equipo_visitante': local,
                    'numero_vuelta': 2,
                    'descanso': None
                })
            if r['descanso']:
                fixture_final.append({
                    'grupo': grupo,
                    'jornada': jornada_v2,
                    'equipo_local': None,
                    'equipo_visitante': None,
                    'numero_vuelta': 2,
                    'descanso': r['descanso']
                })

    return fixture_final


def calcular_vista_previa_fixture(torneo, organizacion, config):
    """
    Calcula dinámicamente la vista previa del fixture sin guardar nada en la base de datos.
    Soporta asignación de horarios, fechas, árbitros, vocales y detección de conflictos.
    """
    fecha_inicio = config.get('fecha_inicio', datetime.date.today())
    dias_semana = config.get('dias_semana', [5, 6])  # 5=Sábado, 6=Domingo por defecto
    horas_str = config.get('horas', ['08:00', '10:00', '12:00', '14:00'])
    estadio = config.get('estadio', 'Estadio Principal')
    grupos_ids = config.get('grupos_ids', [])
    asignar_arbitro = config.get('asignar_arbitro', False)
    asignar_vocal = config.get('asignar_vocal', False)

    if grupos_ids:
        grupos = GrupoTorneo.objects.filter(torneo=torneo, id__in=grupos_ids, activo=True).order_by('orden', 'id')
    else:
        grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden', 'id')

    arbitros = list(User.objects.filter(role='arbitro', organizaciones__organizacion=organizacion).distinct()) if asignar_arbitro else []
    vocales = list(User.objects.filter(role='vocal', organizaciones__organizacion=organizacion).distinct()) if asignar_vocal else []

    vista_previa_grupos = []
    conflictos = []
    advertencias = []
    total_partidos_calculados = 0
    total_descansos = 0

    # Mapa de ocupación en tiempo de cálculo: (fecha_hora, tipo, obj_id)
    ocupacion_equipos = set()
    ocupacion_estadios = set()
    ocupacion_arbitros = set()
    ocupacion_vocales = set()

    for grupo in grupos:
        asigs = EquipoGrupoTorneo.objects.filter(grupo=grupo).select_related('equipo')
        equipos = [a.equipo for a in asigs]

        if len(equipos) < 2:
            advertencias.append(f"El grupo '{grupo.nombre}' tiene menos de 2 equipos ({len(equipos)}), no se generarán partidos.")
            continue

        matches_grupo = generar_fixture_grupo_completo(grupo, equipos, formato=grupo.formato_enfrentamientos)

        # Agrupar partidos por jornada dentro del grupo
        jornadas_dict = {}
        for m in matches_grupo:
            j = m['jornada']
            if j not in jornadas_dict:
                jornadas_dict[j] = {'partidos': [], 'descanso': None}
            if m['descanso']:
                jornadas_dict[j]['descanso'] = m['descanso']
            else:
                jornadas_dict[j]['partidos'].append(m)

        # Asignar fechas y horas a las jornadas del grupo
        fecha_actual = fecha_inicio
        jornadas_lista = []
        idx_arbitro = 0
        idx_vocal = 0

        for num_jornada in sorted(jornadas_dict.keys()):
            # Buscar el siguiente día de la semana permitido
            while fecha_actual.weekday() not in dias_semana:
                fecha_actual += datetime.timedelta(days=1)

            partidos_jornada = []
            hora_idx = 0

            for p in jornadas_dict[num_jornada]['partidos']:
                # Calcular hora
                hora_raw = horas_str[hora_idx % len(horas_str)]
                hora_idx += 1
                try:
                    h_parts = [int(x) for x in hora_raw.split(':')]
                    hora_time = datetime.time(h_parts[0], h_parts[1])
                except Exception:
                    hora_time = datetime.time(9, 0)

                dt_partido = datetime.datetime.combine(fecha_actual, hora_time)
                if timezone.is_naive(dt_partido):
                    dt_partido = timezone.make_aware(dt_partido, timezone.get_current_timezone())

                local = p['equipo_local']
                visitante = p['equipo_visitante']

                # Asignar árbitro y vocal
                arb = arbitros[idx_arbitro % len(arbitros)] if arbitros else None
                voc = vocales[idx_vocal % len(vocales)] if vocales else None
                if arbitros:
                    idx_arbitro += 1
                if vocales:
                    idx_vocal += 1

                # Detección de conflictos
                key_local = (dt_partido, 'equipo', local.id)
                key_visitante = (dt_partido, 'equipo', visitante.id)
                key_estadio = (dt_partido, 'estadio', estadio)

                if key_local in ocupacion_equipos:
                    conflictos.append(f"El equipo '{local.nombre}' tiene dos partidos en el mismo horario: {dt_partido.strftime('%Y-%m-%d %H:%M')}.")
                if key_visitante in ocupacion_equipos:
                    conflictos.append(f"El equipo '{visitante.nombre}' tiene dos partidos en el mismo horario: {dt_partido.strftime('%Y-%m-%d %H:%M')}.")
                if key_estadio in ocupacion_estadios:
                    advertencias.append(f"El estadio '{estadio}' está ocupado para múltiples partidos a las {dt_partido.strftime('%Y-%m-%d %H:%M')}.")

                ocupacion_equipos.add(key_local)
                ocupacion_equipos.add(key_visitante)
                ocupacion_estadios.add(key_estadio)

                if arb:
                    key_arb = (dt_partido, 'arbitro', arb.id)
                    if key_arb in ocupacion_arbitros:
                        advertencias.append(f"El árbitro '{arb.get_full_name() or arb.username}' tiene asignaciones simultáneas a las {dt_partido.strftime('%H:%M')}.")
                    ocupacion_arbitros.add(key_arb)

                if voc:
                    key_voc = (dt_partido, 'vocal', voc.id)
                    if key_voc in ocupacion_vocales:
                        advertencias.append(f"El vocal '{voc.get_full_name() or voc.username}' tiene asignaciones simultáneas a las {dt_partido.strftime('%H:%M')}.")
                    ocupacion_vocales.add(key_voc)

                total_partidos_calculados += 1
                partidos_jornada.append({
                    'equipo_local': local,
                    'equipo_visitante': visitante,
                    'fecha_hora': dt_partido,
                    'estadio': estadio,
                    'arbitro': arb,
                    'vocal': voc,
                    'numero_vuelta': p['numero_vuelta']
                })

            if jornadas_dict[num_jornada]['descanso']:
                total_descansos += 1

            jornadas_lista.append({
                'numero_jornada': num_jornada,
                'fecha': fecha_actual,
                'partidos': partidos_jornada,
                'descanso': jornadas_dict[num_jornada]['descanso']
            })

            # Avanzar fecha para la siguiente jornada
            fecha_actual += datetime.timedelta(days=1)

        vista_previa_grupos.append({
            'grupo': grupo,
            'jornadas': jornadas_lista,
            'total_partidos': sum(len(j['partidos']) for j in jornadas_lista),
            'total_jornadas': len(jornadas_lista)
        })

    # Partidos programados existentes que serán reemplazados
    partidos_existentes_afectados = Partido.objects.filter(
        torneo=torneo,
        grupo_personalizado__in=grupos,
        estado='programado'
    ).count()

    return {
        'grupos_vista_previa': vista_previa_grupos,
        'total_partidos': total_partidos_calculados,
        'total_descansos': total_descansos,
        'conflictos': conflictos,
        'advertencias': advertencias,
        'partidos_existentes_afectados': partidos_existentes_afectados,
        'grupos_ids': [g.id for g in grupos]
    }


def guardar_fixture_personalizado(torneo, organizacion, usuario, vista_previa_data):
    """
    Guarda el fixture calculado en la base de datos dentro de una transacción atómica.
    Previene duplicados y bloquea regeneraciones si existen partidos finalizados/en juego.
    """
    grupos_ids = vista_previa_data.get('grupos_ids', [])
    grupos = GrupoTorneo.objects.filter(torneo=torneo, id__in=grupos_ids)

    with transaction.atomic():
        # Regla: Verificar que ningún grupo afectado tenga partidos finalizados o en juego
        partidos_bloqueados = Partido.objects.filter(
            torneo=torneo,
            grupo_personalizado__in=grupos,
            estado__in=['finalizado', 'en_juego']
        )
        if partidos_bloqueados.exists():
            raise ValidationError(
                "Este grupo tiene partidos iniciados o finalizados. "
                "No se puede regenerar automáticamente porque se perdería la integridad histórica."
            )

        # Eliminar únicamente los partidos programados de los grupos seleccionados
        Partido.objects.filter(
            torneo=torneo,
            grupo_personalizado__in=grupos,
            estado='programado'
        ).delete()

        partidos_creados = []
        for g_data in vista_previa_data['grupos_vista_previa']:
            grupo = g_data['grupo']
            for j_data in g_data['jornadas']:
                jornada_num = j_data['numero_jornada']
                for p_data in j_data['partidos']:
                    # Doble comprobación contra duplicados
                    existe = Partido.objects.filter(
                        torneo=torneo,
                        grupo_personalizado=grupo,
                        equipo_local=p_data['equipo_local'],
                        equipo_visitante=p_data['equipo_visitante'],
                        numero_vuelta=p_data['numero_vuelta']
                    ).exists()

                    if not existe:
                        partido = Partido.objects.create(
                            organizacion=organizacion,
                            torneo=torneo,
                            grupo_personalizado=grupo,
                            grupo=grupo.nombre,
                            equipo_local=p_data['equipo_local'],
                            equipo_visitante=p_data['equipo_visitante'],
                            fecha_hora=p_data['fecha_hora'],
                            estadio=p_data['estadio'],
                            jornada=jornada_num,
                            temporada=torneo.temporada,
                            fase='grupos',
                            estado='programado',
                            numero_vuelta=p_data['numero_vuelta'],
                            arbitro=p_data.get('arbitro'),
                            vocal=p_data.get('vocal')
                        )
                        partidos_creados.append(partido)

        # Auditoría
        BitacoraTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            usuario=usuario,
            accion="Generación de Fixture Personalizado",
            detalles=f"Se generaron {len(partidos_creados)} partidos en {len(grupos)} grupos.",
            valores_nuevos={'partidos_creados': len(partidos_creados), 'grupos': [g.nombre for g in grupos]}
        )

    return partidos_creados


def mover_equipo_y_regenerar_fixtures(torneo, organizacion, usuario, asignacion, grupo_destino):
    """
    Regenera de forma segura los fixtures de los dos grupos afectados al mover un equipo.
    """
    grupo_origen = asignacion.grupo

    with transaction.atomic():
        # Verificar partidos finalizados en grupo de origen o destino
        partidos_bloqueantes = Partido.objects.filter(
            torneo=torneo,
            grupo_personalizado__in=[grupo_origen, grupo_destino],
            estado__in=['finalizado', 'en_juego']
        )
        if partidos_bloqueantes.exists():
            raise ValidationError(
                "No es posible mover el equipo porque ya participó en partidos iniciados o finalizados. "
                "Esta operación requiere una corrección administrativa especial para conservar el historial."
            )

        # 1. Eliminar partidos programados de ambos grupos
        Partido.objects.filter(
            torneo=torneo,
            grupo_personalizado__in=[grupo_origen, grupo_destino],
            estado='programado'
        ).delete()

        # 2. Actualizar la asignación del grupo
        grupo_origen_nombre = grupo_origen.nombre
        asignacion.grupo = grupo_destino
        asignacion.save()

        # 3. Regenerar fixture del grupo origen
        config_default = {
            'fecha_inicio': datetime.date.today(),
            'dias_semana': [5, 6],
            'horas': ['08:00', '10:00', '12:00'],
            'estadio': 'Estadio Principal',
            'grupos_ids': [grupo_origen.id, grupo_destino.id]
        }
        vp_data = calcular_vista_previa_fixture(torneo, organizacion, config_default)
        guardar_fixture_personalizado(torneo, organizacion, usuario, vp_data)

        # 4. Auditoría
        BitacoraTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            usuario=usuario,
            accion="Movimiento de Equipo y Regeneración de Fixture",
            detalles=f"Equipo '{asignacion.equipo.nombre}' movido de '{grupo_origen_nombre}' a '{grupo_destino.nombre}'. Fixtures de ambos grupos regenerados.",
            valores_anteriores={'grupo_origen': grupo_origen_nombre},
            valores_nuevos={'grupo_destino': grupo_destino.nombre}
        )
