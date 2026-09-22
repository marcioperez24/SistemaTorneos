from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from matches.models import (
    Torneo, GrupoTorneo, Partido, EventoPartido,
    ClasificadoTorneo, LlaveEliminatoria, ResultadoFinalTorneo, BitacoraTorneo
)
from matches.services.panel_personalizado import (
    evaluar_estado_general_torneo, obtener_indicador_progreso,
    obtener_proxima_accion_recomendada, obtener_resumen_grupos_panel,
    obtener_agenda_operativa, obtener_alertas_administrativas,
    generar_excel_torneo_consolidado, generar_enlaces_whatsapp
)
from matches.services.estadisticas_personalizado import (
    calcular_posiciones_grupo, calcular_estadisticas_jugadores_grupo
)


@login_required
def centro_control_torneo_view(request, torneo_id):
    """
    Vista principal del Centro de Control del Torneo Personalizado por Grupos.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)

    if torneo.tipo != 'personalizado':
        return redirect('detalle_torneo', torneo_id=torneo.id)

    estado_general = evaluar_estado_general_torneo(torneo)
    pasos_progreso = obtener_indicador_progreso(torneo, estado_general)
    recomendacion = obtener_proxima_accion_recomendada(torneo, estado_general)
    resumen_grupos = obtener_resumen_grupos_panel(torneo)
    
    # Filtros para la agenda operativa
    filtros_agenda = {
        'periodo': request.GET.get('periodo'),
        'grupo_id': request.GET.get('grupo_id'),
        'fase': request.GET.get('fase'),
        'equipo_id': request.GET.get('equipo_id'),
    }
    agenda = obtener_agenda_operativa(torneo, filtros_agenda)
    alertas = obtener_alertas_administrativas(torneo)

    base_public_url = request.build_absolute_uri(reverse('vista_publica_torneo', kwargs={'public_uuid': torneo.public_uuid}))
    whatsapp_link = generar_enlaces_whatsapp(torneo, base_public_url)

    # Identificación de permisos de usuario
    user = request.user
    es_admin = user.is_superuser or getattr(user, 'role', '') in ['admin', 'comision', 'organizador']

    context = {
        'torneo': torneo,
        'estado_general': estado_general,
        'pasos_progreso': pasos_progreso,
        'recomendacion': recomendacion,
        'resumen_grupos': resumen_grupos,
        'agenda': agenda,
        'alertas': alertas,
        'base_public_url': base_public_url,
        'whatsapp_link': whatsapp_link,
        'es_admin': es_admin,
        'grupos_activos': GrupoTorneo.objects.filter(torneo=torneo, activo=True),
        'equipos_torneo': torneo.equipos.all(),
    }
    return render(request, 'matches/panel_torneo_personalizado.html', context)


@login_required
def historial_auditoria_view(request, torneo_id):
    """
    Vista de solo lectura del Historial de Auditoría (BitacoraTorneo).
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)

    qs = BitacoraTorneo.objects.filter(torneo=torneo).select_related('usuario').order_by('-fecha_hora')

    # Filtros
    accion = request.GET.get('accion')
    usuario_id = request.GET.get('usuario_id')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if accion:
        qs = qs.filter(accion=accion)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if fecha_inicio:
        qs = qs.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_hora__lte=fecha_fin)

    context = {
        'torneo': torneo,
        'bitacora_items': qs[:200],  # Limitar a los 200 registros más recientes
        'acciones_disponibles': BitacoraTorneo.objects.filter(torneo=torneo).values_list('accion', flat=True).distinct(),
    }
    return render(request, 'matches/historial_auditoria_torneo.html', context)


@login_required
def exportar_excel_consolidado_view(request, torneo_id):
    """
    Endpoint para descargar el informe consolidado en formato Excel (.xlsx).
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)
    content = generar_excel_torneo_consolidado(torneo)

    filename = f"Torneo_{torneo.id}_Reporte_Consolidado.xlsx"
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def imprimir_torneo_consolidado_view(request, torneo_id):
    """
    Vista de impresión general del torneo personalizado.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)

    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden')
    grupos_data = []
    for g in grupos:
        res_pos = calcular_posiciones_grupo(g, torneo, request.organizacion)
        pos = res_pos['tabla']
        partidos = Partido.objects.filter(torneo=torneo, grupo_personalizado=g).select_related('equipo_local', 'equipo_visitante').order_by('fecha_hora')
        grupos_data.append({
            'grupo': g,
            'posiciones': pos,
            'partidos': partidos
        })

    clasificados = ClasificadoTorneo.objects.filter(torneo=torneo).select_related('grupo', 'equipo')
    llaves = LlaveEliminatoria.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'ganador')
    resultado_final = ResultadoFinalTorneo.objects.filter(torneo=torneo).first()

    context = {
        'torneo': torneo,
        'grupos_data': grupos_data,
        'clasificados': clasificados,
        'llaves': llaves,
        'resultado_final': resultado_final,
        'fecha_impresion': timezone.now()
    }
    return render(request, 'matches/imprimir_torneo_consolidado.html', context)
