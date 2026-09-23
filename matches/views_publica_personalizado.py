from django.shortcuts import render, get_object_or_404
from django.http import Http404
from django.urls import reverse
from matches.models import (
    Torneo, GrupoTorneo, Partido, ClasificadoTorneo,
    LlaveEliminatoria, ResultadoFinalTorneo
)
from matches.services.estadisticas_personalizado import (
    calcular_posiciones_grupo, calcular_estadisticas_jugadores_grupo,
    calcular_posiciones_general, calcular_estadisticas_jugadores_general
)
import urllib.parse


def vista_publica_torneo_view(request, public_uuid):
    """
    Vista pública anónima y segura de cualquier torneo (Liga, Grupos o Personalizado).
    No requiere autenticación ni middleware de organización.
    """
    torneo = get_object_or_404(Torneo.objects.select_related('organizacion', 'categoria'), public_uuid=public_uuid)

    if not torneo.es_publico:
        return render(request, 'matches/vista_publica_no_disponible.html', {'torneo': torneo}, status=404)

    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden')
    grupos_data = []

    if grupos.exists():
        for g in grupos:
            res_pos = calcular_posiciones_grupo(g, torneo, torneo.organizacion)
            pos = res_pos['tabla']
            partidos = Partido.objects.filter(torneo=torneo, grupo_personalizado=g).select_related(
                'equipo_local', 'equipo_visitante'
            ).order_by('jornada', 'fecha_hora')

            # Estadísticas de jugadores por grupo
            stats_j = calcular_estadisticas_jugadores_grupo(g, torneo, torneo.organizacion)

            grupos_data.append({
                'grupo': g,
                'posiciones': pos,
                'partidos': partidos,
                'goleadores': stats_j['goleadores'][:10],
                'asistencias': stats_j['asistencias'][:10],
                'tarjetas': stats_j['amarillas'][:10],
            })
    else:
        # Torneo sin grupos (Ej. formato Liga o Eliminatoria pura)
        res_pos = calcular_posiciones_general(torneo, torneo.organizacion)
        pos = res_pos['tabla']
        partidos = Partido.objects.filter(torneo=torneo).select_related(
            'equipo_local', 'equipo_visitante'
        ).order_by('jornada', 'fecha_hora')

        stats_j = calcular_estadisticas_jugadores_general(torneo, torneo.organizacion)

        class GrupoFicticio:
            nombre = "Tabla General"
            sector = "Todos contra todos"
            cupos_clasificacion = 4

        grupos_data.append({
            'grupo': GrupoFicticio(),
            'posiciones': pos,
            'partidos': partidos,
            'goleadores': stats_j['goleadores'][:10],
            'asistencias': stats_j['asistencias'][:10],
            'tarjetas': stats_j['amarillas'][:10],
        })

    clasificados = ClasificadoTorneo.objects.filter(torneo=torneo).select_related('grupo', 'equipo')
    llaves = LlaveEliminatoria.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'ganador').order_by('fase', 'numero_llave')
    resultado_final = ResultadoFinalTorneo.objects.filter(torneo=torneo).first()

    base_public_url = request.build_absolute_uri()
    mensaje_wa = f"🏆 Sigue toda la información, fixture y posiciones de {torneo.nombre} ({torneo.organizacion.nombre}) aquí: {base_public_url}"
    whatsapp_link = f"https://api.whatsapp.com/send?text={urllib.parse.quote(mensaje_wa)}"

    context = {
        'torneo': torneo,
        'grupos_data': grupos_data,
        'clasificados': clasificados,
        'llaves': llaves,
        'resultado_final': resultado_final,
        'base_public_url': base_public_url,
        'whatsapp_link': whatsapp_link,
        'tab_activa': request.GET.get('tab', 'inicio')
    }
    return render(request, 'matches/vista_publica_torneo.html', context)
