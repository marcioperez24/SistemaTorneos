import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.utils import timezone

from matches.models import Torneo, GrupoTorneo, Partido, BitacoraTorneo, Estadio
from teams.models import Equipo
from django.contrib.auth import get_user_model
from matches.services.fixture_personalizado import (
    calcular_vista_previa_fixture,
    guardar_fixture_personalizado,
    eliminar_fixture_personalizado,
    generar_fixture_incremental_equipos_nuevos
)

User = get_user_model()


def _verificar_permiso_gestion(request):
    """Auxiliar para verificar permisos de superadmin o comisión."""
    return request.user.role in ['superadmin', 'comision']


@login_required
def configurar_generar_fixture(request, torneo_id):
    """
    Vista de configuración y vista previa para la generación del fixture personalizado.
    Muestra los parámetros de calendario, vistas previas por grupo y advertencias de conflicto.
    """
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para generar el fixture del torneo.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupos_activos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden', 'id')
    if not grupos_activos.exists():
        messages.error(request, "No puedes generar un fixture en un torneo sin grupos activos.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    # Parámetros del formulario (GET o POST)
    fecha_inicio_str = request.GET.get('fecha_inicio') or request.POST.get('fecha_inicio')
    try:
        fecha_inicio = datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else datetime.date.today()
    except ValueError:
        fecha_inicio = datetime.date.today()

    dias_semana = request.GET.getlist('dias_semana') or request.POST.getlist('dias_semana')
    if not dias_semana:
        dias_semana = [5, 6]  # Sábado y Domingo
    else:
        dias_semana = [int(x) for x in dias_semana]

    horas_raw = request.GET.get('horas') or request.POST.get('horas') or '08:00,10:00,12:00,14:00'
    horas_lista = [h.strip() for h in horas_raw.split(',') if h.strip()]

    estadio = request.GET.get('estadio') or request.POST.get('estadio') or 'Estadio Principal'
    asignar_arbitro = request.GET.get('asignar_arbitro') == 'on' or request.POST.get('asignar_arbitro') == 'on'
    asignar_vocal = request.GET.get('asignar_vocal') == 'on' or request.POST.get('asignar_vocal') == 'on'
    grupo_sel_id = request.GET.get('grupo_id') or request.POST.get('grupo_id')
    grupos_ids = [int(grupo_sel_id)] if grupo_sel_id else []

    config_params = {
        'fecha_inicio': fecha_inicio,
        'dias_semana': dias_semana,
        'horas': horas_lista,
        'estadio': estadio,
        'grupos_ids': grupos_ids,
        'asignar_arbitro': asignar_arbitro,
        'asignar_vocal': asignar_vocal
    }

    # Calcular vista previa
    vista_previa_data = calcular_vista_previa_fixture(torneo, request.organizacion, config_params)

    # Si es una confirmación de guardado vía POST
    if request.method == 'POST' and request.POST.get('confirmar_guardar') == '1':
        forzar_reinicio = request.POST.get('forzar_reinicio') == '1'
        try:
            partidos_guardados = guardar_fixture_personalizado(
                torneo=torneo,
                organizacion=request.organizacion,
                usuario=request.user,
                vista_previa_data=vista_previa_data,
                forzar_reinicio=forzar_reinicio
            )
            messages.success(request, f"Se generó y guardó exitosamente el fixture con {len(partidos_guardados)} partidos.")
            return redirect('ver_fixture_personalizado', torneo_id=torneo.id)
        except ValidationError as ve:
            messages.error(request, str(ve.message if hasattr(ve, 'message') else ve))
        except Exception as e:
            messages.error(request, f"Error al guardar el fixture: {str(e)}")

    context = {
        'torneo': torneo,
        'grupos_activos': grupos_activos,
        'vista_previa': vista_previa_data,
        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
        'dias_semana': dias_semana,
        'horas_str': horas_raw,
        'estadio': estadio,
        'asignar_arbitro': asignar_arbitro,
        'asignar_vocal': asignar_vocal,
        'grupo_sel_id': int(grupo_sel_id) if grupo_sel_id else None,
        'estadios': Estadio.objects.filter(organizacion=torneo.organizacion, activo=True).order_by('nombre'),
    }
    return render(request, 'matches/configurar_generar_fixture.html', context)


@login_required
def ver_fixture_personalizado(request, torneo_id):
    """
    Muestra la cartelera y calendario del fixture para el torneo personalizado,
    agrupado por grupo y jornada con filtros interactivos, descansos y alertas de equipos incompletos.
    """
    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden', 'id')
    partidos_qs = Partido.objects.filter(torneo=torneo, organizacion=request.organizacion).select_related(
        'equipo_local', 'equipo_visitante', 'grupo_personalizado', 'arbitro', 'vocal'
    ).order_by('jornada', 'fecha_hora')

    # Filtros
    grupo_id = request.GET.get('grupo_id')
    jornada = request.GET.get('jornada')
    equipo_id = request.GET.get('equipo_id')
    estado = request.GET.get('estado')

    if grupo_id:
        partidos_qs = partidos_qs.filter(grupo_personalizado_id=grupo_id)
    if jornada:
        partidos_qs = partidos_qs.filter(jornada=jornada)
    if equipo_id:
        partidos_qs = partidos_qs.filter(models.Q(equipo_local_id=equipo_id) | models.Q(equipo_visitante_id=equipo_id))
    if estado:
        partidos_qs = partidos_qs.filter(estado=estado)

    # Construir fixture_agrupado asegurando que todos los grupos (o el filtrado) aparezcan
    fixture_agrupado = {}
    grupos_mostrar = grupos.filter(id=grupo_id) if grupo_id else grupos

    for g in grupos_mostrar:
        fixture_agrupado[g.nombre] = {
            'grupo_obj': g,
            'jornadas': {},
            'jornadas_lista': [],
            'equipos_asignados': [],
            'equipos_incompletos': [],
            'total_partidos_grupo': 0
        }

    for p in partidos_qs:
        g_nombre = p.grupo_personalizado.nombre if p.grupo_personalizado else (p.grupo or "General")
        if g_nombre not in fixture_agrupado:
            fixture_agrupado[g_nombre] = {
                'grupo_obj': p.grupo_personalizado,
                'jornadas': {},
                'jornadas_lista': [],
                'equipos_asignados': [],
                'equipos_incompletos': [],
                'total_partidos_grupo': 0
            }

        j_num = p.jornada or 1
        if j_num not in fixture_agrupado[g_nombre]['jornadas']:
            fixture_agrupado[g_nombre]['jornadas'][j_num] = []

        fixture_agrupado[g_nombre]['jornadas'][j_num].append(p)
        fixture_agrupado[g_nombre]['total_partidos_grupo'] += 1

    # Calcular equipos asignados, descansos por jornada y equipos sin fixture
    total_equipos_incompletos_torneo = 0
    for g_nombre, g_info in fixture_agrupado.items():
        g_obj = g_info['grupo_obj']
        if not g_obj:
            continue

        equipos_del_grupo = [a.equipo for a in g_obj.equipos_asignados.select_related('equipo')]
        g_info['equipos_asignados'] = equipos_del_grupo

        partidos_del_grupo = Partido.objects.filter(torneo=torneo, grupo_personalizado=g_obj)
        conteos = {}
        for eq in equipos_del_grupo:
            c = partidos_del_grupo.filter(models.Q(equipo_local=eq) | models.Q(equipo_visitante=eq)).count()
            conteos[eq.id] = {'equipo': eq, 'count': c}

        max_p = max((v['count'] for v in conteos.values()), default=0)
        incompletos = []
        if max_p > 0:
            for v in conteos.values():
                if v['count'] < max_p:
                    incompletos.append({'equipo': v['equipo'], 'partidos_count': v['count'], 'esperados': max_p})
        elif len(equipos_del_grupo) >= 2 and partidos_del_grupo.count() == 0:
            for v in conteos.values():
                incompletos.append({'equipo': v['equipo'], 'partidos_count': 0, 'esperados': len(equipos_del_grupo) - 1})

        g_info['equipos_incompletos'] = incompletos
        total_equipos_incompletos_torneo += len(incompletos)

        # Construir jornadas_lista ordenada con descansos
        jornadas_lista = []
        for j_num in sorted(g_info['jornadas'].keys()):
            partidos_j = g_info['jornadas'][j_num]
            equipos_jugando = set()
            for p in partidos_j:
                if p.equipo_local_id:
                    equipos_jugando.add(p.equipo_local_id)
                if p.equipo_visitante_id:
                    equipos_jugando.add(p.equipo_visitante_id)

            descansan = [eq for eq in equipos_del_grupo if eq.id not in equipos_jugando]
            jornadas_lista.append({
                'numero': j_num,
                'partidos': partidos_j,
                'descansan': descansan
            })

        g_info['jornadas_lista'] = jornadas_lista

    # Contadores generales de partidos
    todos_partidos = Partido.objects.filter(torneo=torneo, organizacion=request.organizacion)
    total_partidos = todos_partidos.count()
    partidos_programados = todos_partidos.filter(estado='programado').count()
    partidos_en_juego = todos_partidos.filter(estado='en_juego').count()
    partidos_finalizados = todos_partidos.filter(estado='finalizado').count()

    equipos_torneo = torneo.equipos.all().order_by('nombre')
    arbitros = User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct()
    vocales = User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct()

    grupo_id_val = int(grupo_id) if grupo_id else None
    grupo_sel_obj = grupos.filter(id=grupo_id_val).first() if grupo_id_val else None

    context = {
        'torneo': torneo,
        'grupos': grupos,
        'fixture_agrupado': fixture_agrupado,
        'total_partidos': total_partidos,
        'partidos_programados': partidos_programados,
        'partidos_en_juego': partidos_en_juego,
        'partidos_finalizados': partidos_finalizados,
        'total_equipos_incompletos_torneo': total_equipos_incompletos_torneo,
        'equipos_torneo': equipos_torneo,
        'arbitros': arbitros,
        'vocales': vocales,
        'estadios': Estadio.objects.filter(organizacion=torneo.organizacion, activo=True).order_by('nombre'),
        'grupo_id_sel': grupo_id_val,
        'grupo_sel_obj': grupo_sel_obj,
        'jornada_sel': jornada,
        'equipo_id_sel': int(equipo_id) if equipo_id else None,
        'estado_sel': estado,
    }
    return render(request, 'matches/fixture_personalizado.html', context)


@login_required
@require_POST
def borrar_fixture_personalizado(request, torneo_id):
    """
    Elimina los partidos del fixture para un grupo o para todo el torneo.
    Soporta eliminar solo pendientes (programados) o reinicio total completo.
    """
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para eliminar fixtures.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    grupo_id = request.POST.get('grupo_id')
    modo = request.POST.get('modo', 'solo_programados')

    try:
        total = eliminar_fixture_personalizado(
            torneo=torneo,
            organizacion=request.organizacion,
            usuario=request.user,
            grupo_id=int(grupo_id) if grupo_id else None,
            modo=modo
        )
        if modo == 'solo_programados':
            messages.success(request, f"Se eliminaron {total} partidos programados (pendientes). Los resultados y partidos finalizados se mantuvieron intactos.")
        else:
            messages.success(request, f"Reinicio total completado: se eliminaron {total} partidos. Ahora puedes generar un nuevo fixture con todos los equipos.")
    except Exception as e:
        messages.error(request, f"Error al eliminar fixture: {str(e)}")

    return redirect('ver_fixture_personalizado', torneo_id=torneo.id)


@login_required
@require_POST
def generar_fixture_equipos_nuevos(request, torneo_id):
    """
    Genera enfrentamientos únicamente para equipos nuevos incorporados a los grupos,
    sin borrar ni alterar ningún partido ya jugado o programado.
    """
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para generar fixtures.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    grupo_id = request.POST.get('grupo_id')

    try:
        total, resumen = generar_fixture_incremental_equipos_nuevos(
            torneo=torneo,
            organizacion=request.organizacion,
            usuario=request.user,
            grupo_id=int(grupo_id) if grupo_id else None
        )
        if total > 0:
            detalles = ", ".join([f"{r['grupo']}: +{r['partidos_nuevos']} partidos" for r in resumen if r['partidos_nuevos'] > 0])
            messages.success(request, f"¡Éxito! Se generaron {total} partidos nuevos para los equipos incorporados ({detalles}). Todos los partidos anteriores se conservaron.")
        else:
            messages.info(request, "Todos los equipos de este grupo ya tienen su fixture completo. No hay partidos faltantes por programar.")
    except Exception as e:
        messages.error(request, f"Error al generar fixture para equipos nuevos: {str(e)}")

    return redirect('ver_fixture_personalizado', torneo_id=torneo.id)


@login_required
@require_POST
def reprogramar_partido_personalizado(request, torneo_id, partido_id):
    """
    Edita la fecha, hora, estadio, árbitro, vocal o equipos de un partido.
    Conserva intactos el ID, eventos, firmas y resultados.
    """
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para modificar encuentros.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    partido = get_object_or_404(Partido, id=partido_id, torneo=torneo, organizacion=request.organizacion)

    nueva_fecha_str = request.POST.get('fecha')
    nueva_hora_str = request.POST.get('hora')
    nuevo_estadio = request.POST.get('estadio')
    nuevo_arbitro_id = request.POST.get('arbitro_id')
    nuevo_vocal_id = request.POST.get('vocal_id')
    motivo = request.POST.get('motivo', 'Reprogramación administrativa')

    if not nueva_fecha_str or not nueva_hora_str:
        messages.error(request, "Debes proporcionar una fecha y hora válidas.")
        return redirect('ver_fixture_personalizado', torneo_id=torneo.id)

    try:
        dt_str = f"{nueva_fecha_str} {nueva_hora_str}"
        nueva_dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
        if timezone.is_naive(nueva_dt):
            nueva_dt = timezone.make_aware(nueva_dt, timezone.get_current_timezone())
    except ValueError:
        messages.error(request, "El formato de fecha u hora es inválido.")
        return redirect('ver_fixture_personalizado', torneo_id=torneo.id)

    # Validar que los equipos no tengan otro partido simultáneo (excluyendo este partido)
    conflicto_local = Partido.objects.filter(
        organizacion=request.organizacion,
        fecha_hora=nueva_dt
    ).exclude(id=partido.id).filter(
        models.Q(equipo_local=partido.equipo_local) | models.Q(equipo_visitante=partido.equipo_local)
    ).exists()

    conflicto_visitante = Partido.objects.filter(
        organizacion=request.organizacion,
        fecha_hora=nueva_dt
    ).exclude(id=partido.id).filter(
        models.Q(equipo_local=partido.equipo_visitante) | models.Q(equipo_visitante=partido.equipo_visitante)
    ).exists()

    if conflicto_local:
        messages.error(request, f"El equipo '{partido.equipo_local.nombre}' ya posee otro partido a esa misma hora.")
        return redirect('ver_fixture_personalizado', torneo_id=torneo.id)

    if conflicto_visitante:
        messages.error(request, f"El equipo '{partido.equipo_visitante.nombre}' ya posee otro partido a esa misma hora.")
        return redirect('ver_fixture_personalizado', torneo_id=torneo.id)

    with transaction.atomic():
        fecha_anterior = partido.fecha_hora.strftime('%Y-%m-%d %H:%M') if partido.fecha_hora else "N/A"

        partido.fecha_hora = nueva_dt
        if nuevo_estadio:
            partido.estadio = nuevo_estadio.strip()
            org = getattr(request, 'organizacion', None) or torneo.organizacion
            partido.estadio_fk = Estadio.buscar_por_nombre(org, nuevo_estadio)
        if nuevo_arbitro_id:
            partido.arbitro_id = nuevo_arbitro_id
        if nuevo_vocal_id:
            partido.vocal_id = nuevo_vocal_id

        partido.save()

        # Auditoría
        BitacoraTorneo.objects.create(
            organizacion=request.organizacion,
            torneo=torneo,
            usuario=request.user,
            accion="Reprogramación de Partido",
            detalles=f"Partido #{partido.id} ({partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}) reprogramado. Motivo: {motivo}",
            valores_anteriores={'fecha_hora': fecha_anterior},
            valores_nuevos={'fecha_hora': nueva_dt.strftime('%Y-%m-%d %H:%M'), 'estadio': partido.estadio}
        )

        messages.success(request, f"Partido #{partido.id} reprogramado correctamente para el {nueva_dt.strftime('%d/%m/%Y %H:%M')}.")

    return redirect('ver_fixture_personalizado', torneo_id=torneo.id)


@login_required
def imprimir_fixture_personalizado(request, torneo_id):
    """
    Vista optimizada para impresión en PDF/papel del fixture personalizado por grupo.
    Soporta filtrado por grupo, jornada, equipo y estado.
    """
    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupo_id = request.GET.get('grupo_id')
    jornada = request.GET.get('jornada')
    equipo_id = request.GET.get('equipo_id')
    estado = request.GET.get('estado')

    partidos_qs = Partido.objects.filter(torneo=torneo, organizacion=request.organizacion).select_related(
        'equipo_local', 'equipo_visitante', 'grupo_personalizado', 'arbitro', 'vocal'
    ).order_by('jornada', 'fecha_hora')

    if grupo_id:
        partidos_qs = partidos_qs.filter(grupo_personalizado_id=grupo_id)
    if jornada:
        partidos_qs = partidos_qs.filter(jornada=jornada)
    if equipo_id:
        partidos_qs = partidos_qs.filter(
            models.Q(equipo_local_id=equipo_id) | models.Q(equipo_visitante_id=equipo_id)
        )
    if estado:
        partidos_qs = partidos_qs.filter(estado=estado)

    fixture_agrupado = {}
    for p in partidos_qs:
        g_nombre = p.grupo_personalizado.nombre if p.grupo_personalizado else (p.grupo or "General")
        if g_nombre not in fixture_agrupado:
            fixture_agrupado[g_nombre] = {'grupo_obj': p.grupo_personalizado, 'jornadas': {}, 'jornadas_lista': []}

        j_num = p.jornada or 1
        if j_num not in fixture_agrupado[g_nombre]['jornadas']:
            fixture_agrupado[g_nombre]['jornadas'][j_num] = []

        fixture_agrupado[g_nombre]['jornadas'][j_num].append(p)

    for g_nombre, g_info in fixture_agrupado.items():
        g_obj = g_info['grupo_obj']
        equipos_del_grupo = [a.equipo for a in g_obj.equipos_asignados.select_related('equipo')] if g_obj else []
        jornadas_lista = []
        for j_num in sorted(g_info['jornadas'].keys()):
            partidos_j = g_info['jornadas'][j_num]
            equipos_jugando = set()
            for p in partidos_j:
                if p.equipo_local_id:
                    equipos_jugando.add(p.equipo_local_id)
                if p.equipo_visitante_id:
                    equipos_jugando.add(p.equipo_visitante_id)
            descansan = [eq for eq in equipos_del_grupo if eq.id not in equipos_jugando]
            jornadas_lista.append({
                'numero': j_num,
                'partidos': partidos_j,
                'descansan': descansan
            })
        g_info['jornadas_lista'] = jornadas_lista

    context = {
        'torneo': torneo,
        'organizacion': request.organizacion,
        'fixture_agrupado': fixture_agrupado,
        'fecha_impresion': datetime.datetime.now(),
        'jornada_filtrada': jornada,
        'grupo_id_filtrado': grupo_id,
        'equipo_id_filtrado': equipo_id,
        'estado_filtrado': estado,
    }
    return render(request, 'matches/imprimir_fixture_personalizado.html', context)
