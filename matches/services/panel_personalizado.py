import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
import urllib.parse
from django.db.models import Q, Count, Sum
from django.urls import reverse
from django.utils import timezone
from matches.models import (
    Torneo, GrupoTorneo, EquipoGrupoTorneo, Partido, EventoPartido,
    ClasificadoTorneo, LlaveEliminatoria, ResultadoFinalTorneo, BitacoraTorneo
)
from teams.models import Equipo
from matches.services.estadisticas_personalizado import calcular_posiciones_grupo, calcular_estadisticas_jugadores_grupo


def evaluar_estado_general_torneo(torneo):
    """
    Evalúa dinámicamente el estado general del torneo personalizado.
    Retorna uno de los estados:
    'configuracion', 'grupos_configurados', 'fixture_generado',
    'fase_grupos_en_curso', 'fase_grupos_finalizada', 'clasificados_confirmados',
    'eliminatorias_configuradas', 'eliminatorias_en_curso', 'finalizada'
    """
    if ResultadoFinalTorneo.objects.filter(torneo=torneo).exists():
        return 'finalizada'

    llaves = LlaveEliminatoria.objects.filter(torneo=torneo)
    if llaves.exists():
        partidos_elim = Partido.objects.filter(torneo=torneo, grupo_personalizado__isnull=True)
        if partidos_elim.filter(estado='finalizado').exists():
            return 'eliminatorias_en_curso'
        return 'eliminatorias_configuradas'

    if ClasificadoTorneo.objects.filter(torneo=torneo).exists():
        return 'clasificados_confirmados'

    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True)
    if not grupos.exists():
        return 'configuracion'

    partidos_grupos = Partido.objects.filter(torneo=torneo, grupo_personalizado__isnull=False)
    if not partidos_grupos.exists():
        equipos_asignados = EquipoGrupoTorneo.objects.filter(torneo=torneo).exists()
        return 'grupos_configurados' if equipos_asignados else 'configuracion'

    partidos_fin = partidos_grupos.filter(estado='finalizado').count()
    total_partidos = partidos_grupos.count()

    if total_partidos > 0 and partidos_fin == total_partidos:
        return 'fase_grupos_finalizada'
    elif partidos_fin > 0:
        return 'fase_grupos_en_curso'
    else:
        return 'fixture_generado'


def obtener_indicador_progreso(torneo, estado_general):
    """
    Retorna el indicador de 7 pasos del progreso del torneo con su estado visual y URL.
    """
    pasos_definicion = [
        ('1. Configuración', 'configuracion', 'configurar_grupos_torneo'),
        ('2. Grupos', 'grupos', 'configurar_grupos_torneo'),
        ('3. Fixture', 'fixture', 'configurar_generar_fixture_personalizado'),
        ('4. Fase de Grupos', 'fase_grupos', 'fixture_personalizado'),
        ('5. Clasificados', 'clasificados', 'confirmar_clasificados_personalizado'),
        ('6. Eliminatorias', 'eliminatorias', 'ver_cuadro_eliminatorio_personalizado'),
        ('7. Campeón', 'campeon', 'pantalla_campeon_personalizado'),
    ]

    orden_estados = {
        'configuracion': 1,
        'grupos_configurados': 2,
        'fixture_generado': 3,
        'fase_grupos_en_curso': 4,
        'fase_grupos_finalizada': 4,
        'clasificados_confirmados': 5,
        'eliminatorias_configuradas': 6,
        'eliminatorias_en_curso': 6,
        'finalizada': 7
    }

    nivel_actual = orden_estados.get(estado_general, 1)

    pasos = []
    for idx, (nombre, clave, url_name) in enumerate(pasos_definicion, start=1):
        try:
            url = reverse(url_name, kwargs={'torneo_id': torneo.id})
        except Exception:
            url = "#"

        if idx < nivel_actual:
            estado_paso = 'completado'
        elif idx == nivel_actual:
            estado_paso = 'en_curso'
        else:
            estado_paso = 'pendiente'

        pasos.append({
            'numero': idx,
            'nombre': nombre,
            'clave': clave,
            'estado': estado_paso,
            'url': url,
            'es_actual': (idx == nivel_actual)
        })

    return pasos


def obtener_proxima_accion_recomendada(torneo, estado_general):
    """
    Determina la recomendación prioritaria con botón CTA para el administrador.
    """
    if estado_general == 'configuracion':
        return {
            'titulo': 'Crear y Configurar Grupos',
            'mensaje': 'El torneo requiere crear los grupos personalizados y asignar los equipos participantes.',
            'boton': 'Gestionar Grupos',
            'url': reverse('configurar_grupos_torneo', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-primary'
        }
    elif estado_general == 'grupos_configurados':
        return {
            'titulo': 'Generar Fixture por Grupos',
            'mensaje': 'Los grupos tienen equipos asignados. Puedes configurar las fechas y generar el calendario.',
            'boton': 'Generar Fixture',
            'url': reverse('configurar_generar_fixture_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-info text-dark'
        }
    elif estado_general == 'fixture_generado':
        return {
            'titulo': 'Iniciar Fase de Grupos',
            'mensaje': 'El calendario está generado. Inicia los encuentros y registra los resultados.',
            'boton': 'Ver Calendario de Partidos',
            'url': reverse('fixture_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-warning text-dark'
        }
    elif estado_general == 'fase_grupos_en_curso':
        pendientes = Partido.objects.filter(torneo=torneo, grupo_personalizado__isnull=False, estado='programado').count()
        return {
            'titulo': 'Completar Fase de Grupos',
            'mensaje': f'Quedan {pendientes} partidos pendientes por disputar en la fase de grupos.',
            'boton': 'Ver Partidos Pendientes',
            'url': reverse('fixture_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-warning text-dark'
        }
    elif estado_general == 'fase_grupos_finalizada':
        return {
            'titulo': 'Confirmar Clasificados Definitivos',
            'mensaje': 'La fase de grupos finalizó. Revisa las tablas y confirma los clasificados a eliminatorias.',
            'boton': 'Confirmar Clasificados',
            'url': reverse('confirmar_clasificados_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-success'
        }
    elif estado_general == 'clasificados_confirmados':
        return {
            'titulo': 'Configurar Sorteo Eliminatorio',
            'mensaje': 'Los clasificados están confirmados. Configura el sorteo estilo Champions para generar el cuadro.',
            'boton': 'Configurar Sorteo',
            'url': reverse('configurar_sorteo_eliminatorio_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-primary'
        }
    elif estado_general == 'eliminatorias_configuradas':
        return {
            'titulo': 'Disputar Cuadro Eliminatorio',
            'mensaje': 'El cuadro eliminatorio está configurado. Registra los marcadores de las llaves.',
            'boton': 'Ver Cuadro Eliminatorio',
            'url': reverse('ver_cuadro_eliminatorio_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-info text-dark'
        }
    elif estado_general == 'eliminatorias_en_curso':
        llaves_listas = LlaveEliminatoria.objects.filter(torneo=torneo, estado='lista_para_confirmar').count()
        if llaves_listas > 0:
            msg = f'Hay {llaves_listas} llave(s) finalizada(s) lista(s) para confirmar ganador y avanzar.'
        else:
            msg = 'Se están disputando las eliminatorias. Continúa registrando resultados.'
        return {
            'titulo': 'Confirmar Ganadores / Avanzar Ronda',
            'mensaje': msg,
            'boton': 'Ver Cuadro Eliminatorio',
            'url': reverse('ver_cuadro_eliminatorio_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-success'
        }
    else:  # finalizada
        resultado = ResultadoFinalTorneo.objects.filter(torneo=torneo).first()
        campeon_nombre = resultado.campeon.nombre if resultado else "Campeón"
        return {
            'titulo': f'Torneo Finalizado - Campeón: {campeon_nombre}',
            'mensaje': 'El campeonato ha culminado exitosamente. Consulta la pantalla de consagraciones y reportes.',
            'boton': 'Ver Campeón',
            'url': reverse('pantalla_campeon_personalizado', kwargs={'torneo_id': torneo.id}),
            'badge': 'bg-dark'
        }


def obtener_resumen_grupos_panel(torneo):
    """
    Retorna información estructurada de cada grupo del torneo.
    """
    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).select_related('torneo').order_by('orden', 'id')
    resumen = []

    for g in grupos:
        asig = EquipoGrupoTorneo.objects.filter(grupo=g).select_related('equipo')
        equipos = [a.equipo for a in asig]

        partidos = Partido.objects.filter(torneo=torneo, grupo_personalizado=g)
        total_p = partidos.count()
        fin_p = partidos.filter(estado='finalizado').count()
        pend_p = partidos.filter(estado='programado').count()
        pct = round((fin_p / total_p * 100), 1) if total_p > 0 else 0.0

        res_pos = calcular_posiciones_grupo(g, torneo, torneo.organizacion)
        posiciones = res_pos['tabla']
        lider = posiciones[0]['equipo'] if posiciones else None

        clasificados = ClasificadoTorneo.objects.filter(grupo=g).select_related('equipo')
        if clasificados.exists():
            clasif_equipos = [c.equipo for c in clasificados]
            es_definitivo = True
        else:
            clasif_equipos = [p['equipo'] for p in posiciones[:g.cupos_clasificacion]]
            es_definitivo = False

        proximo = partidos.filter(estado='programado').order_by('fecha_hora').first()

        resumen.append({
            'grupo': g,
            'equipos_count': len(equipos),
            'equipos': equipos,
            'cupos': g.cupos_clasificacion,
            'total_partidos': total_p,
            'partidos_finalizados': fin_p,
            'partidos_pendientes': pend_p,
            'progreso_pct': pct,
            'lider': lider,
            'clasificados': clasif_equipos,
            'es_clasificacion_definitiva': es_definitivo,
            'proximo_partido': proximo
        })

    return resumen


def obtener_agenda_operativa(torneo, filtros=None):
    """
    Retorna la lista de encuentros con sus asignaciones de árbitro, vocal y advertencias operativas.
    """
    filtros = filtros or {}
    qs = Partido.objects.filter(torneo=torneo).select_related(
        'equipo_local', 'equipo_visitante', 'grupo_personalizado', 'organizacion'
    ).order_by('fecha_hora', 'id')

    # Filtros
    periodo = filtros.get('periodo')
    ahora = timezone.now()
    if periodo == 'hoy':
        qs = qs.filter(fecha_hora__date=ahora.date())
    elif periodo == 'semana':
        semana_fin = ahora + timezone.timedelta(days=7)
        qs = qs.filter(fecha_hora__range=[ahora, semana_fin])

    if filtros.get('grupo_id'):
        qs = qs.filter(grupo_personalizado_id=filtros['grupo_id'])

    if filtros.get('fase'):
        qs = qs.filter(fase=filtros['fase'])

    if filtros.get('equipo_id'):
        eq_id = filtros['equipo_id']
        qs = qs.filter(Q(equipo_local_id=eq_id) | Q(equipo_visitante_id=eq_id))

    partidos = []
    for p in qs:
        adv = []
        if not p.estadio:
            adv.append({'tipo': 'warning', 'mensaje': 'Sin cancha / estadio asignado'})
        if not p.arbitro:
            adv.append({'tipo': 'warning', 'mensaje': 'Sin árbitro asignado'})
        if not p.vocal:
            adv.append({'tipo': 'info', 'mensaje': 'Sin vocal asignado'})
        if p.estado == 'programado' and p.fecha_hora < ahora:
            adv.append({'tipo': 'danger', 'mensaje': 'Partido vencido sin finalizar'})

        partidos.append({
            'partido': p,
            'advertencias': adv
        })

    return partidos


def obtener_alertas_administrativas(torneo):
    """
    Genera la lista de alertas administrativas clasificadas por nivel: informacion, advertencia, critica.
    """
    alertas = []

    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True)
    if not grupos.exists():
        alertas.append({
            'nivel': 'critica',
            'titulo': 'Sin Grupos Creados',
            'mensaje': 'No existen grupos personalizados configurados en este torneo.'
        })
    else:
        for g in grupos:
            cnt = EquipoGrupoTorneo.objects.filter(grupo=g).count()
            if cnt == 0:
                alertas.append({
                    'nivel': 'critica',
                    'titulo': f'Grupo {g.nombre} Vacío',
                    'mensaje': f'El grupo {g.nombre} no tiene equipos asignados.'
                })
            elif cnt < g.cupos_clasificacion:
                alertas.append({
                    'nivel': 'advertencia',
                    'titulo': f'Inconsistencia de Cupos en {g.nombre}',
                    'mensaje': f'El grupo {g.nombre} tiene {cnt} equipos pero asigna {g.cupos_clasificacion} cupos.'
                })

    equipos_total = torneo.equipos.count()
    equipos_en_grupos = EquipoGrupoTorneo.objects.filter(torneo=torneo).values_list('equipo_id', flat=True).distinct().count()
    if equipos_total > equipos_en_grupos:
        diff = equipos_total - equipos_en_grupos
        alertas.append({
            'nivel': 'advertencia',
            'titulo': 'Equipos sin Grupo Asignado',
            'mensaje': f'Existen {diff} equipos inscritos en el torneo que no han sido asignados a ningún grupo.'
        })

    partidos_sin_cancha = Partido.objects.filter(torneo=torneo, estado='programado', estadio__isnull=True).count()
    if partidos_sin_cancha > 0:
        alertas.append({
            'nivel': 'informacion',
            'titulo': 'Partidos sin Cancha',
            'mensaje': f'Hay {partidos_sin_cancha} partido(s) programado(s) sin cancha/estadio asignado.'
        })

    llaves_listas = LlaveEliminatoria.objects.filter(torneo=torneo, estado='lista_para_confirmar').count()
    if llaves_listas > 0:
        alertas.append({
            'nivel': 'informacion',
            'titulo': 'Llaves Listas para Confirmar',
            'mensaje': f'Hay {llaves_listas} llave(s) eliminatoria(s) con resultados finalizados listas para confirmar ganador.'
        })

    ahora = timezone.now()
    partidos_vencidos = Partido.objects.filter(torneo=torneo, estado='programado', fecha_hora__lt=ahora).count()
    if partidos_vencidos > 0:
        alertas.append({
            'nivel': 'advertencia',
            'titulo': 'Partidos Vencidos Pendientes',
            'mensaje': f'Existen {partidos_vencidos} encuentro(s) con fecha pasada que siguen en estado programado.'
        })

    return alertas


def generar_excel_torneo_consolidado(torneo, opcion='completo'):
    """
    Genera un libro de trabajo Excel (.xlsx) consolidado con la información completa del torneo.
    Pestañas: Resumen General, Grupos y Equipos, Fixture y Resultados, Posiciones por Grupo, Clasificados Definitivos, Cuadro Eliminatorio, Tabla de Goleadores.
    """
    wb = openpyxl.Workbook()
    
    # Estilos
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    sub_font = Font(name="Calibri", size=10, italic=True, color="595959")
    bold_font = Font(name="Calibri", size=11, bold=True)
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # 1. Hoja Resumen
    ws_resumen = wb.active
    ws_resumen.title = "Resumen General"
    org_name = torneo.organizacion.nombre.upper() if (torneo.organizacion and torneo.organizacion.nombre) else "ORGANIZACIÓN"
    ws_resumen.append([f"SISTEMA DE TORNEOS - {org_name}"])
    ws_resumen.append([f"REPORTE CONSOLIDADO: {torneo.nombre}"])
    ws_resumen.append([f"Generado el: {timezone.now().strftime('%Y-%m-%d %H:%M')}"])
    ws_resumen.append([])

    cat_name = torneo.categoria.nombre if torneo.categoria else "General"
    tipo_name = torneo.get_tipo_display() if hasattr(torneo, 'get_tipo_display') else str(torneo.tipo or "")
    total_equipos_count = torneo.equipos.count() if hasattr(torneo, 'equipos') else 0
    total_partidos_count = Partido.objects.filter(torneo=torneo).count()

    ws_resumen.append(["Categoría", cat_name])
    ws_resumen.append(["Temporada", torneo.temporada or "-"])
    ws_resumen.append(["Modalidad", torneo.modalidad or "-"])
    ws_resumen.append(["Tipo de Torneo", tipo_name])
    ws_resumen.append(["Total de Grupos", GrupoTorneo.objects.filter(torneo=torneo, activo=True).count()])
    ws_resumen.append(["Total de Equipos", total_equipos_count])
    ws_resumen.append(["Total de Partidos", total_partidos_count])

    # 2. Hoja Grupos y Equipos
    ws_grupos = wb.create_sheet(title="Grupos y Equipos")
    ws_grupos.append(["Grupo", "Sector", "Equipo", "Ciudad / Representante"])
    for cell in ws_grupos[1]:
        cell.fill = header_fill
        cell.font = header_font

    grupos = GrupoTorneo.objects.filter(torneo=torneo, activo=True).order_by('orden')
    for g in grupos:
        asig = EquipoGrupoTorneo.objects.filter(grupo=g).select_related('equipo')
        for a in asig:
            eq_nombre = a.equipo.nombre if a.equipo else "Por definir"
            eq_entrenador = (a.equipo.entrenador or "") if a.equipo else ""
            ws_grupos.append([g.nombre, g.sector or "", eq_nombre, eq_entrenador])

    # 3. Hoja Fixture y Resultados
    ws_fix = wb.create_sheet(title="Fixture y Resultados")
    ws_fix.append(["ID", "Fecha / Hora", "Fase / Grupo", "Jornada", "Local", "Goles L", "Goles V", "Visitante", "Estadio", "Estado"])
    for cell in ws_fix[1]:
        cell.fill = header_fill
        cell.font = header_font

    partidos = Partido.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'grupo_personalizado').order_by('fecha_hora', 'id')
    for p in partidos:
        fase_str = p.grupo_personalizado.nombre if p.grupo_personalizado else (p.get_fase_display() if hasattr(p, 'get_fase_display') else str(p.fase or ""))
        gl = p.goles_local if p.estado in ['finalizado', 'en_curso'] and p.goles_local is not None else ""
        gv = p.goles_visitante if p.estado in ['finalizado', 'en_curso'] and p.goles_visitante is not None else ""
        eq_loc = p.equipo_local.nombre if p.equipo_local else "Por definir"
        eq_vis = p.equipo_visitante.nombre if p.equipo_visitante else "Por definir"
        fecha_str = p.fecha_hora.strftime("%Y-%m-%d %H:%M") if p.fecha_hora else "Por definir"
        estado_str = p.get_estado_display() if hasattr(p, 'get_estado_display') else str(p.estado or "")
        ws_fix.append([
            p.id,
            fecha_str,
            fase_str,
            p.numero_jornada or "",
            eq_loc,
            gl,
            gv,
            eq_vis,
            p.estadio or "",
            estado_str
        ])

    # 4. Hoja Posiciones por Grupo
    ws_pos = wb.create_sheet(title="Posiciones por Grupo")
    ws_pos.append(["Grupo", "Pos", "Equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "PTS"])
    for cell in ws_pos[1]:
        cell.fill = header_fill
        cell.font = header_font

    for g in grupos:
        try:
            res_pos = calcular_posiciones_grupo(g, torneo, torneo.organizacion)
            pos = res_pos.get('tabla', [])
            for p in pos:
                eq_obj = p.get('equipo')
                eq_nombre = eq_obj.nombre if hasattr(eq_obj, 'nombre') else str(eq_obj or "Por definir")
                ws_pos.append([
                    g.nombre,
                    p.get('posicion', ''),
                    eq_nombre,
                    p.get('PJ', 0), p.get('PG', 0), p.get('PE', 0), p.get('PP', 0),
                    p.get('GF', 0), p.get('GC', 0), p.get('DG', 0), p.get('PTS', 0)
                ])
        except Exception:
            pass

    # 5. Hoja Clasificados Definitivos
    ws_clas = wb.create_sheet(title="Clasificados Definitivos")
    ws_clas.append(["Grupo", "Posición", "Equipo", "Bombo Asignado", "PTS", "DG"])
    for cell in ws_clas[1]:
        cell.fill = header_fill
        cell.font = header_font

    clasificados = ClasificadoTorneo.objects.filter(torneo=torneo).select_related('grupo', 'equipo').order_by('grupo__orden', 'posicion_grupo')
    for c in clasificados:
        grp_name = c.grupo.nombre if c.grupo else ""
        eq_name = c.equipo.nombre if c.equipo else "Por definir"
        ws_clas.append([
            grp_name,
            c.posicion_grupo or "",
            eq_name,
            c.bombo or "",
            c.puntos if c.puntos is not None else 0,
            c.diferencia_goles if c.diferencia_goles is not None else 0
        ])

    # 6. Hoja Eliminatorias
    ws_elim = wb.create_sheet(title="Cuadro Eliminatorio")
    ws_elim.append(["Fase", "Llave", "Equipo Local", "Global L", "Global V", "Equipo Visitante", "Penales", "Ganador / Estado"])
    for cell in ws_elim[1]:
        cell.fill = header_fill
        cell.font = header_font

    llaves = LlaveEliminatoria.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'ganador').order_by('id')
    for ll in llaves:
        loc = ll.equipo_local.nombre if ll.equipo_local else ("BYE" if getattr(ll, 'es_bye', False) else "Por Definir")
        vis = ll.equipo_visitante.nombre if ll.equipo_visitante else ("BYE" if getattr(ll, 'es_bye', False) else "Por Definir")
        gan = ll.ganador.nombre if ll.ganador else (ll.get_estado_display() if hasattr(ll, 'get_estado_display') else str(ll.estado or "Pendiente"))
        pen = f"{ll.penales_local if ll.penales_local is not None else 0}-{ll.penales_visitante if ll.penales_visitante is not None else 0}" if ll.definido_por_penales else ""
        fase_name = ll.get_fase_display() if hasattr(ll, 'get_fase_display') else str(ll.fase or "")
        ws_elim.append([
            fase_name,
            ll.numero_llave or "",
            loc,
            ll.marcador_global_local if ll.marcador_global_local is not None else 0,
            ll.marcador_global_visitante if ll.marcador_global_visitante is not None else 0,
            vis,
            pen,
            gan
        ])

    # 7. Hoja Goleadores (si existen)
    try:
        from matches.services.estadisticas_personalizado import calcular_estadisticas_jugadores_general, calcular_estadisticas_jugadores_grupo
        goleadores_list = []
        if torneo.tipo == 'grupos' or GrupoTorneo.objects.filter(torneo=torneo, activo=True).exists():
            for g in grupos:
                st = calcular_estadisticas_jugadores_grupo(g, torneo, torneo.organizacion)
                goleadores_list.extend(st.get('goleadores', []))
        else:
            st = calcular_estadisticas_jugadores_general(torneo, torneo.organizacion)
            goleadores_list = st.get('goleadores', [])

        if goleadores_list:
            ws_gol = wb.create_sheet(title="Tabla de Goleadores")
            ws_gol.append(["Pos", "Jugador", "Equipo", "Goles"])
            for cell in ws_gol[1]:
                cell.fill = header_fill
                cell.font = header_font
            for idx, item in enumerate(goleadores_list, start=1):
                jug_nombre = item.get('nombre') or (item.get('jugador').get_full_name() if hasattr(item.get('jugador'), 'get_full_name') else str(item.get('jugador') or ""))
                eq_nombre = item.get('equipo_nombre') or (item.get('equipo').nombre if hasattr(item.get('equipo'), 'nombre') else "")
                ws_gol.append([idx, jug_nombre, eq_nombre, item.get('total', item.get('goles', 0))])
    except Exception:
        pass

    # Autoajuste de columnas
    for sheet in wb.worksheets:
        for col in sheet.columns:
            vals = [str(cell.value or '') for cell in col]
            max_len = max(len(v) for v in vals) if vals else 0
            if col and len(col) > 0:
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def generar_enlaces_whatsapp(torneo, base_public_url, partido=None, grupo=None):
    """
    Genera enlaces codificados de WhatsApp para compartir el torneo, un partido o la tabla de un grupo.
    """
    encoded_url = urllib.parse.quote(base_public_url)

    if partido:
        texto = f"⚽ *{torneo.nombre}*\n\n{partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}\n📅 Fecha: {partido.fecha_hora.strftime('%d/%m/%Y %H:%M') if partido.fecha_hora else 'Por definir'}\n📍 Cancha: {partido.estadio or 'Por definir'}\n\nConsulta calendario y resultados aquí:\n{base_public_url}"
    elif grupo:
        texto = f"🏆 *{torneo.nombre} - Tabla del Grupo {grupo.nombre}*\n\nConsulta las posiciones actualizadas:\n{base_public_url}"
    else:
        texto = f"🏆 *{torneo.nombre}*\nCategoría: {torneo.categoria.nombre if torneo.categoria else 'General'}\n\nSigue todos los grupos, resultados y tabla de posiciones aquí:\n{base_public_url}"

    texto_enc = urllib.parse.quote(texto)
    return f"https://api.whatsapp.com/send?text={texto_enc}"
