from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify

from matches.models import (
    Torneo, GrupoTorneo, ClasificadoTorneo, LlaveEliminatoria, Partido, EquipoGrupoTorneo,
    ResultadoFinalTorneo
)
from matches.services.sorteo_personalizado import (
    verificar_estado_clasificacion_grupos,
    confirmar_clasificados_definitivos,
    resolver_empate_administrativo,
    reabrir_clasificacion_definitiva,
    generar_sorteo_eliminatorio,
    confirmar_y_crear_cuadro_eliminatorio
)
from matches.services.eliminatorias_personalizado import (
    evaluar_estado_llave,
    confirmar_ganador_llave,
    procesar_bye_llave,
    reabrir_llave_eliminatoria,
    programar_partidos_ronda_siguiente,
    generar_excel_cuadro_eliminatorio_completo
)
from teams.models import Equipo


@login_required
def confirmar_clasificados_view(request, torneo_id):
    """
    Pantalla de revisión y confirmación definitiva de clasificados de la fase de grupos.
    """
    torneo = get_object_or_404(
        Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado'
    )

    clasificados_existentes = ClasificadoTorneo.objects.filter(torneo=torneo, activo=True).select_related('equipo', 'grupo')
    ya_confirmado = clasificados_existentes.exists()

    estado_info = verificar_estado_clasificacion_grupos(torneo, request.organizacion)

    if request.method == 'POST':
        if request.user.role not in ['superadmin', 'comision']:
            messages.error(request, "No tienes permisos para confirmar los clasificados.")
            return redirect('confirmar_clasificados_view', torneo_id=torneo.id)

        confirmacion_excepcional = request.POST.get('confirmacion_excepcional') == '1'
        motivo = request.POST.get('motivo_excepcional', '')

        try:
            confirmar_clasificados_definitivos(
                torneo=torneo,
                organizacion=request.organizacion,
                usuario=request.user,
                confirmacion_excepcional=confirmacion_excepcional,
                motivo=motivo
            )
            messages.success(request, "¡Clasificados confirmados exitosamente! Ahora puedes configurar la fase eliminatoria.")
            return redirect('configurar_sorteo_eliminatorio_view', torneo_id=torneo.id)
        except Exception as e:
            messages.error(request, f"Error al confirmar clasificados: {str(e)}")
            return redirect('confirmar_clasificados_view', torneo_id=torneo.id)

    context = {
        'torneo': torneo,
        'ya_confirmado': ya_confirmado,
        'clasificados_existentes': clasificados_existentes,
        'estado_info': estado_info,
    }
    return render(request, 'matches/confirmar_clasificados_personalizado.html', context)


@login_required
def resolver_empate_view(request, torneo_id, grupo_id):
    """
    Acción para resolver administrativamente un empate en el límite de clasificación de un grupo.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    grupo = get_object_or_404(GrupoTorneo, id=grupo_id, torneo=torneo)

    if request.method == 'POST':
        equipo_ganador_id = request.POST.get('equipo_ganador_id')
        equipos_ids = request.POST.getlist('equipos_empatados_ids')
        motivo = request.POST.get('motivo_resolucion', 'sorteo_admin')
        observacion = request.POST.get('observacion', '')

        try:
            resolver_empate_administrativo(
                torneo=torneo,
                grupo=grupo,
                equipos_ids=equipos_ids,
                equipo_ganador_id=equipo_ganador_id,
                motivo=motivo,
                observacion=observacion,
                usuario=request.user,
                organizacion=request.organizacion
            )
            messages.success(request, f"Empate del Grupo {grupo.nombre} resuelto exitosamente.")
        except Exception as e:
            messages.error(request, f"Error al resolver empate: {str(e)}")

    return redirect('confirmar_clasificados_view', torneo_id=torneo.id)


@login_required
def reabrir_clasificacion_view(request, torneo_id):
    """
    Acción exclusiva para superadmin que permite reabrir la clasificación definitiva.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')

    if request.method == 'POST':
        motivo = request.POST.get('motivo_reapertura', '')
        try:
            reabrir_clasificacion_definitiva(torneo, request.organizacion, request.user, motivo)
            messages.success(request, "La fase de clasificación ha sido reabierta.")
        except Exception as e:
            messages.error(request, f"Error al reabrir clasificación: {str(e)}")

    return redirect('estadisticas_torneo_personalizado', torneo_id=torneo.id)


@login_required
def configurar_sorteo_eliminatorio_view(request, torneo_id):
    """
    Formulario de configuración del sorteo o asignación de cruces eliminatorios.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    clasificados = list(ClasificadoTorneo.objects.filter(torneo=torneo, activo=True).select_related('equipo', 'grupo'))

    if not clasificados:
        messages.warning(request, "Primero debes confirmar los clasificados del torneo.")
        return redirect('confirmar_clasificados_view', torneo_id=torneo.id)

    if request.method == 'POST':
        params = {
            'formato': request.POST.get('formato', 'partido_unico'),
            'evitar_mismo_grupo': request.POST.get('evitar_mismo_grupo') == '1',
            'evitar_mismo_sector': request.POST.get('evitar_mismo_sector') == '1',
            'sortear_localia': request.POST.get('sortear_localia') == '1',
            'semilla': request.POST.get('semilla', str(timezone.now().timestamp())),
            'fecha_inicial': request.POST.get('fecha_inicial', timezone.now().strftime('%Y-%m-%d')),
            'hora_inicial': request.POST.get('hora_inicial', '14:00'),
            'intervalo_dias': int(request.POST.get('intervalo_dias', 7)),
            'estadio': request.POST.get('estadio', 'Estadio Principal'),
        }

        try:
            preview = generar_sorteo_eliminatorio(torneo, request.organizacion, request.user, params)
            
            # Guardar en sesión datos serializables
            session_preview = {
                'fase_inicial': preview['fase_inicial'],
                'fase_display': preview['fase_display'],
                'formato': preview['formato'],
                'fecha_inicial': params['fecha_inicial'],
                'hora_inicial': params['hora_inicial'],
                'intervalo_dias': params['intervalo_dias'],
                'estadio': params['estadio'],
                'params': params,
                'llaves': [
                    {
                        'numero_llave': item['numero_llave'],
                        'fase': item['fase'],
                        'es_bye': item['es_bye'],
                        'local': {'id': item['local'].id, 'nombre': item['local'].equipo.nombre, 'grupo': item['local'].grupo.nombre, 'posicion': item['local'].posicion_grupo, 'bombo': item['local'].bombo} if item['local'] else None,
                        'visitante': {'id': item['visitante'].id, 'nombre': item['visitante'].equipo.nombre, 'grupo': item['visitante'].grupo.nombre, 'posicion': item['visitante'].posicion_grupo, 'bombo': item['visitante'].bombo} if item['visitante'] else None,
                    }
                    for item in preview['llaves']
                ]
            }
            request.session['preview_sorteo_data'] = session_preview
            return redirect('vista_previa_sorteo_view', torneo_id=torneo.id)
        except Exception as e:
            messages.error(request, f"Error al generar sorteo: {str(e)}")

    context = {
        'torneo': torneo,
        'clasificados': clasificados,
        'total_clasificados': len(clasificados),
    }
    return render(request, 'matches/configurar_sorteo_eliminatorio.html', context)


@login_required
def vista_previa_sorteo_view(request, torneo_id):
    """
    Muestra la previsualización del sorteo antes de crear partidos en la base de datos.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    preview_data = request.session.get('preview_sorteo_data')

    if not preview_data:
        messages.warning(request, "No existe una vista previa activa. Por favor configura el sorteo.")
        return redirect('configurar_sorteo_eliminatorio_view', torneo_id=torneo.id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'repetir':
            params = preview_data.get('params', {})
            params['semilla'] = str(timezone.now().timestamp())
            try:
                preview = generar_sorteo_eliminatorio(torneo, request.organizacion, request.user, params)
                preview_data['llaves'] = [
                    {
                        'numero_llave': item['numero_llave'],
                        'fase': item['fase'],
                        'es_bye': item['es_bye'],
                        'local': {'id': item['local'].id, 'nombre': item['local'].equipo.nombre, 'grupo': item['local'].grupo.nombre, 'posicion': item['local'].posicion_grupo, 'bombo': item['local'].bombo} if item['local'] else None,
                        'visitante': {'id': item['visitante'].id, 'nombre': item['visitante'].equipo.nombre, 'grupo': item['visitante'].grupo.nombre, 'posicion': item['visitante'].posicion_grupo, 'bombo': item['visitante'].bombo} if item['visitante'] else None,
                    }
                    for item in preview['llaves']
                ]
                request.session['preview_sorteo_data'] = preview_data
                messages.info(request, "Sorteo repetido con una nueva semilla aleatoria.")
            except Exception as e:
                messages.error(request, f"Error al repetir sorteo: {str(e)}")
            return redirect('vista_previa_sorteo_view', torneo_id=torneo.id)

    context = {
        'torneo': torneo,
        'preview': preview_data,
    }
    return render(request, 'matches/vista_previa_sorteo_eliminatorio.html', context)


@login_required
def confirmar_cuadro_view(request, torneo_id):
    """
    Confirma el cuadro eliminatorio e inserta las Llaves y Partidos en la base de datos.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    preview_data = request.session.get('preview_sorteo_data')

    if not preview_data and request.method != 'POST':
        messages.error(request, "Sin datos de previsualización.")
        return redirect('configurar_sorteo_eliminatorio_view', torneo_id=torneo.id)

    if request.method == 'POST':
        try:
            confirmar_y_crear_cuadro_eliminatorio(torneo, request.organizacion, request.user, preview_data)
            if 'preview_sorteo_data' in request.session:
                del request.session['preview_sorteo_data']
            messages.success(request, "¡Cuadro eliminatorio y partidos de primera ronda creados exitosamente!")
            return redirect('ver_cuadro_eliminatorio_view', torneo_id=torneo.id)
        except Exception as e:
            messages.error(request, f"Error al confirmar cuadro eliminatorio: {str(e)}")

    return redirect('vista_previa_sorteo_view', torneo_id=torneo.id)


@login_required
def ver_cuadro_eliminatorio_view(request, torneo_id):
    """
    Visualización responsive del bracket/cuadro eliminatorio del torneo personalizado.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')

    llaves = list(
        LlaveEliminatoria.objects.filter(torneo=torneo)
        .select_related('equipo_local', 'equipo_visitante', 'clasificado_local', 'clasificado_visitante', 'ganador')
        .order_by('fase', 'numero_llave')
    )

    partidos_eliminatorios = Partido.objects.filter(
        organizacion=request.organizacion,
        torneo=torneo,
        fase__in=['dieciseisavos', 'octavos', 'cuartos', 'semifinal', 'tercer_lugar', 'final']
    ).select_related('equipo_local', 'equipo_visitante').order_by('fecha_hora', 'id')

    # Agrupar partidos por pareja de equipos
    partidos_map = {}
    for p in partidos_eliminatorios:
        key = tuple(sorted([p.equipo_local_id, p.equipo_visitante_id]))
        partidos_map.setdefault(key, []).append(p)

    llaves_con_evaluacion = []
    for ll in llaves:
        pts_rel = []
        if ll.equipo_local_id and ll.equipo_visitante_id:
            key = tuple(sorted([ll.equipo_local_id, ll.equipo_visitante_id]))
            pts_rel = partidos_map.get(key, [])

        eval_data = evaluar_estado_llave(ll, request.organizacion)

        llaves_con_evaluacion.append({
            'llave': ll,
            'partidos': pts_rel,
            'evaluacion': eval_data,
        })

    resultado_final = ResultadoFinalTorneo.objects.filter(torneo=torneo).select_related('campeon', 'subcampeon', 'tercer_lugar', 'cuarto_lugar').first()

    context = {
        'torneo': torneo,
        'llaves_con_evaluacion': llaves_con_evaluacion,
        'hay_llaves': len(llaves) > 0,
        'resultado_final': resultado_final,
    }
    return render(request, 'matches/ver_cuadro_eliminatorio_personalizado.html', context)


@login_required
def confirmar_ganador_llave_view(request, torneo_id, llave_id):
    """
    POST endpoint para confirmar el ganador de una llave eliminatoria.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    llave = get_object_or_404(LlaveEliminatoria, id=llave_id, torneo=torneo, organizacion=request.organizacion)

    if request.method == 'POST':
        ganador_id = request.POST.get('ganador_id')
        datos_confirmacion = {
            'penales_local': request.POST.get('penales_local'),
            'penales_visitante': request.POST.get('penales_visitante'),
            'hubo_prorroga': request.POST.get('hubo_prorroga') == '1',
            'motivo_admin': request.POST.get('motivo_admin'),
            'observaciones': request.POST.get('observaciones'),
        }

        try:
            confirmar_ganador_llave(
                llave=llave,
                ganador_id=ganador_id,
                usuario=request.user,
                organizacion=request.organizacion,
                datos_confirmacion=datos_confirmacion
            )
            messages.success(request, f"Ganador confirmado exitosamente en {llave.get_fase_display()} Llave #{llave.numero_llave}.")
        except Exception as e:
            messages.error(request, f"Error al confirmar ganador: {str(e)}")

    return redirect('ver_cuadro_eliminatorio_view', torneo_id=torneo.id)


@login_required
def procesar_bye_view(request, torneo_id, llave_id):
    """
    POST endpoint para procesar el pase directo por BYE.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    llave = get_object_or_404(LlaveEliminatoria, id=llave_id, torneo=torneo, organizacion=request.organizacion)

    if request.method == 'POST':
        try:
            procesar_bye_llave(llave, request.user, request.organizacion)
            messages.success(request, f"Pase directo BYE procesado correctamente para la llave #{llave.numero_llave}.")
        except Exception as e:
            messages.error(request, f"Error al procesar BYE: {str(e)}")

    return redirect('ver_cuadro_eliminatorio_view', torneo_id=torneo.id)


@login_required
def reabrir_llave_view(request, torneo_id, llave_id):
    """
    POST endpoint para que superadmin reabra una llave eliminatoria finalizada.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    llave = get_object_or_404(LlaveEliminatoria, id=llave_id, torneo=torneo, organizacion=request.organizacion)

    if request.method == 'POST':
        motivo = request.POST.get('motivo_reapertura', '')
        try:
            reabrir_llave_eliminatoria(llave, request.user, request.organizacion, motivo)
            messages.success(request, f"Llave {llave.get_fase_display()} #{llave.numero_llave} reabierta exitosamente.")
        except Exception as e:
            messages.error(request, f"Error al reabrir llave: {str(e)}")

    return redirect('ver_cuadro_eliminatorio_view', torneo_id=torneo.id)


@login_required
def programar_partidos_ronda_view(request, torneo_id):
    """
    POST endpoint para programar partidos de llaves preparadas en la siguiente ronda.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')

    if request.method == 'POST':
        datos = {
            'fase': request.POST.get('fase'),
            'fecha_inicial': request.POST.get('fecha_inicial', timezone.now().strftime('%Y-%m-%d')),
            'hora_inicial': request.POST.get('hora_inicial', '14:00'),
            'intervalo_dias': int(request.POST.get('intervalo_dias', 7)),
            'estadio': request.POST.get('estadio', 'Estadio Principal'),
            'formato': request.POST.get('formato', 'partido_unico'),
        }
        try:
            partidos = programar_partidos_ronda_siguiente(torneo, request.organizacion, request.user, datos)
            messages.success(request, f"Programados {len(partidos)} partidos para la fase {datos['fase']}.")
        except Exception as e:
            messages.error(request, f"Error al programar ronda: {str(e)}")

    return redirect('ver_cuadro_eliminatorio_view', torneo_id=torneo.id)


@login_required
def pantalla_campeon_view(request, torneo_id):
    """
    Vista de celebración pública/administrativa del campeón y cuadro de honor del torneo.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    resultado_final = get_object_or_404(ResultadoFinalTorneo, torneo=torneo, organizacion=request.organizacion)

    partidos_final = Partido.objects.filter(
        organizacion=request.organizacion,
        torneo=torneo,
        fase='final',
        estado='finalizado'
    )

    context = {
        'torneo': torneo,
        'organizacion': request.organizacion,
        'resultado_final': resultado_final,
        'partidos_final': partidos_final,
    }
    return render(request, 'matches/pantalla_campeon.html', context)


@login_required
def imprimir_cuadro_eliminatorio_view(request, torneo_id):
    """
    Vista de impresión oficial (@media print) del cuadro eliminatorio.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    llaves = list(LlaveEliminatoria.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'ganador'))
    clasificados = list(ClasificadoTorneo.objects.filter(torneo=torneo, activo=True).select_related('equipo', 'grupo'))
    resultado_final = ResultadoFinalTorneo.objects.filter(torneo=torneo).select_related('campeon', 'subcampeon', 'tercer_lugar', 'cuarto_lugar').first()

    context = {
        'torneo': torneo,
        'organizacion': request.organizacion,
        'llaves': llaves,
        'clasificados': clasificados,
        'resultado_final': resultado_final,
        'fecha_impresion': timezone.now(),
    }
    return render(request, 'matches/imprimir_cuadro_eliminatorio_personalizado.html', context)


@login_required
def exportar_excel_cuadro_eliminatorio_view(request, torneo_id):
    """
    Descarga del libro de Excel con la estructura completa del cuadro eliminatorio, campeón y auditoría.
    """
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion, tipo='personalizado')
    excel_bytes = generar_excel_cuadro_eliminatorio_completo(torneo, request.organizacion)

    nombre_clean = slugify(torneo.nombre)
    fecha_str = timezone.now().strftime('%Y%m%d')
    filename = f"cuadro_eliminatorio_{nombre_clean}_{fecha_str}.xlsx"

    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

