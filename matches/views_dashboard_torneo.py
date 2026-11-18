import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.urls import reverse

from matches.models import (
    Torneo, GrupoTorneo, Partido, EventoPartido,
    EquipoGrupoTorneo, LlaveEliminatoria, ResultadoFinalTorneo, Estadio
)
from teams.models import Equipo, FichaJugador, FichaDT
from finances.models import MultaTarjeta

logger = logging.getLogger(__name__)


@login_required
def dashboard_torneo(request, torneo_id):
    """
    Dashboard ejecutivo, analítico e interactivo específico para un Torneo / Liga.
    Consolida métricas en tiempo real de avance, equipos, jugadores, estadísticas
    deportivas, disciplina, finanzas y posiciones.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id)
    org = torneo.organizacion or getattr(request, 'organizacion', None)

    # Permisos
    user = request.user
    es_gestor = user.is_superuser or user.role in ['superadmin', 'comision', 'dirigente', 'admin', 'organizador']

    # 1. Equipos y Fichas de Jugadores / DTs
    equipos_qs = torneo.equipos.all().order_by('nombre')
    total_equipos = equipos_qs.count()
    equipos_ids = list(equipos_qs.values_list('id', flat=True))

    fichas_jugador_qs = FichaJugador.objects.filter(
        Q(torneo=torneo) | Q(equipo_id__in=equipos_ids, torneo__isnull=True)
    ).distinct()
    total_jugadores = fichas_jugador_qs.count()
    jugadores_habilitados = fichas_jugador_qs.filter(estado_validacion='aprobado').count()
    jugadores_pendientes = fichas_jugador_qs.filter(estado_validacion='pendiente').count()
    jugadores_con_firma = fichas_jugador_qs.filter(firma_digital=True).count()
    promedio_jugadores_equipo = round(total_jugadores / total_equipos, 1) if total_equipos > 0 else 0

    total_dts = FichaDT.objects.filter(
        Q(torneo=torneo) | Q(equipo_id__in=equipos_ids, torneo__isnull=True)
    ).distinct().count()

    # 2. Partidos y Avance Operativo
    partidos_qs = list(
        Partido.objects.filter(torneo=torneo)
        .select_related('equipo_local', 'equipo_visitante', 'estadio_fk', 'arbitro', 'vocal')
        .order_by('jornada', 'fecha_hora')
    )
    total_partidos = len(partidos_qs)
    partidos_finalizados_qs = [p for p in partidos_qs if p.estado == 'finalizado']
    partidos_finalizados = len(partidos_finalizados_qs)
    partidos_en_curso = sum(1 for p in partidos_qs if p.estado == 'en_curso')
    partidos_programados = sum(1 for p in partidos_qs if p.estado == 'programado')
    partidos_anulados = sum(1 for p in partidos_qs if p.estado == 'anulado')

    porcentaje_avance = round((partidos_finalizados / total_partidos * 100), 1) if total_partidos > 0 else 0.0

    # Estado general visual
    if total_partidos == 0:
        estado_label = "En Configuración"
        estado_badge = "bg-secondary text-white"
        estado_icon = "fa-screwdriver-wrench"
    elif partidos_finalizados == total_partidos and total_partidos > 0:
        estado_label = "Torneo Finalizado"
        estado_badge = "bg-dark text-white"
        estado_icon = "fa-flag-checkered"
    elif partidos_finalizados > 0 or partidos_en_curso > 0:
        estado_label = "En Competencia"
        estado_badge = "bg-success text-white"
        estado_icon = "fa-circle-play"
    else:
        estado_label = "Fixture Listo / Próximo a Iniciar"
        estado_badge = "bg-primary text-white"
        estado_icon = "fa-calendar-check"

    # 3. Métricas de Goles y Marcadores
    goles_locales = sum(p.goles_local or 0 for p in partidos_finalizados_qs)
    goles_visitantes = sum(p.goles_visitante or 0 for p in partidos_finalizados_qs)
    total_goles = goles_locales + goles_visitantes
    promedio_goles = round(total_goles / partidos_finalizados, 2) if partidos_finalizados > 0 else 0.0

    victorias_locales = sum(1 for p in partidos_finalizados_qs if (p.goles_local or 0) > (p.goles_visitante or 0))
    victorias_visitantes = sum(1 for p in partidos_finalizados_qs if (p.goles_visitante or 0) > (p.goles_local or 0))
    empates = sum(1 for p in partidos_finalizados_qs if (p.goles_local or 0) == (p.goles_visitante or 0))

    porc_locales = round(victorias_locales / partidos_finalizados * 100) if partidos_finalizados > 0 else 0
    porc_empates = round(empates / partidos_finalizados * 100) if partidos_finalizados > 0 else 0
    porc_visitantes = round(victorias_visitantes / partidos_finalizados * 100) if partidos_finalizados > 0 else 0

    # Partidos destacados
    partido_record_goles = None
    mayor_goleada = None
    if partidos_finalizados > 0:
        partido_record_goles = max(partidos_finalizados_qs, key=lambda p: (p.goles_local or 0) + (p.goles_visitante or 0), default=None)
        mayor_goleada = max(partidos_finalizados_qs, key=lambda p: abs((p.goles_local or 0) - (p.goles_visitante or 0)), default=None)

    # 4. Disciplina, Fair Play y Finanzas
    eventos_torneo = EventoPartido.objects.filter(partido__torneo=torneo)
    total_amarillas = eventos_torneo.filter(tipo='amarilla').count()
    total_rojas = eventos_torneo.filter(tipo='roja').count()
    total_tarjetas = total_amarillas + total_rojas
    promedio_tarjetas = round(total_tarjetas / partidos_finalizados, 2) if partidos_finalizados > 0 else 0.0

    costo_amarilla = float(torneo.costo_amarilla or 0)
    costo_roja = float(torneo.costo_roja or 0)
    monto_multas_generadas = (total_amarillas * costo_amarilla) + (total_rojas * costo_roja)

    multas_qs = MultaTarjeta.objects.filter(partido__torneo=torneo)
    multas_pagadas_monto = float(multas_qs.filter(estado='pagado').aggregate(s=Sum('monto'))['s'] or 0)
    multas_pendientes_monto = float(multas_qs.filter(estado='pendiente').aggregate(s=Sum('monto'))['s'] or 0)
    if multas_pagadas_monto == 0 and multas_pendientes_monto == 0 and monto_multas_generadas > 0:
        multas_pendientes_monto = monto_multas_generadas

    # 5. Tablas de Posiciones según Tipo de Torneo
    tablas_grupos = []
    tabla_liga = []
    formato_visual_posiciones = 'liga'  # 'liga' o 'grupos'

    def _normalizar_filas_tabla(filas_raw):
        filas_norm = []
        for item in filas_raw:
            eq_obj = item.get('equipo')
            nombre_eq = item.get('equipo_nombre') or item.get('nombre')
            if not nombre_eq and eq_obj:
                nombre_eq = getattr(eq_obj, 'nombre', 'Club')
            if not nombre_eq:
                nombre_eq = 'Club'

            logo_url = item.get('equipo_logo')
            if not logo_url:
                if eq_obj and getattr(eq_obj, 'logo', None):
                    try:
                        logo_url = eq_obj.logo.url
                    except Exception:
                        logo_url = None
                elif item.get('logo'):
                    try:
                        logo_url = item['logo'].url
                    except Exception:
                        logo_url = None

            pj = item.get('PJ', item.get('pj', 0))
            pg = item.get('PG', item.get('pg', 0))
            pe = item.get('PE', item.get('pe', 0))
            pp = item.get('PP', item.get('pp', 0))
            gf = item.get('GF', item.get('gf', 0))
            gc = item.get('GC', item.get('gc', 0))
            gd = item.get('DG', item.get('gd', gf - gc))
            pts = item.get('PTS', item.get('pts', 0))

            item['nombre'] = nombre_eq
            item['equipo_nombre'] = nombre_eq
            item['equipo_logo'] = logo_url
            item['pj'] = pj
            item['PJ'] = pj
            item['pg'] = pg
            item['PG'] = pg
            item['pe'] = pe
            item['PE'] = pe
            item['pp'] = pp
            item['PP'] = pp
            item['gf'] = gf
            item['GF'] = gf
            item['gc'] = gc
            item['GC'] = gc
            item['gd'] = gd
            item['DG'] = gd
            item['pts'] = pts
            item['PTS'] = pts
            filas_norm.append(item)
        return filas_norm

    if torneo.tipo == 'personalizado':
        formato_visual_posiciones = 'grupos'
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        grupos_pers = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden', 'id')
        for g in grupos_pers:
            res = calcular_posiciones_grupo(g, torneo, org)
            tablas_grupos.append({
                'grupo_id': g.id,
                'grupo_nombre': g.nombre,
                'sector': g.sector,
                'cupos': g.cupos_clasificacion,
                'tabla': _normalizar_filas_tabla(res.get('tabla', [])),
                'advertencia': res.get('advertencia_cupos'),
            })
    elif torneo.tipo == 'torneo':
        # Torneo con fase de grupos estándar
        formato_visual_posiciones = 'grupos'
        grupos_pers = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden', 'id')
        if grupos_pers.exists():
            from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
            for g in grupos_pers:
                res = calcular_posiciones_grupo(g, torneo, org)
                tablas_grupos.append({
                    'grupo_id': g.id,
                    'grupo_nombre': g.nombre,
                    'sector': g.sector,
                    'cupos': g.cupos_clasificacion,
                    'tabla': _normalizar_filas_tabla(res.get('tabla', [])),
                })
        else:
            # Derivar grupos de partidos con fase 'grupos'
            partidos_grupos = [p for p in partidos_qs if p.fase == 'grupos']
            if partidos_grupos:
                grupos_dict = {}
                for p in partidos_grupos:
                    g_name = p.grupo or "Grupo A"
                    grupos_dict.setdefault(g_name, set()).add(p.equipo_local)
                    grupos_dict.setdefault(g_name, set()).add(p.equipo_visitante)

                for g_name, eq_set in sorted(grupos_dict.items()):
                    grupo_tabla = []
                    for eq in eq_set:
                        if not eq:
                            continue
                        p_jugados = [
                            p for p in partidos_finalizados_qs 
                            if p.fase == 'grupos' and (p.grupo == g_name or not p.grupo) and (p.equipo_local_id == eq.id or p.equipo_visitante_id == eq.id)
                        ]
                        pj = len(p_jugados)
                        pg = pe = pp = gf = gc = 0
                        for p in p_jugados:
                            gl = p.goles_local or 0
                            gv = p.goles_visitante or 0
                            if p.equipo_local_id == eq.id:
                                gf += gl; gc += gv
                                if gl > gv: pg += 1
                                elif gl == gv: pe += 1
                                else: pp += 1
                            else:
                                gf += gv; gc += gl
                                if gv > gl: pg += 1
                                elif gl == gv: pe += 1
                                else: pp += 1
                        pts = (pg * torneo.puntos_victoria) + (pe * torneo.puntos_empate) + (pp * torneo.puntos_derrota)
                        gd = gf - gc
                        grupo_tabla.append({
                            'equipo': eq,
                            'equipo_id': eq.id,
                            'equipo_nombre': eq.nombre,
                            'nombre': eq.nombre,
                            'equipo_logo': eq.logo.url if eq.logo else None,
                            'pj': pj, 'pg': pg, 'pe': pe, 'pp': pp,
                            'gf': gf, 'gc': gc, 'gd': gd, 'pts': pts
                        })
                    grupo_tabla.sort(key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
                    cupos = torneo.clasificados_por_grupo or 2
                    for idx, item in enumerate(grupo_tabla, start=1):
                        item['posicion'] = idx
                        item['es_clasificado_provisional'] = (idx <= cupos)
                    tablas_grupos.append({
                        'grupo_id': g_name,
                        'grupo_nombre': g_name,
                        'cupos': cupos,
                        'tabla': _normalizar_filas_tabla(grupo_tabla)
                    })
            else:
                formato_visual_posiciones = 'liga'

    if formato_visual_posiciones == 'liga':
        # Construir tabla general unificada
        for eq in equipos_qs:
            p_jugados = [
                p for p in partidos_finalizados_qs 
                if (p.equipo_local_id == eq.id or p.equipo_visitante_id == eq.id)
            ]
            pj = len(p_jugados)
            pg = pe = pp = gf = gc = 0
            forma = []
            p_jugados_sorted = sorted(p_jugados, key=lambda p: (p.jornada or 0, p.fecha_hora or timezone.now()))
            for p in p_jugados_sorted[-5:]:
                gl = p.goles_local or 0
                gv = p.goles_visitante or 0
                if p.equipo_local_id == eq.id:
                    if gl > gv: forma.append('G')
                    elif gl == gv: forma.append('E')
                    else: forma.append('P')
                else:
                    if gv > gl: forma.append('G')
                    elif gl == gv: forma.append('E')
                    else: forma.append('P')

            for p in p_jugados:
                gl = p.goles_local or 0
                gv = p.goles_visitante or 0
                if p.equipo_local_id == eq.id:
                    gf += gl; gc += gv
                    if gl > gv: pg += 1
                    elif gl == gv: pe += 1
                    else: pp += 1
                else:
                    gf += gv; gc += gl
                    if gv > gl: pg += 1
                    elif gl == gv: pe += 1
                    else: pp += 1
            pts = (pg * torneo.puntos_victoria) + (pe * torneo.puntos_empate) + (pp * torneo.puntos_derrota)
            gd = gf - gc
            tabla_liga.append({
                'equipo': eq,
                'equipo_id': eq.id,
                'equipo_nombre': eq.nombre,
                'nombre': eq.nombre,
                'equipo_logo': eq.logo.url if eq.logo else None,
                'pj': pj, 'pg': pg, 'pe': pe, 'pp': pp,
                'gf': gf, 'gc': gc, 'gd': gd, 'pts': pts,
                'forma': forma
            })
        tabla_liga.sort(key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
        for idx, item in enumerate(tabla_liga, start=1):
            item['posicion'] = idx
        tabla_liga = _normalizar_filas_tabla(tabla_liga)

    # 6. Cuadro de Honor / Superlativos Colectivos
    equipos_analisis = []
    if formato_visual_posiciones == 'liga':
        equipos_analisis = tabla_liga
    else:
        for tg in tablas_grupos:
            equipos_analisis.extend(tg.get('tabla', []))

    mejor_ataque = None
    mejor_defensa = None
    equipo_puntero = None
    con_partidos = []
    if equipos_analisis:
        # Mejor ataque
        con_goles = [e for e in equipos_analisis if (e.get('gf') or 0) > 0]
        if con_goles:
            mejor_ataque = max(con_goles, key=lambda x: x.get('gf', 0))

        # Mejor defensa con al menos 1 partido
        con_partidos = [e for e in equipos_analisis if (e.get('pj') or 0) > 0]
        if con_partidos:
            mejor_defensa = min(con_partidos, key=lambda x: x.get('gc', 999))
            equipo_puntero = max(con_partidos, key=lambda x: (x.get('pts', 0), x.get('gd', 0)))

    # Fair Play: tarjetas acumuladas por equipo
    tarjetas_por_equipo_dict = {}
    for eq in equipos_qs:
        tarjetas_por_equipo_dict[eq.id] = {
            'amarillas': 0,
            'rojas': 0,
            'puntos': 0,
            'equipo_nombre': eq.nombre,
            'equipo_logo': eq.logo.url if eq.logo else None
        }

    for ev in eventos_torneo.filter(tipo__in=['amarilla', 'roja']):
        if ev.equipo_id:
            if ev.equipo_id not in tarjetas_por_equipo_dict:
                tarjetas_por_equipo_dict[ev.equipo_id] = {
                    'amarillas': 0, 'rojas': 0, 'puntos': 0,
                    'equipo_nombre': ev.equipo.nombre if ev.equipo else 'Club',
                    'equipo_logo': ev.equipo.logo.url if ev.equipo and ev.equipo.logo else None
                }
            curr = tarjetas_por_equipo_dict[ev.equipo_id]
            if ev.tipo == 'amarilla':
                curr['amarillas'] += 1
                curr['puntos'] += 1
            else:
                curr['rojas'] += 1
                curr['puntos'] += 3

    equipo_fairplay = None
    if con_partidos:
        equipos_con_pj_ids = {e.get('equipo_id') for e in con_partidos if e.get('equipo_id')}
        candidatos_fairplay = [v for k, v in tarjetas_por_equipo_dict.items() if k in equipos_con_pj_ids]
        if candidatos_fairplay:
            equipo_fairplay = min(candidatos_fairplay, key=lambda x: x['puntos'])
    elif tarjetas_por_equipo_dict:
        equipo_fairplay = min(tarjetas_por_equipo_dict.values(), key=lambda x: x['puntos'])

    # 7. Líderes Individuales (Rankings)
    def get_ranking_eventos(tipo_evento, limit=6):
        events = EventoPartido.objects.filter(
            partido__torneo=torneo, tipo=tipo_evento, jugador__isnull=False
        ).values(
            'jugador__id', 'jugador__first_name', 'jugador__last_name',
            'equipo__id', 'equipo__nombre', 'equipo__logo'
        ).annotate(total=Count('id')).order_by('-total')[:limit]

        ranking = []
        for evt in events:
            ficha = FichaJugador.objects.filter(
                user_id=evt['jugador__id'], equipo_id=evt['equipo__id'], torneo=torneo
            ).first() or FichaJugador.objects.filter(
                user_id=evt['jugador__id'], equipo_id=evt['equipo__id']
            ).order_by('-id').first() or FichaJugador.objects.filter(
                user_id=evt['jugador__id']
            ).order_by('-id').first()

            ranking.append({
                'jugador_id': evt['jugador__id'],
                'nombre': f"{evt['jugador__first_name']} {evt['jugador__last_name']}".strip() or "Jugador",
                'equipo_id': evt['equipo__id'],
                'equipo_nombre': evt['equipo__nombre'],
                'equipo_logo': ('/media/' + evt['equipo__logo']) if evt['equipo__logo'] else None,
                'numero_camiseta': ficha.numero_camiseta if ficha and ficha.numero_camiseta else None,
                'foto_url': ficha.foto.url if ficha and ficha.foto else None,
                'total': evt['total']
            })
        return ranking

    top_goleadores = get_ranking_eventos('gol', limit=6)
    top_asistidores = get_ranking_eventos('asistencia', limit=6)
    top_amarillas = get_ranking_eventos('amarilla', limit=6)
    top_rojas = get_ranking_eventos('roja', limit=6)

    # 8. Agenda de Partidos (Próximos y Recientes)
    proximos_partidos = [p for p in partidos_qs if p.estado == 'programado'][:6]
    ultimos_resultados = sorted(partidos_finalizados_qs, key=lambda p: (p.fecha_hora or timezone.now(), p.id), reverse=True)[:6]

    # 9. Estadios y Sedes
    estadios_stats = Partido.objects.filter(torneo=torneo).exclude(estadio='').values(
        'estadio'
    ).annotate(
        total=Count('id'),
        jugados=Count('id', filter=Q(estado='finalizado'))
    ).order_by('-total')[:5]

    # 10. Cuadro de Honor / Campeón y Llaves
    resultado_final = ResultadoFinalTorneo.objects.filter(torneo=torneo).select_related('campeon', 'subcampeon', 'tercer_lugar', 'cuarto_lugar').first()
    llaves_eliminatorias = LlaveEliminatoria.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'ganador').order_by('fase', 'numero_llave')

    # URL pública y WhatsApp
    base_public_url = request.build_absolute_uri(reverse('vista_publica_torneo', kwargs={'public_uuid': torneo.public_uuid})) if hasattr(torneo, 'public_uuid') and torneo.public_uuid else None

    context = {
        'torneo': torneo,
        'es_gestor': es_gestor,
        'base_public_url': base_public_url,
        
        # Estado
        'estado_label': estado_label,
        'estado_badge': estado_badge,
        'estado_icon': estado_icon,
        
        # Avance & Totales
        'total_equipos': total_equipos,
        'total_jugadores': total_jugadores,
        'jugadores_habilitados': jugadores_habilitados,
        'jugadores_pendientes': jugadores_pendientes,
        'jugadores_con_firma': jugadores_con_firma,
        'promedio_jugadores_equipo': promedio_jugadores_equipo,
        'total_dts': total_dts,
        
        'total_partidos': total_partidos,
        'partidos_finalizados': partidos_finalizados,
        'partidos_en_curso': partidos_en_curso,
        'partidos_programados': partidos_programados,
        'partidos_anulados': partidos_anulados,
        'porcentaje_avance': porcentaje_avance,
        
        # Goles
        'total_goles': total_goles,
        'promedio_goles': promedio_goles,
        'goles_locales': goles_locales,
        'goles_visitantes': goles_visitantes,
        'victorias_locales': victorias_locales,
        'victorias_visitantes': victorias_visitantes,
        'empates': empates,
        'porc_locales': porc_locales,
        'porc_empates': porc_empates,
        'porc_visitantes': porc_visitantes,
        'partido_record_goles': partido_record_goles,
        'mayor_goleada': mayor_goleada,
        
        # Disciplina y Multas
        'total_amarillas': total_amarillas,
        'total_rojas': total_rojas,
        'total_tarjetas': total_tarjetas,
        'promedio_tarjetas': promedio_tarjetas,
        'monto_multas_generadas': monto_multas_generadas,
        'multas_pagadas_monto': multas_pagadas_monto,
        'multas_pendientes_monto': multas_pendientes_monto,
        
        # Posiciones
        'formato_visual_posiciones': formato_visual_posiciones,
        'tablas_grupos': tablas_grupos,
        'tabla_liga': tabla_liga,
        
        # Superlativos
        'mejor_ataque': mejor_ataque,
        'mejor_defensa': mejor_defensa,
        'equipo_puntero': equipo_puntero,
        'equipo_fairplay': equipo_fairplay,
        
        # Líderes
        'top_goleadores': top_goleadores,
        'top_asistidores': top_asistidores,
        'top_amarillas': top_amarillas,
        'top_rojas': top_rojas,
        
        # Agenda
        'proximos_partidos': proximos_partidos,
        'ultimos_resultados': ultimos_resultados,
        'estadios_stats': estadios_stats,
        
        # Cuadro de honor
        'resultado_final': resultado_final,
        'llaves_eliminatorias': llaves_eliminatorias,
    }
    return render(request, 'matches/dashboard_torneo.html', context)
