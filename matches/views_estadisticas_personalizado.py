from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify

from matches.models import Torneo, GrupoTorneo
from matches.services.estadisticas_personalizado import (
    calcular_posiciones_grupo,
    calcular_estadisticas_jugadores_grupo,
    calcular_resumen_grupo,
    obtener_partidos_recientes_y_proximos,
    calcular_resumen_torneo_general,
    generar_excel_estadisticas_torneo,
)


@login_required
def estadisticas_torneo_personalizado(request, torneo_id):
    """
    Vista principal para consultar la tabla de posiciones y estadísticas
    de un torneo personalizado por grupos.
    """
    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupos = list(GrupoTorneo.objects.filter(torneo=torneo).order_by('orden', 'id'))
    grupo_id_param = request.GET.get('grupo')

    grupo_seleccionado = None
    es_vista_todos = True

    if grupo_id_param and grupo_id_param != 'todos':
        try:
            grupo_id = int(grupo_id_param)
            grupo_seleccionado = get_object_or_404(
                GrupoTorneo,
                id=grupo_id,
                torneo=torneo,
                torneo__organizacion=request.organizacion
            )
            es_vista_todos = False
        except (ValueError, TypeError):
            grupo_seleccionado = None
            es_vista_todos = True

    context = {
        'torneo': torneo,
        'grupos': grupos,
        'grupo_seleccionado': grupo_seleccionado,
        'es_vista_todos': es_vista_todos,
    }

    if es_vista_todos:
        context['resumen_general'] = calcular_resumen_torneo_general(torneo, request.organizacion)
    else:
        pos_data = calcular_posiciones_grupo(grupo_seleccionado, torneo, request.organizacion)
        jug_data = calcular_estadisticas_jugadores_grupo(grupo_seleccionado, torneo, request.organizacion)
        res_info = calcular_resumen_grupo(grupo_seleccionado, torneo, request.organizacion)
        partidos_info = obtener_partidos_recientes_y_proximos(grupo_seleccionado, torneo, request.organizacion)

        context.update({
            'tabla': pos_data['tabla'],
            'cupos': pos_data['cupos'],
            'advertencia_cupos': pos_data['advertencia_cupos'],
            'goleadores': jug_data['goleadores'],
            'asistencias': jug_data['asistencias'],
            'amarillas': jug_data['amarillas'],
            'rojas': jug_data['rojas'],
            'resumen': res_info,
            'partidos_recientes': partidos_info['recientes'],
            'proximos_partidos': partidos_info['proximos'],
        })

    return render(request, 'matches/estadisticas_torneo_personalizado.html', context)


@login_required
def imprimir_estadisticas_personalizado(request, torneo_id):
    """
    Vista limpia optimizada para impresión (@media print) de tablas y estadísticas.
    """
    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupos = list(GrupoTorneo.objects.filter(torneo=torneo).order_by('orden', 'id'))
    grupo_id_param = request.GET.get('grupo')

    grupo_seleccionado = None
    if grupo_id_param and grupo_id_param != 'todos':
        try:
            grupo_id = int(grupo_id_param)
            grupo_seleccionado = get_object_or_404(
                GrupoTorneo,
                id=grupo_id,
                torneo=torneo,
                torneo__organizacion=request.organizacion
            )
        except (ValueError, TypeError):
            grupo_seleccionado = None

    tablas_grupos = []

    if grupo_seleccionado:
        pos_data = calcular_posiciones_grupo(grupo_seleccionado, torneo, request.organizacion)
        jug_data = calcular_estadisticas_jugadores_grupo(grupo_seleccionado, torneo, request.organizacion)
        res_info = calcular_resumen_grupo(grupo_seleccionado, torneo, request.organizacion)
        tablas_grupos.append({
            'grupo': grupo_seleccionado,
            'tabla': pos_data['tabla'],
            'cupos': pos_data['cupos'],
            'advertencia_cupos': pos_data['advertencia_cupos'],
            'resumen': res_info,
            'goleadores': jug_data['goleadores'][:5],
            'asistencias': jug_data['asistencias'][:5],
        })
    else:
        for g in grupos:
            pos_data = calcular_posiciones_grupo(g, torneo, request.organizacion)
            jug_data = calcular_estadisticas_jugadores_grupo(g, torneo, request.organizacion)
            res_info = calcular_resumen_grupo(g, torneo, request.organizacion)
            tablas_grupos.append({
                'grupo': g,
                'tabla': pos_data['tabla'],
                'cupos': pos_data['cupos'],
                'advertencia_cupos': pos_data['advertencia_cupos'],
                'resumen': res_info,
                'goleadores': jug_data['goleadores'][:5],
                'asistencias': jug_data['asistencias'][:5],
            })

    context = {
        'torneo': torneo,
        'organizacion': request.organizacion,
        'grupo_seleccionado': grupo_seleccionado,
        'tablas_grupos': tablas_grupos,
        'fecha_impresion': timezone.now(),
    }

    return render(request, 'matches/imprimir_estadisticas_personalizado.html', context)


@login_required
def exportar_excel_estadisticas_personalizado(request, torneo_id):
    """
    Genera y descarga el archivo de Excel (.xlsx) con la tabla de posiciones y estadísticas.
    """
    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupo_id_param = request.GET.get('grupo')
    grupo_id = None
    if grupo_id_param and grupo_id_param != 'todos':
        try:
            grupo_id = int(grupo_id_param)
            get_object_or_404(
                GrupoTorneo,
                id=grupo_id,
                torneo=torneo,
                torneo__organizacion=request.organizacion
            )
        except (ValueError, TypeError):
            grupo_id = None

    excel_bytes = generar_excel_estadisticas_torneo(torneo, request.organizacion, grupo_id=grupo_id)

    nombre_torneo_clean = slugify(torneo.nombre)
    fecha_str = timezone.now().strftime('%Y%m%d')
    filename = f"posiciones_{nombre_torneo_clean}_{fecha_str}.xlsx"

    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
