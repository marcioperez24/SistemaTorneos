import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.utils import timezone

from matches.models import Torneo, GrupoTorneo, Partido, BitacoraTorneo
from teams.models import Equipo
from django.contrib.auth import get_user_model
from matches.services.fixture_personalizado import (
    calcular_vista_previa_fixture,
    guardar_fixture_personalizado
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
        try:
            partidos_guardados = guardar_fixture_personalizado(
                torneo=torneo,
                organizacion=request.organizacion,
                usuario=request.user,
                vista_previa_data=vista_previa_data
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
        'grupo_sel_id': int(grupo_sel_id) if grupo_sel_id else None
    }
    return render(request, 'matches/configurar_generar_fixture.html', context)


@login_required
def ver_fixture_personalizado(request, torneo_id):
    """
    Muestra la cartelera y calendario del fixture para el torneo personalizado,
    agrupado por grupo y jornada con filtros interactivos.
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

    # Agrupar partidos por Grupo -> Jornada
    fixture_agrupado = {}
    for p in partidos_qs:
        g_nombre = p.grupo_personalizado.nombre if p.grupo_personalizado else (p.grupo or "General")
        if g_nombre not in fixture_agrupado:
            fixture_agrupado[g_nombre] = {'grupo_obj': p.grupo_personalizado, 'jornadas': {}}

        j_num = p.jornada
        if j_num not in fixture_agrupado[g_nombre]['jornadas']:
            fixture_agrupado[g_nombre]['jornadas'][j_num] = []

        fixture_agrupado[g_nombre]['jornadas'][j_num].append(p)

    # Contadores generales de partidos
    todos_partidos = Partido.objects.filter(torneo=torneo, organizacion=request.organizacion)
    total_partidos = todos_partidos.count()
    partidos_programados = todos_partidos.filter(estado='programado').count()
    partidos_en_juego = todos_partidos.filter(estado='en_juego').count()
    partidos_finalizados = todos_partidos.filter(estado='finalizado').count()

    equipos_torneo = torneo.equipos.all().order_by('nombre')
    arbitros = User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct()
    vocales = User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct()

    context = {
        'torneo': torneo,
        'grupos': grupos,
        'fixture_agrupado': fixture_agrupado,
        'total_partidos': total_partidos,
        'partidos_programados': partidos_programados,
        'partidos_en_juego': partidos_en_juego,
        'partidos_finalizados': partidos_finalizados,
        'equipos_torneo': equipos_torneo,
        'arbitros': arbitros,
        'vocales': vocales,
        'grupo_id_sel': int(grupo_id) if grupo_id else None,
        'jornada_sel': jornada,
        'equipo_id_sel': int(equipo_id) if equipo_id else None,
        'estado_sel': estado,
    }
    return render(request, 'matches/fixture_personalizado.html', context)


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
            partido.estadio = nuevo_estadio
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
    """
    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupo_id = request.GET.get('grupo_id')
    jornada = request.GET.get('jornada')

    partidos_qs = Partido.objects.filter(torneo=torneo, organizacion=request.organizacion).select_related(
        'equipo_local', 'equipo_visitante', 'grupo_personalizado', 'arbitro', 'vocal'
    ).order_by('jornada', 'fecha_hora')

    if grupo_id:
        partidos_qs = partidos_qs.filter(grupo_personalizado_id=grupo_id)
    if jornada:
        partidos_qs = partidos_qs.filter(jornada=jornada)

    fixture_agrupado = {}
    for p in partidos_qs:
        g_nombre = p.grupo_personalizado.nombre if p.grupo_personalizado else (p.grupo or "General")
        if g_nombre not in fixture_agrupado:
            fixture_agrupado[g_nombre] = {'grupo_obj': p.grupo_personalizado, 'jornadas': {}}

        j_num = p.jornada
        if j_num not in fixture_agrupado[g_nombre]['jornadas']:
            fixture_agrupado[g_nombre]['jornadas'][j_num] = []

        fixture_agrupado[g_nombre]['jornadas'][j_num].append(p)

    context = {
        'torneo': torneo,
        'organizacion': request.organizacion,
        'fixture_agrupado': fixture_agrupado,
        'fecha_impresion': datetime.datetime.now()
    }
    return render(request, 'matches/imprimir_fixture_personalizado.html', context)
