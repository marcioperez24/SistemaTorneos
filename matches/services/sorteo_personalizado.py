import io
import random
from datetime import datetime, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from matches.models import (
    Torneo, GrupoTorneo, Partido, EquipoGrupoTorneo,
    ClasificadoTorneo, ResolucionEmpateTorneo, LlaveEliminatoria, BitacoraTorneo
)
from matches.services.estadisticas_personalizado import (
    calcular_posiciones_grupo, calcular_resumen_grupo
)
from teams.models import Equipo

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


def verificar_estado_clasificacion_grupos(torneo, organizacion):
    """
    Revisa el estado de finalización de todos los grupos y detecta empates pendientes en frontera de clasificación.
    """
    grupos = list(GrupoTorneo.objects.filter(torneo=torneo).order_by('orden', 'id'))
    grupos_info = []

    todos_finalizados = True
    tiene_partidos_pendientes = False
    tiene_empates_pendientes = False

    for g in grupos:
        res_pos = calcular_posiciones_grupo(g, torneo, organizacion)
        res_info = calcular_resumen_grupo(g, torneo, organizacion)

        estado = res_info['estado_grupo']
        if estado != 'Finalizado':
            todos_finalizados = False
            tiene_partidos_pendientes = True

        # Verificar empates pendientes en los clasificados
        empates_en_grupo = False
        for item in res_pos['tabla']:
            if item['empate_pendiente']:
                tiene_empates_pendientes = True
                empates_en_grupo = True

        grupos_info.append({
            'grupo': g,
            'estado': estado,
            'resumen': res_info,
            'tabla': res_pos['tabla'],
            'cupos': res_pos['cupos'],
            'advertencia_cupos': res_pos['advertencia_cupos'],
            'empates_en_grupo': empates_en_grupo,
        })

    return {
        'todos_finalizados': todos_finalizados,
        'tiene_partidos_pendientes': tiene_partidos_pendientes,
        'tiene_empates_pendientes': tiene_empates_pendientes,
        'grupos_info': grupos_info,
    }


def resolver_empate_administrativo(torneo, grupo, equipos_ids, equipo_ganador_id, motivo, observacion, usuario, organizacion):
    """
    Registra la resolución administrativa de un empate para un grupo.
    """
    if torneo.tipo != 'personalizado':
        raise ValidationError("Esta función solo aplica a torneos personalizados.")

    equipo_ganador = Equipo.objects.get(id=equipo_ganador_id, organizacion=organizacion)
    equipos = list(Equipo.objects.filter(id__in=equipos_ids, organizacion=organizacion))

    with transaction.atomic():
        resolucion = ResolucionEmpateTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            grupo=grupo,
            equipo_ganador=equipo_ganador,
            motivo_resolucion=motivo,
            observacion=observacion,
            resuelto_por=usuario
        )
        resolucion.equipos_empatados.set(equipos)

        BitacoraTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            usuario=usuario,
            accion="Resolución Administrativa de Empate",
            detalles=f"Grupo {grupo.nombre}: Empate entre {[e.nombre for e in equipos]} resuelto a favor de {equipo_ganador.nombre} (Motivo: {motivo})"
        )

    return resolucion


def confirmar_clasificados_definitivos(torneo, organizacion, usuario, confirmacion_excepcional=False, motivo=""):
    """
    Confirma definitivamente los equipos clasificados de la fase de grupos y genera registros ClasificadoTorneo.
    """
    if torneo.tipo != 'personalizado':
        raise ValidationError("Solo se pueden confirmar clasificados en torneos personalizados.")

    if ClasificadoTorneo.objects.filter(torneo=torneo, activo=True).exists():
        raise ValidationError("Los clasificados de este torneo ya han sido confirmados definitivamente.")

    estado_info = verificar_estado_clasificacion_grupos(torneo, organizacion)

    if not estado_info['todos_finalizados'] and not confirmacion_excepcional:
        raise ValidationError("No se pueden confirmar los clasificados porque todavía existen partidos pendientes en los grupos.")

    if confirmacion_excepcional:
        if not motivo or len(motivo.strip()) < 5:
            raise ValidationError("Para una confirmación excepcional debes ingresar un motivo justificado.")
        if usuario.role not in ['superadmin', 'comision']:
            raise ValidationError("Solo un usuario administrador puede realizar una confirmación excepcional.")

    if estado_info['tiene_empates_pendientes']:
        raise ValidationError("Existen empates pendientes de resolución en la zona de clasificación. Debes resolver los empates antes de confirmar.")

    clasificados_creados = []

    with transaction.atomic():
        for item_g in estado_info['grupos_info']:
            grupo = item_g['grupo']
            cupos = item_g['cupos']
            tabla = item_g['tabla']

            clasificados_grupo = tabla[:cupos]
            for pos_idx, item_eq in enumerate(clasificados_grupo, start=1):
                equipo_obj = item_eq['equipo']
                bombo_num = item_eq['posicion'] # El puesto en el grupo determina el Bombo (1ro -> Bombo 1, 2do -> Bombo 2, etc.)

                clas = ClasificadoTorneo.objects.create(
                    organizacion=organizacion,
                    torneo=torneo,
                    grupo=grupo,
                    equipo=equipo_obj,
                    posicion_grupo=item_eq['posicion'],
                    puntos=item_eq['PTS'],
                    diferencia_goles=item_eq['DG'],
                    goles_favor=item_eq['GF'],
                    bombo=bombo_num,
                    metodo_clasificacion='posicion',
                    confirmado_por=usuario,
                    datos_tabla={
                        'PJ': item_eq['PJ'],
                        'PG': item_eq['PG'],
                        'PE': item_eq['PE'],
                        'PP': item_eq['PP'],
                        'rendimiento': item_eq['rendimiento'],
                        'forma': item_eq['forma'],
                    }
                )
                clasificados_creados.append(clas)

        detalles_log = f"Confirmados {len(clasificados_creados)} clasificados de {len(estado_info['grupos_info'])} grupos."
        if confirmacion_excepcional:
            detalles_log += f" [CONFIRMACIÓN EXCEPCIONAL. Motivo: {motivo}]"

        BitacoraTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            usuario=usuario,
            accion="Confirmación Definitiva de Clasificados",
            detalles=detalles_log
        )

    return clasificados_creados


def reabrir_clasificacion_definitiva(torneo, organizacion, usuario, motivo):
    """
    Permite a un superadmin reabrir la clasificación previa a las eliminatorias si no han iniciado partidos eliminatorios.
    """
    if usuario.role != 'superadmin':
        raise ValidationError("Solo un superadmin puede reabrir la clasificación.")

    if not motivo or len(motivo.strip()) < 5:
        raise ValidationError("Debes especificar un motivo para reabrir la clasificación.")

    # Verificar si existen partidos eliminatorios iniciados o finalizados
    partidos_iniciados = Partido.objects.filter(
        organizacion=organizacion,
        torneo=torneo,
        fase__in=['dieciseisavos', 'octavos', 'cuartos', 'semifinal', 'final'],
        estado__in=['en_curso', 'finalizado']
    ).count()

    if partidos_iniciados > 0:
        raise ValidationError("No se puede reabrir la clasificación porque ya existen partidos eliminatorios iniciados o finalizados.")

    with transaction.atomic():
        # Borrar partidos eliminatorios programados
        Partido.objects.filter(
            organizacion=organizacion,
            torneo=torneo,
            fase__in=['dieciseisavos', 'octavos', 'cuartos', 'semifinal', 'final']
        ).delete()

        # Borrar llaves eliminatorias
        LlaveEliminatoria.objects.filter(torneo=torneo).delete()

        # Borrar clasificados definitivos
        ClasificadoTorneo.objects.filter(torneo=torneo).delete()

        BitacoraTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            usuario=usuario,
            accion="Reapertura de Clasificación Definitiva",
            detalles=f"Se reabrió la fase de clasificación. Motivo: {motivo}"
        )


def _calcular_fase_y_byes(total_clasificados):
    """
    Determina la primera fase eliminatoria y la cantidad de pases directos (BYE).
    """
    if total_clasificados > 16:
        fase = 'dieciseisavos'
        target_teams = 32
        num_llaves = 16
    elif total_clasificados > 8:
        fase = 'octavos'
        target_teams = 16
        num_llaves = 8
    elif total_clasificados > 4:
        fase = 'cuartos'
        target_teams = 8
        num_llaves = 4
    elif total_clasificados > 2:
        fase = 'semifinal'
        target_teams = 4
        num_llaves = 2
    else:
        fase = 'final'
        target_teams = 2
        num_llaves = 1

    byes = target_teams - total_clasificados
    return fase, num_llaves, byes


def generar_sorteo_eliminatorio(torneo, organizacion, usuario, params):
    """
    Genera el sorteo automático de cruces eliminatorios estilo Champions o permite estructuración manual.
    Retorna la estructura de vista previa sin crear partidos todavía.
    """
    clasificados = list(
        ClasificadoTorneo.objects.filter(torneo=torneo, activo=True)
        .select_related('equipo', 'grupo')
        .order_by('bombo', '-puntos', '-diferencia_goles', '-goles_favor')
    )

    if not clasificados:
        raise ValidationError("No existen clasificados definitivos confirmados para este torneo.")

    total_clas = len(clasificados)
    fase_inicial, num_llaves, num_byes = _calcular_fase_y_byes(total_clas)

    evitar_mismo_grupo = params.get('evitar_mismo_grupo', True)
    evitar_mismo_sector = params.get('evitar_mismo_sector', False)
    semilla = str(params.get('semilla', timezone.now().timestamp()))
    formato = params.get('formato', 'partido_unico')
    sortear_localia = params.get('sortear_localia', True)

    rng = random.Random(semilla)

    # Asignar BYEs si existen (favoreciendo a los mejores de Bombo 1)
    equipos_para_sorteo = list(clasificados)
    equipos_bye = []

    if num_byes > 0:
        # Los top de bombo 1 obtienen pase directo (BYE)
        equipos_bye = equipos_para_sorteo[:num_byes]
        equipos_para_sorteo = equipos_para_sorteo[num_byes:]

    # Separar en Sembrados (Locales / Bombo 1 y 2) y No Sembrados (Visitantes / Bombo 3, 4)
    mitad = len(equipos_para_sorteo) // 2
    sembrados = equipos_para_sorteo[:mitad]
    no_sembrados = equipos_para_sorteo[mitad:]

    # Algoritmo de emparejamiento con reintentos
    max_intentos = 500
    exito = False
    cruces = []

    for intento in range(max_intentos):
        cand_sembrados = list(sembrados)
        cand_no_sembrados = list(no_sembrados)
        rng.shuffle(cand_sembrados)
        rng.shuffle(cand_no_sembrados)

        temp_cruces = []
        conflicto = False

        while cand_sembrados and cand_no_sembrados:
            local = cand_sembrados.pop(0)
            
            # Buscar visitante compatible
            visitante_encontrado = None
            for idx, vis in enumerate(cand_no_sembrados):
                incompatible = False
                if evitar_mismo_grupo and local.grupo_id == vis.grupo_id:
                    incompatible = True
                if evitar_mismo_sector and local.grupo.sector and vis.grupo.sector and local.grupo.sector == vis.grupo.sector:
                    incompatible = True

                if not incompatible:
                    visitante_encontrado = cand_no_sembrados.pop(idx)
                    break

            if not visitante_encontrado:
                conflicto = True
                break
            
            # Intercambiar localía aleatoriamente si está habilitado
            if sortear_localia and rng.choice([True, False]):
                local, visitante_encontrado = visitante_encontrado, local

            temp_cruces.append({
                'local': local,
                'visitante': visitante_encontrado,
                'es_bye': False
            })

        if not conflicto and len(temp_cruces) == mitad:
            cruces = temp_cruces
            exito = True
            break

    if not exito and len(equipos_para_sorteo) > 0:
        # Si falló con todas las restricciones juntas, intentar sin restricción de sector
        if evitar_mismo_sector:
            raise ValidationError("No es posible generar cruces respetando la restricción de mismo sector. Desactiva la restricción de sector y vuelve a intentar.")
        elif evitar_mismo_grupo:
            raise ValidationError("No es posible generar cruces respetando la restricción de mismo grupo. Relaja las restricciones y vuelve a intentar.")

    # Agregar llaves de BYE
    llaves_vista_previa = []
    numero_llave = 1

    for c in cruces:
        llaves_vista_previa.append({
            'numero_llave': numero_llave,
            'fase': fase_inicial,
            'local': c['local'],
            'visitante': c['visitante'],
            'es_bye': False,
            'formato': formato,
        })
        numero_llave += 1

    for bye_clas in equipos_bye:
        llaves_vista_previa.append({
            'numero_llave': numero_llave,
            'fase': fase_inicial,
            'local': bye_clas,
            'visitante': None,
            'es_bye': True,
            'formato': formato,
        })
        numero_llave += 1

    return {
        'torneo': torneo,
        'fase_inicial': fase_inicial,
        'fase_display': dict(Partido.FASE_CHOICES).get(fase_inicial, fase_inicial),
        'total_clasificados': total_clas,
        'num_llaves': len(llaves_vista_previa),
        'num_byes': num_byes,
        'semilla': semilla,
        'formato': formato,
        'llaves': llaves_vista_previa,
        'params': params,
    }


def confirmar_y_crear_cuadro_eliminatorio(torneo, organizacion, usuario, preview_data):
    """
    Confirma la vista previa e inserta en la base de datos las LlavesEliminatorias y los Partidos de la primera ronda.
    """
    if torneo.tipo != 'personalizado':
        raise ValidationError("Solo aplica a torneos personalizados.")

    llaves_input = preview_data.get('llaves', [])
    fase_inicial = preview_data.get('fase_inicial', 'octavos')
    formato = preview_data.get('formato', 'partido_unico')
    fecha_inicial_str = preview_data.get('fecha_inicial', timezone.now().strftime('%Y-%m-%d'))
    hora_inicial_str = preview_data.get('hora_inicial', '14:00')
    intervalo_dias = int(preview_data.get('intervalo_dias', 7))
    estadio = preview_data.get('estadio', 'Estadio Principal')

    try:
        dt_base = datetime.strptime(f"{fecha_inicial_str} {hora_inicial_str}", '%Y-%m-%d %H:%M')
        dt_base = timezone.make_aware(dt_base)
    except Exception:
        dt_base = timezone.now() + timedelta(days=1)

    with transaction.atomic():
        # Limpiar llaves previas no iniciadas
        LlaveEliminatoria.objects.filter(torneo=torneo).delete()
        Partido.objects.filter(
            organizacion=organizacion,
            torneo=torneo,
            fase__in=['dieciseisavos', 'octavos', 'cuartos', 'semifinal', 'final']
        ).delete()

        llaves_creadas = []

        for idx, item in enumerate(llaves_input, start=1):
            clas_loc = item.get('local')
            clas_vis = item.get('visitante')
            es_bye = item.get('es_bye', False)

            if isinstance(clas_loc, dict):
                clas_loc = ClasificadoTorneo.objects.get(id=clas_loc['id'])
            if isinstance(clas_vis, dict) and clas_vis is not None:
                clas_vis = ClasificadoTorneo.objects.get(id=clas_vis['id'])

            eq_loc = clas_loc.equipo if clas_loc else None
            eq_vis = clas_vis.equipo if clas_vis else None

            llave = LlaveEliminatoria.objects.create(
                organizacion=organizacion,
                torneo=torneo,
                fase=fase_inicial,
                numero_llave=idx,
                equipo_local=eq_loc,
                equipo_visitante=eq_vis,
                clasificado_local=clas_loc,
                clasificado_visitante=clas_vis,
                formato=formato,
                estado='programada' if not es_bye else 'finalizada',
                es_bye=es_bye,
                orden_visual=idx
            )
            llaves_creadas.append(llave)

            # Crear partidos de primera ronda si no es BYE
            if not es_bye and eq_loc and eq_vis:
                # Partido Ida / Único
                Partido.objects.create(
                    organizacion=organizacion,
                    torneo=torneo,
                    fase=fase_inicial,
                    numero_vuelta=1,
                    equipo_local=eq_loc,
                    equipo_visitante=eq_vis,
                    fecha_hora=dt_base + timedelta(hours=(idx - 1) * 2),
                    estadio=estadio,
                    jornada=idx,
                    estado='programado',
                    temporada=torneo.temporada
                )

                # Si es Ida y Vuelta, crear Partido de Vuelta con localía invertida
                if formato == 'ida_vuelta':
                    dt_vuelta = dt_base + timedelta(days=intervalo_dias, hours=(idx - 1) * 2)
                    Partido.objects.create(
                        organizacion=organizacion,
                        torneo=torneo,
                        fase=fase_inicial,
                        numero_vuelta=2,
                        equipo_local=eq_vis, # Inversión de localía
                        equipo_visitante=eq_loc,
                        fecha_hora=dt_vuelta,
                        estadio=estadio,
                        jornada=idx,
                        estado='programado',
                        temporada=torneo.temporada
                    )

        BitacoraTorneo.objects.create(
            organizacion=organizacion,
            torneo=torneo,
            usuario=usuario,
            accion="Confirmación de Cuadro Eliminatorio",
            detalles=f"Creado cuadro eliminatorio de {fase_inicial} con {len(llaves_creadas)} llaves (Formato: {formato})."
        )

    return llaves_creadas


def generar_excel_cuadro_eliminatorio(torneo, organizacion):
    """
    Genera un libro Excel (.xlsx) con la estructura completa del cuadro eliminatorio.
    """
    if not OPENPYXL_AVAILABLE:
        raise ImportError("openpyxl no está disponible.")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    normal_font = Font(name="Calibri", size=11)
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )

    # 1. Hoja de Clasificados
    ws_clas = wb.create_sheet(title="Clasificados")
    ws_clas.append([f"CLASIFICADOS DEFINITIVOS - {torneo.nombre.upper()}"])
    ws_clas.append(["BOMBO", "EQUIPO", "GRUPO", "POSICIÓN", "PTS", "DG", "GF", "FECHA CONFIRMACIÓN"])
    ws_clas['A1'].font = title_font

    for c in range(1, 9):
        ws_clas.cell(row=2, column=c).fill = header_fill
        ws_clas.cell(row=2, column=c).font = header_font

    clasificados = ClasificadoTorneo.objects.filter(torneo=torneo, activo=True).order_by('bombo', 'posicion_grupo')
    for item in clasificados:
        ws_clas.append([
            f"Bombo {item.bombo}",
            item.equipo.nombre,
            item.grupo.nombre,
            item.posicion_grupo,
            item.puntos,
            item.diferencia_goles,
            item.goles_favor,
            item.fecha_confirmacion.strftime('%Y-%m-%d %H:%M')
        ])
        for col_idx in range(1, 9):
            ws_clas.cell(row=ws_clas.max_row, column=col_idx).border = thin_border

    # 2. Hoja del Cuadro Eliminatorio
    ws_cuadro = wb.create_sheet(title="Cuadro Eliminatorio")
    ws_cuadro.append([f"CUADRO ELIMINATORIO - {torneo.nombre.upper()}"])
    ws_cuadro.append(["LLAVE #", "FASE", "LOCAL", "VISITANTE", "FORMATO", "ESTADO", "BYE"])
    ws_cuadro['A1'].font = title_font

    for c in range(1, 8):
        ws_cuadro.cell(row=2, column=c).fill = header_fill
        ws_cuadro.cell(row=2, column=c).font = header_font

    llaves = LlaveEliminatoria.objects.filter(torneo=torneo).order_by('fase', 'numero_llave')
    for ll in llaves:
        loc_name = ll.equipo_local.nombre if ll.equipo_local else ("BYE" if ll.es_bye else "Por Definir")
        vis_name = ll.equipo_visitante.nombre if ll.equipo_visitante else ("BYE" if ll.es_bye else "Por Definir")
        ws_cuadro.append([
            ll.numero_llave,
            ll.get_fase_display(),
            loc_name,
            vis_name,
            ll.get_formato_display(),
            ll.get_estado_display(),
            "SI" if ll.es_bye else "NO"
        ])
        for col_idx in range(1, 8):
            ws_cuadro.cell(row=ws_cuadro.max_row, column=col_idx).border = thin_border

    for ws_curr in [ws_clas, ws_cuadro]:
        for col in ws_curr.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_curr.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
