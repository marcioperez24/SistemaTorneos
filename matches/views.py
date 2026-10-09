from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from teams.models import Equipo, FichaJugador
from .models import Partido, EventoPartido, Torneo, Estadio, BitacoraTorneo
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, F, Count
from .forms import ArbitroForm, ArbitroEdicionForm, VocalForm, VocalEdicionForm, TorneoForm, TorneoEdicionForm, EstadioForm
from finances.models import MultaTarjeta

User = get_user_model()


def partidos_lista(request):
    torneo_id = request.GET.get('torneo')
    torneos = Torneo.objects.filter(organizacion=request.organizacion).order_by('-fecha_creacion')
    
    selected_torneo = None
    if torneo_id:
        selected_torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)
    elif torneos.exists():
        selected_torneo = torneos.first()
        
    if selected_torneo:
        partidos = Partido.objects.filter(torneo=selected_torneo).select_related('equipo_local', 'equipo_visitante', 'arbitro', 'vocal').order_by('jornada', 'fecha_hora')
        equipos = selected_torneo.equipos.all()
    else:
        partidos = Partido.objects.filter(organizacion=request.organizacion).select_related('equipo_local', 'equipo_visitante', 'arbitro', 'vocal').order_by('jornada', 'fecha_hora')
        equipos = Equipo.objects.filter(organizacion=request.organizacion)
    
    tabla_tipo = 'general'
    tabla_posiciones = []
    tablas_grupos = []
    partidos_eliminatorias = []
    
    # 1. Tabla General de Posiciones
    for eq in equipos:
        if selected_torneo:
            partidos_jugados = Partido.objects.filter(
                Q(equipo_local=eq) | Q(equipo_visitante=eq),
                torneo=selected_torneo,
                estado='finalizado'
            )
        else:
            partidos_jugados = Partido.objects.filter(
                Q(equipo_local=eq) | Q(equipo_visitante=eq),
                estado='finalizado'
            )
        
        pj = partidos_jugados.count()
        pg = pe = pp = gf = gc = 0
        for p in partidos_jugados:
            if p.equipo_local == eq:
                gf += p.goles_local
                gc += p.goles_visitante
                if p.goles_local > p.goles_visitante:
                    pg += 1
                elif p.goles_local == p.goles_visitante:
                    pe += 1
                else:
                    pp += 1
            else:
                gf += p.goles_visitante
                gc += p.goles_local
                if p.goles_visitante > p.goles_local:
                    pg += 1
                elif p.goles_local == p.goles_visitante:
                    pe += 1
                else:
                    pp += 1
        
        pts = (pg * 3) + pe
        gd = gf - gc
        tabla_posiciones.append({
            'equipo': eq, 'pj': pj, 'pg': pg, 'pe': pe, 'pp': pp,
            'gf': gf, 'gc': gc, 'gd': gd, 'pts': pts
        })
    tabla_posiciones = sorted(tabla_posiciones, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))

    # 2. Si el torneo es de tipo 'torneo' (Fase de Grupos + Eliminatorias)
    if selected_torneo and selected_torneo.tipo == 'torneo':
        tabla_tipo = 'grupos'
        partidos_grupos = Partido.objects.filter(torneo=selected_torneo, fase='grupos')
        
        if partidos_grupos.exists():
            grupos_dict = {}
            for p in partidos_grupos:
                g_name = p.grupo or "Grupo A"
                grupos_dict.setdefault(g_name, set()).add(p.equipo_local)
                grupos_dict.setdefault(g_name, set()).add(p.equipo_visitante)
                
            for g_name, eq_set in sorted(grupos_dict.items()):
                grupo_tabla = []
                for eq in eq_set:
                    partidos_jugados = Partido.objects.filter(
                        Q(equipo_local=eq) | Q(equipo_visitante=eq),
                        torneo=selected_torneo,
                        fase='grupos',
                        grupo=g_name,
                        estado='finalizado'
                    )
                    pj = partidos_jugados.count()
                    pg = pe = pp = gf = gc = 0
                    for p in partidos_jugados:
                        if p.equipo_local == eq:
                            gf += p.goles_local
                            gc += p.goles_visitante
                            if p.goles_local > p.goles_visitante: pg += 1
                            elif p.goles_local == p.goles_visitante: pe += 1
                            else: pp += 1
                        else:
                            gf += p.goles_visitante
                            gc += p.goles_local
                            if p.goles_visitante > p.goles_local: pg += 1
                            elif p.goles_local == p.goles_visitante: pe += 1
                            else: pp += 1
                    pts = (pg * 3) + pe
                    gd = gf - gc
                    grupo_tabla.append({
                        'equipo': eq, 'pj': pj, 'pg': pg, 'pe': pe, 'pp': pp,
                        'gf': gf, 'gc': gc, 'gd': gd, 'pts': pts
                    })
                grupo_tabla = sorted(grupo_tabla, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
                tablas_grupos.append({'grupo': g_name, 'tabla': grupo_tabla})
        
        if not tablas_grupos:
            tabla_tipo = 'grupos_sin_sorteo'
            
        # Partidos de Fase Eliminatoria
        partidos_eliminatorias = Partido.objects.filter(
            torneo=selected_torneo,
            fase__in=['dieciseisavos', 'octavos', 'cuartos', 'semifinal', 'final']
        ).select_related('equipo_local', 'equipo_visitante').order_by('fase', 'id')

    # 3. Estadísticas de Jugadores (Líderes) para la competencia seleccionada
    def get_top_events(event_type):
        qs = EventoPartido.objects.filter(tipo=event_type, jugador__isnull=False)
        if selected_torneo:
            qs = qs.filter(partido__torneo=selected_torneo)
        else:
            qs = qs.filter(partido__organizacion=request.organizacion)
            
        events = qs.values(
            'jugador__id', 'jugador__first_name', 'jugador__last_name',
            'equipo__id', 'equipo__nombre', 'equipo__logo'
        ).annotate(total=Count('id')).order_by('-total')[:10]
        
        stats = []
        for evt in events:
            ficha = None
            if selected_torneo:
                ficha = FichaJugador.objects.filter(
                    user_id=evt['jugador__id'], equipo_id=evt['equipo__id'], torneo=selected_torneo
                ).first()
            if not ficha:
                ficha = FichaJugador.objects.filter(
                    user_id=evt['jugador__id'], equipo_id=evt['equipo__id']
                ).order_by('-id').first()
                
            numero_camiseta = ficha.numero_camiseta if ficha and ficha.numero_camiseta else '-'
            foto_url = ficha.foto.url if ficha and ficha.foto else None
            logo_url = '/media/' + evt['equipo__logo'] if evt['equipo__logo'] else None
            
            stats.append({
                'nombre_jugador': f"{evt['jugador__first_name']} {evt['jugador__last_name']}".strip(),
                'equipo': evt['equipo__nombre'],
                'numero_camiseta': numero_camiseta,
                'total': evt['total'],
                'foto_url': foto_url,
                'logo_url': logo_url
            })
        return stats

    top_goleadores = get_top_events('gol')
    top_asistidores = get_top_events('asistencia')
    top_amarillas = get_top_events('amarilla')
    top_rojas = get_top_events('roja')

    context = {
        'partidos': partidos,
        'tabla': tabla_posiciones,
        'tablas_grupos': tablas_grupos,
        'partidos_eliminatorias': partidos_eliminatorias,
        'tabla_tipo': tabla_tipo,
        'torneos': torneos,
        'selected_torneo': selected_torneo,
        'top_goleadores': top_goleadores,
        'top_asistidores': top_asistidores,
        'top_amarillas': top_amarillas,
        'top_rojas': top_rojas,
    }
    return render(request, 'matches/partidos_lista.html', context)


@login_required
def generar_fixture_view(request):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para generar calendarios.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        categoria = request.POST.get('categoria', 'senior')
        equipos = list(Equipo.objects.filter(categoria=categoria))
        
        if len(equipos) < 2:
            messages.error(request, "Se necesitan al menos 2 equipos en esta categoría para generar el fixture.")
            return redirect('generar_fixture')
            
        # Si el número de equipos es impar, agregamos un equipo ficticio para "BYE" (descanso)
        if len(equipos) % 2 != 0:
            equipos.append(None)
            
        n = len(equipos)
        rondas = n - 1
        partidos_por_ronda = n // 2
        
        # Algoritmo de Calendario (Round Robin / Sistema Berger)
        partidos_creados = 0
        fecha_inicial = timezone.now() + timedelta(days=1) # Empieza mañana
        
        # Eliminar partidos programados previos de esa categoría para evitar duplicación
        Partido.objects.filter(
            Q(equipo_local__categoria=categoria) | Q(equipo_visitante__categoria=categoria),
            estado='programado'
        ).delete()
        
        for r in range(rondas):
            jornada = r + 1
            fecha_jornada = fecha_inicial + timedelta(weeks=r) # Una jornada por semana
            
            for p in range(partidos_por_ronda):
                local = equipos[p]
                visitante = equipos[n - 1 - p]
                
                # Omitir descansos (si alguno es None)
                if local is not None and visitante is not None:
                    # Alternar localía
                    if r % 2 == 0:
                        eq_local, eq_vis = local, visitante
                    else:
                        eq_local, eq_vis = visitante, local
                        
                    # Configurar hora del partido (separados por 2 horas en el mismo estadio de forma ilustrativa)
                    hora_partido = fecha_jornada.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(hours=p*2)
                    
                    # Asignar un vocal y árbitro de la organización actual si existen
                    vocal = User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct().first()
                    arbitro = User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct().first()

                    Partido.objects.create(
                        equipo_local=eq_local,
                        equipo_visitante=eq_vis,
                        fecha_hora=hora_partido,
                        estadio="Estadio Central de la Liga",
                        jornada=jornada,
                        temporada="Copa de Campeones 2026",
                        vocal=vocal,
                        arbitro=arbitro,
                        estado='programado',
                        organizacion=request.organizacion
                    )
                    partidos_creados += 1
            
            # Rotar los equipos (dejando el primero fijo)
            equipos = [equipos[0]] + [equipos[-1]] + equipos[1:-1]
            
        messages.success(request, f"¡Fixture todos contra todos generado! Se crearon {partidos_creados} partidos en {rondas} jornadas para la categoría {categoria.upper()}.")
        return redirect('partidos_lista')
        
    return render(request, 'matches/generar_fixture.html')


@login_required
def vocalia_dashboard(request):
    if request.user.role not in ['vocal', 'superadmin']:
        messages.error(request, "Solo los vocales autorizados pueden acceder a este portal.")
        return redirect('partidos_lista')
        
    # Partidos asignados a este vocal
    partidos = Partido.objects.filter(
        organizacion=request.organizacion,
        vocal=request.user
    ).exclude(estado='finalizado').select_related('equipo_local', 'equipo_visitante').order_by('fecha_hora')
    
    historial = Partido.objects.filter(
        organizacion=request.organizacion,
        vocal=request.user,
        estado='finalizado'
    ).select_related('equipo_local', 'equipo_visitante').order_by('-fecha_hora')[:10]

    context = {
        'partidos': partidos,
        'historial': historial
    }
    return render(request, 'matches/vocalia_dashboard.html', context)


@login_required
def match_day(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    
    if request.user.role not in ['vocal', 'arbitro', 'superadmin'] or (
        partido.vocal != request.user and partido.arbitro != request.user and request.user.role != 'superadmin'
    ):
        messages.error(request, "No estás autorizado como vocal o árbitro de este partido.")
        return redirect('vocalia_dashboard')
        
    sync_requested = request.GET.get('sync') == '1'
    
    if partido.estado == 'programado':
        partido.estado = 'en_curso'
        partido.alineacion_local = partido.equipo_local.alineacion or {}
        partido.alineacion_visitante = partido.equipo_visitante.alineacion or {}
        partido.save()
        messages.info(request, f"¡El partido entre {partido.equipo_local.nombre} y {partido.equipo_visitante.nombre} ha iniciado!")
    else:
        save_needed = False
        if sync_requested or not partido.alineacion_local or not partido.alineacion_local.get('players'):
            partido.alineacion_local = partido.equipo_local.alineacion or {}
            save_needed = True
        if sync_requested or not partido.alineacion_visitante or not partido.alineacion_visitante.get('players'):
            partido.alineacion_visitante = partido.equipo_visitante.alineacion or {}
            save_needed = True
        if save_needed:
            partido.save()
            if sync_requested:
                messages.success(request, "Alineaciones sincronizadas con las plantillas del club correctamente.")
        
    # Obtener jugadores habilitados (aprobados) de cada equipo para este torneo específico
    jugadores_local = FichaJugador.objects.filter(equipo=partido.equipo_local, torneo=partido.torneo, estado_validacion='aprobado').select_related('user')
    jugadores_visitante = FichaJugador.objects.filter(equipo=partido.equipo_visitante, torneo=partido.torneo, estado_validacion='aprobado').select_related('user')
    
    # Eventos actuales del partido
    eventos = EventoPartido.objects.filter(partido=partido).select_related('jugador', 'equipo').order_by('-minuto', '-id')
    
    context = {
        'partido': partido,
        'jugadores_local': jugadores_local,
        'jugadores_visitante': jugadores_visitante,
        'eventos': eventos
    }
    return render(request, 'matches/match_day.html', context)


@login_required
def registrar_evento(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    
    if request.user.role not in ['vocal', 'arbitro', 'superadmin'] or (
        partido.vocal != request.user and partido.arbitro != request.user and request.user.role != 'superadmin'
    ):
        return redirect('vocalia_dashboard')
        
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        minuto = int(request.POST.get('minuto', 0))
        equipo_id = request.POST.get('equipo_id')
        jugador_id = request.POST.get('jugador_id')
        
        equipo = get_object_or_404(Equipo, id=equipo_id)
        jugador = None
        if jugador_id:
            jugador = User.objects.filter(id=jugador_id).first()
            if not jugador:
                ficha_ref = FichaJugador.objects.filter(id=jugador_id).select_related('user').first()
                if ficha_ref and ficha_ref.user:
                    jugador = ficha_ref.user
        
        # En caso de sustitución
        jugador_entra = None
        detalle_str = None
        if tipo == 'cambio':
            jugador_entra_id = request.POST.get('jugador_entra_id')
            if jugador_entra_id:
                jugador_entra = User.objects.filter(id=jugador_entra_id).first()
                if not jugador_entra:
                    ficha_e_ref = FichaJugador.objects.filter(id=jugador_entra_id).select_related('user').first()
                    if ficha_e_ref and ficha_e_ref.user:
                        jugador_entra = ficha_e_ref.user

                ficha_sale = FichaJugador.objects.filter(user=jugador, equipo=equipo, torneo=partido.torneo).first() if jugador else None
                ficha_entra = FichaJugador.objects.filter(user=jugador_entra, equipo=equipo, torneo=partido.torneo).first() if jugador_entra else None
                n_sale = f"#{ficha_sale.numero_camiseta}" if (ficha_sale and ficha_sale.numero_camiseta) else ""
                n_entra = f"#{ficha_entra.numero_camiseta}" if (ficha_entra and ficha_entra.numero_camiseta) else ""
                
                nom_entra = (jugador_entra.get_full_name() or jugador_entra.username) if jugador_entra else "Jugador"
                nom_sale = (jugador.get_full_name() or jugador.username) if jugador else "Jugador"
                detalle_str = f"Entra {nom_entra} {n_entra} por {nom_sale} {n_sale}"
                
                # Actualizar alineación en vivo del partido
                lineup = partido.alineacion_local if partido.equipo_local == equipo else partido.alineacion_visitante
                if lineup and 'players' in lineup:
                    pos_key_to_replace = None
                    for pos_key, p_info in lineup['players'].items():
                        p_id = p_info.get('id') if p_info else None
                        if p_id is not None and ((jugador and int(p_id) == jugador.id) or (ficha_sale and int(p_id) == ficha_sale.id)):
                            pos_key_to_replace = pos_key
                            break
                    if pos_key_to_replace is not None and jugador_entra:
                        lineup['players'][pos_key_to_replace] = {
                            'id': ficha_entra.id if ficha_entra else jugador_entra.id,
                            'nombre': jugador_entra.get_full_name() or jugador_entra.username,
                            'camiseta': str(ficha_entra.numero_camiseta) if (ficha_entra and ficha_entra.numero_camiseta) else '-'
                        }
                        if partido.equipo_local == equipo:
                            partido.alineacion_local = lineup
                        else:
                            partido.alineacion_visitante = lineup
                        partido.save()
        
        # Registrar evento
        evento = EventoPartido.objects.create(
            partido=partido,
            tipo=tipo,
            minuto=minuto,
            jugador=jugador,
            equipo=equipo,
            detalle=detalle_str
        )
        
        if tipo in ['amarilla', 'roja']:
            ficha = None
            if jugador:
                ficha = FichaJugador.objects.filter(user=jugador, equipo=equipo, torneo=partido.torneo).first()
                if not ficha:
                    ficha = FichaJugador.objects.filter(user=jugador, equipo=equipo).order_by('-id').first()

            if tipo == 'amarilla':
                if ficha:
                    # Contar amarillas en el torneo actual
                    amarillas_count = EventoPartido.objects.filter(
                        partido__torneo=partido.torneo,
                        tipo='amarilla',
                        jugador=jugador
                    ).count()
                    
                    limite = partido.torneo.limite_amarillas_suspension if partido.torneo else 3
                    if amarillas_count > 0 and amarillas_count % limite == 0:
                        ficha.partidos_suspension += 1
                        ficha.save()
                        messages.warning(request, f"⚠️ ¡ALERTA! El jugador ha acumulado {amarillas_count} amarillas y se le ha aplicado 1 partido de suspensión.")
            elif tipo == 'roja':
                if ficha:
                    ficha.partidos_suspension += 1
                    ficha.save()
                    messages.warning(request, f"🟥 ¡EXPULSIÓN! El jugador ha recibido tarjeta roja directa y se le aplica 1 partido de suspensión.")
        
        # Si es gol, sumamos al marcador
        if tipo == 'gol':
            if partido.equipo_local == equipo:
                partido.goles_local += 1
            else:
                partido.goles_visitante += 1
            partido.save()
            
        messages.success(request, f"Evento '{tipo.upper()}' registrado con éxito en el minuto {minuto}.")
        
    return redirect('match_day', partido_id=partido.id)


@login_required
def eliminar_evento(request, partido_id, evento_id):
    partido = get_object_or_404(Partido, id=partido_id, organizacion=request.organizacion)
    
    if request.user.role not in ['vocal', 'arbitro', 'superadmin', 'comision'] and not request.user.is_superuser:
        messages.error(request, "No estás autorizado para modificar los eventos de este partido.")
        return redirect('match_day', partido_id=partido.id)
        
    evento = get_object_or_404(EventoPartido, id=evento_id, partido=partido)
    tipo = str(evento.tipo).lower()
    jugador = evento.jugador
    equipo = evento.equipo

    # 1. Si era gol, restar del marcador
    if tipo == 'gol':
        if partido.equipo_local == equipo and partido.goles_local > 0:
            partido.goles_local -= 1
        elif partido.equipo_visitante == equipo and partido.goles_visitante > 0:
            partido.goles_visitante -= 1
        partido.save()

    # 2. Si era tarjeta, revertir suspensiones y eliminar multa asociada
    if tipo in ['amarilla', 'roja']:
        # Eliminar MultaTarjeta asociada si existe
        if hasattr(evento, 'multa_tarjeta') and evento.multa_tarjeta:
            evento.multa_tarjeta.delete()
        else:
            MultaTarjeta.objects.filter(evento=evento).delete()

        if jugador and partido.torneo:
            ficha = FichaJugador.objects.filter(user=jugador, equipo=equipo, torneo=partido.torneo).first()
            if not ficha:
                ficha = FichaJugador.objects.filter(user=jugador, equipo=equipo).order_by('-id').first()
            if ficha and ficha.partidos_suspension > 0:
                if tipo == 'amarilla':
                    limite = partido.torneo.limite_amarillas_suspension or 3
                    total_amarillas = EventoPartido.objects.filter(
                        partido__torneo=partido.torneo,
                        tipo__in=['amarilla', 'AMARILLA'],
                        jugador=jugador
                    ).count()
                    if total_amarillas % limite == 0:
                        ficha.partidos_suspension = max(0, ficha.partidos_suspension - 1)
                        ficha.save()
                elif tipo == 'roja':
                    ficha.partidos_suspension = max(0, ficha.partidos_suspension - 1)
                    ficha.save()

    evento.delete()
    messages.success(request, f"Incidencia '{tipo.upper()}' eliminada y corregida del acta del partido.")
    return redirect('match_day', partido_id=partido.id)


@login_required
def cerrar_partido(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    
    if request.user.role not in ['vocal', 'arbitro', 'superadmin'] or (
        partido.vocal != request.user and partido.arbitro != request.user and request.user.role != 'superadmin'
    ):
        messages.error(request, "No estás autorizado para cerrar este partido.")
        return redirect('vocalia_dashboard')
        
    if request.method == 'POST':
        # Validar y guardar firma de acuerdo a la persona autenticada
        if request.user.role == 'vocal':
            firma_vocal_data = request.POST.get('firma_vocal_data')
            if firma_vocal_data:
                partido.firma_vocal = True
                partido.firma_vocal_img = firma_vocal_data
                if partido.estado != 'finalizado':
                    _descontar_suspensiones(partido)
                partido.estado = 'finalizado'
                partido.save()
                messages.success(request, "Acta de partido cerrada y firmada exitosamente por el Vocal de Mesa.")
                return redirect('vocalia_dashboard')
            else:
                messages.error(request, "La firma manuscrita del Vocal es obligatoria.")
                
        elif request.user.role == 'arbitro':
            firma_arbitro_data = request.POST.get('firma_arbitro_data')
            if firma_arbitro_data:
                partido.firma_arbitro_img = firma_arbitro_data
                if partido.estado != 'finalizado':
                    _descontar_suspensiones(partido)
                partido.estado = 'finalizado'
                partido.save()
                messages.success(request, "Acta de partido cerrada y firmada exitosamente por el Árbitro.")
                return redirect('vocalia_dashboard')
            else:
                messages.error(request, "La firma manuscrita del Árbitro es obligatoria.")
                
        elif request.user.role == 'superadmin':
            # Superadmin puede cerrar con cualquiera de las firmas disponibles
            firma_vocal_data = request.POST.get('firma_vocal_data')
            firma_arbitro_data = request.POST.get('firma_arbitro_data')
            
            if firma_vocal_data:
                partido.firma_vocal = True
                partido.firma_vocal_img = firma_vocal_data
            if firma_arbitro_data:
                partido.firma_arbitro_img = firma_arbitro_data
                
            if partido.estado != 'finalizado':
                _descontar_suspensiones(partido)
            partido.estado = 'finalizado'
            partido.save()
            messages.success(request, "Acta de partido cerrada y finalizada por el Administrador.")
            return redirect('vocalia_dashboard')
            
    return redirect('match_day', partido_id=partido.id)


def _descontar_suspensiones(partido):
    # Todos los jugadores de estos equipos que estén suspendidos descuentan 1 partido cumplido
    fichas_suspendidas = FichaJugador.objects.filter(
        Q(equipo=partido.equipo_local) | Q(equipo=partido.equipo_visitante),
        torneo=partido.torneo,
        partidos_suspension__gt=0
    )
    for ficha in fichas_suspendidas:
        ficha.partidos_suspension -= 1
        ficha.save()


@login_required
def anular_o_reabrir_partido(request, partido_id):
    """
    Anula o restablece un partido que fue iniciado, finalizado o con datos registrados por error,
    regresándolo a su estado original 'programado' para que pueda disputarse o jugarse nuevamente.
    - Revierte el marcador a 0 - 0.
    - Elimina todos los eventos (goles, tarjetas, cambios).
    - Revierte las sanciones/suspensiones causadas por tarjetas en este partido.
    - Si el partido estaba finalizado, restaura las suspensiones previas que habían sido descontadas.
    - Elimina las multas financieras generadas por este partido o sus incidencias.
    - Limpia las firmas digitales del acta y alineaciones en vivo.
    - Registra la auditoría en BitacoraTorneo.
    """
    partido = get_object_or_404(Partido, id=partido_id, organizacion=request.organizacion)
    
    is_admin = request.user.role in ['superadmin', 'comision'] or request.user.is_superuser
    is_assigned_staff = (partido.vocal == request.user or partido.arbitro == request.user)
    
    if not (is_admin or is_assigned_staff):
        messages.error(request, "No estás autorizado para anular o restablecer este partido.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '').strip()
        if not motivo:
            motivo = "Partido anulado / reiniciado por error de digitación o no disputado aún"
            
        with transaction.atomic():
            valores_anteriores = {
                'estado': partido.estado,
                'goles_local': partido.goles_local,
                'goles_visitante': partido.goles_visitante,
                'total_eventos': partido.eventos.count(),
                'firma_vocal': partido.firma_vocal,
            }
            
            # Obtener todas las fichas de los jugadores de ambos equipos para este torneo
            fichas_ambos_equipos = FichaJugador.objects.filter(
                Q(equipo=partido.equipo_local) | Q(equipo=partido.equipo_visitante),
                torneo=partido.torneo
            )
            
            # 1. Gestionar tarjetas y suspensiones
            eventos_tarjeta = list(partido.eventos.filter(tipo__in=['amarilla', 'roja']))
            jugadores_sancionados_este_partido = set()
            limite = partido.torneo.limite_amarillas_suspension if partido.torneo else 3
            
            for ev in eventos_tarjeta:
                if ev.tipo == 'roja':
                    jugadores_sancionados_este_partido.add(ev.jugador_id)
                elif ev.tipo == 'amarilla':
                    total_amarillas = EventoPartido.objects.filter(
                        partido__torneo=partido.torneo,
                        tipo__in=['amarilla', 'AMARILLA'],
                        jugador=ev.jugador
                    ).count()
                    if total_amarillas > 0 and total_amarillas % limite == 0:
                        jugadores_sancionados_este_partido.add(ev.jugador_id)
            
            if partido.estado == 'finalizado':
                # El partido fue cerrado, por lo que _descontar_suspensiones restó 1 a quienes tenían partidos_suspension > 0.
                # Restaurar +1 a los jugadores que tenían suspensión previa y cuyo partido en realidad no se disputó
                for ficha in fichas_ambos_equipos:
                    if ficha.user_id not in jugadores_sancionados_este_partido:
                        if ficha.partidos_suspension > 0:
                            ficha.partidos_suspension += 1
                            ficha.save()
                        else:
                            rojas_prev = EventoPartido.objects.filter(
                                partido__torneo=partido.torneo, 
                                tipo__in=['roja', 'ROJA'], 
                                jugador=ficha.user
                            ).exclude(partido=partido).count()
                            
                            amarillas_prev = EventoPartido.objects.filter(
                                partido__torneo=partido.torneo, 
                                tipo__in=['amarilla', 'AMARILLA'], 
                                jugador=ficha.user
                            ).exclude(partido=partido).count()
                            
                            sanciones_prev = rojas_prev + (amarillas_prev // limite)
                            if sanciones_prev > 0:
                                ficha.partidos_suspension += 1
                                ficha.save()
            else:
                # El partido no estaba finalizado, pero pudo haber sumado suspensiones por tarjetas en vivo
                for jugador_id in jugadores_sancionados_este_partido:
                    ficha = fichas_ambos_equipos.filter(user_id=jugador_id).first()
                    if ficha and ficha.partidos_suspension > 0:
                        ficha.partidos_suspension = max(0, ficha.partidos_suspension - 1)
                        ficha.save()
            
            # 2. Eliminar multas financieras asociadas a este partido o sus incidencias
            MultaTarjeta.objects.filter(partido=partido).delete()
            MultaTarjeta.objects.filter(evento__partido=partido).delete()
            
            # 3. Eliminar todas las incidencias/eventos del partido
            partido.eventos.all().delete()
            
            # 4. Restablecer marcador y estado del partido
            partido.goles_local = 0
            partido.goles_visitante = 0
            partido.estado = 'programado'
            
            # 5. Limpiar firmas digitales y alineaciones
            partido.firma_vocal = False
            partido.firma_capitan_local = False
            partido.firma_capitan_visitante = False
            partido.firma_vocal_img = None
            partido.firma_arbitro_img = None
            partido.firma_entrenador_local_img = None
            partido.firma_entrenador_visitante_img = None
            partido.alineacion_local = dict()
            partido.alineacion_visitante = dict()
            partido.save()
            
            # 6. Auditoría en BitacoraTorneo
            if partido.torneo:
                BitacoraTorneo.objects.create(
                    organizacion=request.organizacion,
                    torneo=partido.torneo,
                    usuario=request.user,
                    accion="Anulación / Reinicio de Partido",
                    detalles=f"Se anuló y restableció a 'Programado' el partido #{partido.id} ({partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}). Marcador previo: {valores_anteriores['goles_local']}-{valores_anteriores['goles_visitante']}. Eventos eliminados: {valores_anteriores['total_eventos']}. Motivo: {motivo}",
                    valores_anteriores=valores_anteriores,
                    valores_nuevos={'estado': 'programado', 'goles_local': 0, 'goles_visitante': 0}
                )
                
        messages.success(
            request, 
            f"El partido #{partido.id} ({partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}) fue ANULADO y restablecido a 'Programado' exitosamente. El marcador volvió a 0-0 y las incidencias/multas fueron eliminadas para que pueda disputarse de nuevo."
        )
        
        # Redirección inteligente
        next_url = request.POST.get('next')
        if next_url and 'vocalia/' not in next_url:
            return redirect(next_url)
            
        if request.user.role == 'vocal':
            return redirect('vocalia_dashboard')
            
        if partido.torneo:
            if partido.torneo.tipo == 'personalizado':
                return redirect('ver_fixture_personalizado', torneo_id=partido.torneo.id)
            return redirect('detalle_torneo', torneo_id=partido.torneo.id)
            
        return redirect('partidos_lista')
        
    return redirect('detalle_partido', partido_id=partido.id)


@login_required
def notificar_whatsapp_mock(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    
    # Simulación de envío de WhatsApp recordatorio
    arbitro_nombre = partido.arbitro.get_full_name() if partido.arbitro else "Árbitro no asignado"
    arbitro_tel = partido.arbitro.telefono if (partido.arbitro and partido.arbitro.telefono) else "Sin número"
    
    vocal_nombre = partido.vocal.get_full_name() if partido.vocal else "Vocal no asignado"
    vocal_tel = partido.vocal.telefono if (partido.vocal and partido.vocal.telefono) else "Sin número"
    
    dt_local = partido.equipo_local.get_dt_name()
    dt_local_tel = partido.equipo_local.get_dt_telefono() or "Sin número"
    
    dt_vis = partido.equipo_visitante.get_dt_name()
    dt_vis_tel = partido.equipo_visitante.get_dt_telefono() or "Sin número"
    
    # Obtener jugadores habilitados
    jugadores_local_count = FichaJugador.objects.filter(equipo=partido.equipo_local, torneo=partido.torneo, estado_validacion='aprobado').count()
    jugadores_visitante_count = FichaJugador.objects.filter(equipo=partido.equipo_visitante, torneo=partido.torneo, estado_validacion='aprobado').count()
    
    messages.info(
        request, 
        f"📱 [WhatsApp API Mock]: Mensajes de confirmación enviados exitosamente:\n\n"
        f"➔ Árbitro: {arbitro_nombre} (Tel: {arbitro_tel}) - 'Recordatorio: Tienes asignado el partido {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre} el {partido.fecha_hora.strftime('%d/%m/%Y a las %H:%M')} en {partido.estadio}. Por favor, confirma asistencia.'\n\n"
        f"➔ Vocal de Mesa: {vocal_nombre} (Tel: {vocal_tel}) - 'Recordatorio: Tienes asignado el control de mesa digital del partido {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}. Por favor, confirma asistencia.'\n\n"
        f"➔ Entrenador {partido.equipo_local.nombre}: {dt_local} (Tel: {dt_local_tel}) - 'Notificación: Su encuentro contra {partido.equipo_visitante.nombre} está programado para el {partido.fecha_hora.strftime('%d/%m/%Y a las %H:%M')}.'\n\n"
        f"➔ Entrenador {partido.equipo_visitante.nombre}: {dt_vis} (Tel: {dt_vis_tel}) - 'Notificación: Su encuentro contra {partido.equipo_local.nombre} está programado para el {partido.fecha_hora.strftime('%d/%m/%Y a las %H:%M')}.'\n\n"
        f"➔ Jugadores habilitados: {jugadores_local_count} de {partido.equipo_local.nombre} y {jugadores_visitante_count} de {partido.equipo_visitante.nombre} notificados vía SMS/Push."
    )
    return redirect('partidos_lista')


@login_required
def editar_partido(request, partido_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para editar partidos.")
        return redirect('partidos_lista')
        
    partido = get_object_or_404(Partido, id=partido_id)
    
    if request.method == 'POST':
        fecha_hora = request.POST.get('fecha_hora')
        estadio = request.POST.get('estadio')
        arbitro_id = request.POST.get('arbitro')
        vocal_id = request.POST.get('vocal')
        
        if fecha_hora:
            partido.fecha_hora = fecha_hora
        if estadio:
            partido.estadio = estadio.strip()
            org = getattr(request, 'organizacion', None) or partido.organizacion
            partido.estadio_fk = Estadio.buscar_por_nombre(org, estadio)
            
        if arbitro_id:
            partido.arbitro = User.objects.get(id=arbitro_id)
        else:
            partido.arbitro = None
            
        if vocal_id:
            partido.vocal = User.objects.get(id=vocal_id)
        else:
            partido.vocal = None
            
        partido.save()
        messages.success(request, f"¡Partido {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre} actualizado correctamente!")
        return redirect('partidos_lista')
        
    # Obtener usuarios de la organización actual para asignar
    arbitros = User.objects.filter(role__in=['arbitro', 'superadmin', 'comision'], organizaciones__organizacion=request.organizacion).distinct().order_by('first_name', 'last_name')
    vocales = User.objects.filter(role__in=['vocal', 'superadmin', 'comision'], organizaciones__organizacion=request.organizacion).distinct().order_by('first_name', 'last_name')
    estadios = Estadio.objects.filter(organizacion=request.organizacion, activo=True).order_by('nombre')
    
    context = {
        'partido': partido,
        'arbitros': arbitros,
        'vocales': vocales,
        'estadios': estadios,
    }
    return render(request, 'matches/editar_partido.html', context)


@login_required
def detalle_partido(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    eventos = EventoPartido.objects.filter(partido=partido).select_related('jugador', 'equipo').order_by('minuto', 'id')
    
    # Obtener jugadores alineados de cada equipo que están habilitados en este torneo (para otras vistas si se usan)
    jugadores_local = FichaJugador.objects.filter(equipo=partido.equipo_local, torneo=partido.torneo, estado_validacion='aprobado').select_related('user')
    jugadores_visitante = FichaJugador.objects.filter(equipo=partido.equipo_visitante, torneo=partido.torneo, estado_validacion='aprobado').select_related('user')
    
    # Preparar lookup de fichas para la cronología
    user_ids = [ev.jugador_id for ev in eventos if ev.jugador_id]
    fichas_todas = FichaJugador.objects.filter(user_id__in=user_ids).select_related('user')
    
    fichas_lookup = {}
    for ficha in fichas_todas:
        # Priorizar fichas que pertenecen al torneo actual
        if ficha.user_id not in fichas_lookup or ficha.torneo_id == partido.torneo_id:
            fichas_lookup[ficha.user_id] = ficha
        
    eventos_local = []
    eventos_visitante = []
    
    for ev in eventos:
        if ev.jugador_id and ev.jugador_id in fichas_lookup:
            ev.ficha_jugador = fichas_lookup[ev.jugador_id]
        else:
            ev.ficha_jugador = None
            
        if ev.equipo == partido.equipo_local:
            eventos_local.append(ev)
        elif ev.equipo == partido.equipo_visitante:
            eventos_visitante.append(ev)
    
    context = {
        'partido': partido,
        'eventos': eventos, # Retenemos por compatibilidad si algo lo usa
        'eventos_local': eventos_local,
        'eventos_visitante': eventos_visitante,
        'jugadores_local': jugadores_local,
        'jugadores_visitante': jugadores_visitante,
    }
    return render(request, 'matches/detalle_partido.html', context)


@login_required
def imprimir_acta_partido(request, partido_id):
    """
    Vista especializada para generar e imprimir la Hoja de Vocalía / Acta Oficial de Partido.
    Diseñada en formato de alta calidad editorial sin menús ni elementos del sistema,
    con logotipo institucional, marcador, autoridades, alineaciones, incidencias y firmas.
    """
    partido = get_object_or_404(Partido, id=partido_id)
    organizacion = getattr(request, 'organizacion', None) or partido.organizacion
    eventos = EventoPartido.objects.filter(partido=partido).select_related('jugador', 'equipo').order_by('minuto', 'id')
    
    # Jugadores inscritos/habilitados de cada equipo
    jugadores_local_qs = FichaJugador.objects.filter(
        equipo=partido.equipo_local, 
        torneo=partido.torneo, 
        estado_validacion='aprobado'
    ).select_related('user').order_by('numero_camiseta', 'user__last_name', 'user__first_name')
    if not jugadores_local_qs.exists():
        jugadores_local_qs = FichaJugador.objects.filter(
            equipo=partido.equipo_local,
            estado_validacion='aprobado'
        ).select_related('user').order_by('numero_camiseta', 'user__last_name', 'user__first_name')
        
    jugadores_visitante_qs = FichaJugador.objects.filter(
        equipo=partido.equipo_visitante, 
        torneo=partido.torneo, 
        estado_validacion='aprobado'
    ).select_related('user').order_by('numero_camiseta', 'user__last_name', 'user__first_name')
    if not jugadores_visitante_qs.exists():
        jugadores_visitante_qs = FichaJugador.objects.filter(
            equipo=partido.equipo_visitante,
            estado_validacion='aprobado'
        ).select_related('user').order_by('numero_camiseta', 'user__last_name', 'user__first_name')

    stats_local = {}
    stats_visitante = {}
    eventos_local = []
    eventos_visitante = []
    
    total_goles_local = 0
    total_goles_visitante = 0
    total_amarillas_local = 0
    total_amarillas_visitante = 0
    total_rojas_local = 0
    total_rojas_visitante = 0
    
    user_ids = [ev.jugador_id for ev in eventos if ev.jugador_id]
    fichas_todas = FichaJugador.objects.filter(user_id__in=user_ids).select_related('user')
    fichas_lookup = {}
    for f in fichas_todas:
        if f.user_id not in fichas_lookup or f.torneo_id == partido.torneo_id:
            fichas_lookup[f.user_id] = f

    for ev in eventos:
        if ev.jugador_id and ev.jugador_id in fichas_lookup:
            ev.ficha_jugador = fichas_lookup[ev.jugador_id]
        else:
            ev.ficha_jugador = None
            
        es_local = (ev.equipo_id == partido.equipo_local_id)
        if es_local:
            eventos_local.append(ev)
            if ev.tipo == 'gol':
                total_goles_local += 1
            elif ev.tipo == 'amarilla':
                total_amarillas_local += 1
            elif ev.tipo == 'roja':
                total_rojas_local += 1
        elif ev.equipo_id == partido.equipo_visitante_id:
            eventos_visitante.append(ev)
            if ev.tipo == 'gol':
                total_goles_visitante += 1
            elif ev.tipo == 'amarilla':
                total_amarillas_visitante += 1
            elif ev.tipo == 'roja':
                total_rojas_visitante += 1
                
        target_dict = stats_local if es_local else stats_visitante
        if ev.jugador_id:
            if ev.jugador_id not in target_dict:
                target_dict[ev.jugador_id] = {'goles': [], 'amarillas': [], 'rojas': [], 'cambios': []}
            if ev.tipo == 'gol':
                target_dict[ev.jugador_id]['goles'].append(ev.minuto)
            elif ev.tipo == 'amarilla':
                target_dict[ev.jugador_id]['amarillas'].append(ev.minuto)
            elif ev.tipo == 'roja':
                target_dict[ev.jugador_id]['rojas'].append(ev.minuto)
            elif ev.tipo == 'cambio':
                target_dict[ev.jugador_id]['cambios'].append(ev.minuto)

    lista_jugadores_local = []
    for f in jugadores_local_qs:
        st = stats_local.get(f.user_id, {'goles': [], 'amarillas': [], 'rojas': [], 'cambios': []})
        lista_jugadores_local.append({
            'ficha': f,
            'goles': st['goles'],
            'amarillas': st['amarillas'],
            'rojas': st['rojas'],
            'cambios': st['cambios'],
            'tiene_incidencias': bool(st['goles'] or st['amarillas'] or st['rojas'] or st['cambios']),
        })
        
    lista_jugadores_visitante = []
    for f in jugadores_visitante_qs:
        st = stats_visitante.get(f.user_id, {'goles': [], 'amarillas': [], 'rojas': [], 'cambios': []})
        lista_jugadores_visitante.append({
            'ficha': f,
            'goles': st['goles'],
            'amarillas': st['amarillas'],
            'rojas': st['rojas'],
            'cambios': st['cambios'],
            'tiene_incidencias': bool(st['goles'] or st['amarillas'] or st['rojas'] or st['cambios']),
        })

    dt_local = partido.equipo_local.get_dt_name()
    dt_visitante = partido.equipo_visitante.get_dt_name()

    context = {
        'partido': partido,
        'organizacion': organizacion,
        'eventos': eventos,
        'eventos_local': eventos_local,
        'eventos_visitante': eventos_visitante,
        'jugadores_local': lista_jugadores_local,
        'jugadores_visitante': lista_jugadores_visitante,
        'total_goles_local': total_goles_local if total_goles_local > 0 else partido.goles_local,
        'total_goles_visitante': total_goles_visitante if total_goles_visitante > 0 else partido.goles_visitante,
        'total_amarillas_local': total_amarillas_local,
        'total_amarillas_visitante': total_amarillas_visitante,
        'total_rojas_local': total_rojas_local,
        'total_rojas_visitante': total_rojas_visitante,
        'dt_local': dt_local,
        'dt_visitante': dt_visitante,
        'fecha_impresion': timezone.now(),
        'codigo_acta': f"ACTA-{partido.id:05d}-J{partido.jornada}",
    }
    return render(request, 'matches/imprimir_acta_partido.html', context)


@login_required
def gestion_arbitros(request):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para acceder a la gestión de árbitros.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        form = ArbitroForm(request.POST)
        if form.is_valid():
            arbitro = form.save()
            from users.models import UsuarioOrganizacion
            UsuarioOrganizacion.objects.create(
                usuario=arbitro,
                organizacion=request.organizacion,
                rol='arbitro'
            )
            messages.success(request, f"Árbitro '{arbitro.get_full_name() or arbitro.username}' registrado exitosamente.")
            return redirect('gestion_arbitros')
        else:
            messages.error(request, "Error al registrar al árbitro. Por favor, revisa los datos ingresados.")
    else:
        form = ArbitroForm()
        
    arbitros = User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct().order_by('first_name', 'last_name')
    
    context = {
        'form': form,
        'arbitros': arbitros,
    }
    return render(request, 'matches/gestion_arbitros.html', context)


@login_required
def eliminar_arbitro(request, arbitro_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para eliminar árbitros.")
        return redirect('partidos_lista')
        
    arbitro = get_object_or_404(User, id=arbitro_id, role='arbitro', organizaciones__organizacion=request.organizacion)
    
    if request.method == 'POST':
        nombre_arbitro = arbitro.get_full_name() or arbitro.username
        arbitro.delete()
        messages.warning(request, f"El árbitro '{nombre_arbitro}' ha sido eliminado del sistema.")
        return redirect('gestion_arbitros')
        
    return redirect('gestion_arbitros')


@login_required
def editar_arbitro(request, arbitro_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para editar árbitros.")
        return redirect('gestion_arbitros')
        
    arbitro = get_object_or_404(User, id=arbitro_id, role='arbitro', organizaciones__organizacion=request.organizacion)
    
    if request.method == 'POST':
        form = ArbitroEdicionForm(request.POST, instance=arbitro)
        if form.is_valid():
            form.save()
            messages.success(request, f"Árbitro '{arbitro.get_full_name() or arbitro.username}' actualizado exitosamente.")
            return redirect('gestion_arbitros')
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al actualizar árbitro: {' | '.join(error_details)}")
    else:
        form = ArbitroEdicionForm(instance=arbitro)
        
    context = {
        'form': form,
        'arbitro': arbitro,
    }
    return render(request, 'matches/editar_arbitro.html', context)


@login_required
def gestion_vocales(request):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para acceder a la gestión de vocales de mesa.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        form = VocalForm(request.POST)
        if form.is_valid():
            vocal = form.save()
            from users.models import UsuarioOrganizacion
            UsuarioOrganizacion.objects.create(
                usuario=vocal,
                organizacion=request.organizacion,
                rol='vocal'
            )
            messages.success(request, f"Vocal de Mesa '{vocal.get_full_name() or vocal.username}' registrado exitosamente.")
            return redirect('gestion_vocales')
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al registrar al vocal de mesa: {' | '.join(error_details)}")
    else:
        form = VocalForm()
        
    vocales = User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct().order_by('first_name', 'last_name')
    
    context = {
        'form': form,
        'vocales': vocales,
    }
    return render(request, 'matches/gestion_vocales.html', context)


@login_required
def editar_vocal(request, vocal_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para editar vocales de mesa.")
        return redirect('gestion_vocales')
        
    vocal = get_object_or_404(User, id=vocal_id, role='vocal', organizaciones__organizacion=request.organizacion)
    
    if request.method == 'POST':
        form = VocalEdicionForm(request.POST, instance=vocal)
        if form.is_valid():
            form.save()
            messages.success(request, f"Vocal de mesa '{vocal.get_full_name() or vocal.username}' actualizado exitosamente.")
            return redirect('gestion_vocales')
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al actualizar vocal: {' | '.join(error_details)}")
    else:
        form = VocalEdicionForm(instance=vocal)
        
    context = {
        'form': form,
        'vocal': vocal,
    }
    return render(request, 'matches/editar_vocal.html', context)


@login_required
def eliminar_vocal(request, vocal_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para eliminar vocales de mesa.")
        return redirect('partidos_lista')
        
    vocal = get_object_or_404(User, id=vocal_id, role='vocal', organizaciones__organizacion=request.organizacion)
    
    if request.method == 'POST':
        nombre_vocal = vocal.get_full_name() or vocal.username
        vocal.delete()
        messages.warning(request, f"El vocal de mesa '{nombre_vocal}' ha sido eliminado del sistema.")
        return redirect('gestion_vocales')
        
    return redirect('gestion_vocales')


@login_required
def gestion_torneos(request):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para acceder a la gestión de torneos.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        form = TorneoForm(request.POST, organizacion=request.organizacion)
        if form.is_valid():
            torneo = form.save(commit=False)
            torneo.organizacion = request.organizacion
            torneo.save()
            form.save_m2m()
            messages.success(request, f"Torneo/Liga '{torneo.nombre}' creado exitosamente.")
            return redirect('gestion_torneos')
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al crear el torneo: {' | '.join(error_details)}")
    else:
        form = TorneoForm(organizacion=request.organizacion)
        
    torneos = Torneo.objects.filter(organizacion=request.organizacion).order_by('-fecha_creacion')
    
    context = {
        'form': form,
        'torneos': torneos,
    }
    return render(request, 'matches/gestion_torneos.html', context)


@login_required
def detalle_torneo(request, torneo_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para ver el detalle de gestión del torneo.")
        return redirect('partidos_lista')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
    if torneo.tipo == 'personalizado':
        return redirect('panel_torneo_personalizado', torneo_id=torneo.id)
    equipos = torneo.equipos.all()
    partidos = Partido.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'vocal', 'arbitro').order_by('jornada', 'fecha_hora')
    
    todos_equipos = Equipo.objects.filter(categoria=torneo.categoria).order_by('nombre')
    todos_arbitros = User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct().order_by('first_name', 'last_name')
    todos_vocales = User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct().order_by('first_name', 'last_name')
    
    # Agrupar partidos por fase o fecha para el UI
    partidos_regular = partidos.filter(fase='regular')
    partidos_grupos = partidos.filter(fase='grupos')
    partidos_dieciseisavos = partidos.filter(fase='dieciseisavos')
    partidos_octavos = partidos.filter(fase='octavos')
    partidos_cuartos = partidos.filter(fase='cuartos')
    partidos_semis = partidos.filter(fase='semifinal')
    partidos_final = partidos.filter(fase='final')
    
    # Si es liga, agrupar por jornada
    partidos_por_jornada = {}
    if torneo.tipo == 'liga':
        for p in partidos:
            partidos_por_jornada.setdefault(p.jornada, []).append(p)
            
    # Equipos no asignados a este torneo que pertenezcan a la categoría del torneo
    equipos_candidatos = Equipo.objects.filter(organizacion=request.organizacion).exclude(id__in=equipos.values_list('id', flat=True))
    equipos_no_asignados = [eq for eq in equipos_candidatos if eq.pertenece_a_categoria(torneo.categoria)]
    
    # Manejar POST para asignar equipos manualmente
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'agregar_equipo':
            equipo_id = request.POST.get('equipo_id')
            if equipo_id:
                equipo = get_object_or_404(Equipo, id=equipo_id)
                if torneo.categoria and not equipo.pertenece_a_categoria(torneo.categoria):
                    messages.error(request, f"El equipo '{equipo.nombre}' ({equipo.get_categoria_display()}) no pertenece a la categoría de este torneo ({torneo.get_categoria_display()}).")
                else:
                    torneo.equipos.add(equipo)
                    messages.success(request, f"Equipo '{equipo.nombre}' asignado al torneo '{torneo.nombre}'.")
                return redirect('detalle_torneo', torneo_id=torneo.id)
        elif action == 'quitar_equipo':
            equipo_id = request.POST.get('equipo_id')
            if equipo_id:
                equipo = get_object_or_404(Equipo, id=equipo_id)
                # Verificar si tiene partidos
                if Partido.objects.filter(torneo=torneo).filter(Q(equipo_local=equipo) | Q(equipo_visitante=equipo)).exists():
                    messages.error(request, f"No puedes quitar a '{equipo.nombre}' porque ya tiene partidos registrados en este torneo.")
                else:
                    torneo.equipos.remove(equipo)
                    messages.warning(request, f"Equipo '{equipo.nombre}' retirado del torneo.")
                return redirect('detalle_torneo', torneo_id=torneo.id)
                
    context = {
        'torneo': torneo,
        'equipos': equipos,
        'partidos': partidos,
        'total_partidos': partidos.count(),
        'partidos_regular': partidos_regular,
        'partidos_grupos': partidos_grupos,
        'partidos_dieciseisavos': partidos_dieciseisavos,
        'partidos_octavos': partidos_octavos,
        'partidos_cuartos': partidos_cuartos,
        'partidos_semis': partidos_semis,
        'partidos_final': partidos_final,
        'partidos_por_jornada': sorted(partidos_por_jornada.items()),
        'todos_equipos': todos_equipos,
        'todos_arbitros': todos_arbitros,
        'todos_vocales': todos_vocales,
        'equipos_no_asignados': equipos_no_asignados,
        'estadios': Estadio.objects.filter(organizacion=request.organizacion, activo=True).order_by('nombre'),
        'torneo_edicion_form': TorneoEdicionForm(instance=torneo),
    }
    return render(request, 'matches/detalle_torneo.html', context)


@login_required
def imprimir_fixture_torneo(request, torneo_id):
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)
    equipos = torneo.equipos.all()
    partidos = Partido.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'vocal', 'arbitro').order_by('jornada', 'fecha_hora')
    
    jornada = request.GET.get('jornada')
    equipo_id = request.GET.get('equipo_id')
    estado = request.GET.get('estado')

    if jornada:
        partidos = partidos.filter(jornada=jornada)
    if equipo_id:
        partidos = partidos.filter(Q(equipo_local_id=equipo_id) | Q(equipo_visitante_id=equipo_id))
    if estado:
        partidos = partidos.filter(estado=estado)

    total_partidos = partidos.count()
    
    # Agrupar partidos por jornada si es liga
    partidos_por_jornada = {}
    if torneo.tipo == 'liga':
        for p in partidos:
            partidos_por_jornada.setdefault(p.jornada, []).append(p)
            
    # Agrupar partidos por grupo si es torneo de fases
    partidos_grupos = partidos.filter(fase='grupos')
    partidos_grupos_dict = {}
    if torneo.tipo == 'torneo' and partidos_grupos.exists():
        for p in partidos_grupos:
            g_name = p.grupo or "Fase de Grupos"
            partidos_grupos_dict.setdefault(g_name, []).append(p)
            
    # Agrupar eliminatorias
    partidos_eliminatorias = partidos.filter(fase__in=['dieciseisavos', 'octavos', 'cuartos', 'semifinal', 'final'])
    partidos_eliminatoria_dict = {}
    for p in partidos_eliminatorias:
        fase_display = p.get_fase_display()
        partidos_eliminatoria_dict.setdefault(fase_display, []).append(p)

    context = {
        'torneo': torneo,
        'equipos': equipos,
        'partidos': partidos,
        'total_partidos': total_partidos,
        'partidos_por_jornada': sorted(partidos_por_jornada.items()),
        'partidos_grupos_dict': sorted(partidos_grupos_dict.items()),
        'partidos_eliminatoria_dict': sorted(partidos_eliminatoria_dict.items()),
        'fecha_impresion': timezone.now(),
        'jornada_filtrada': jornada,
        'equipo_id_filtrado': equipo_id,
        'estado_filtrado': estado,
    }
    return render(request, 'matches/imprimir_fixture.html', context)


@login_required
def eliminar_torneo(request, torneo_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para eliminar torneos.")
        return redirect('partidos_lista')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
    if request.method == 'POST':
        nombre = torneo.nombre
        torneo.delete()
        messages.warning(request, f"El torneo/liga '{nombre}' ha sido eliminado permanentemente.")
        return redirect('gestion_torneos')
    return redirect('gestion_torneos')


@login_required
def generar_fixture_torneo(request, torneo_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para generar fixture.")
        return redirect('partidos_lista')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
    equipos = list(torneo.equipos.all())
    
    if len(equipos) < 2:
        messages.error(request, "Se necesitan al menos 2 equipos para generar el fixture.")
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
    # Obtener vocales y árbitros pertenecientes exclusivamente a esta organización
    vocales = list(User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct())
    arbitros = list(User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct())
    
    if not vocales:
        vocales = [None]
    if not arbitros:
        arbitros = [None]
        
    if request.method == 'POST':
        tipo_gen = request.POST.get('tipo_gen', 'liga')
        
        if request.POST.get('limpiar_existentes') == 'on':
            Partido.objects.filter(torneo=torneo, estado='programado').delete()
            
        if tipo_gen == 'liga' or torneo.tipo == 'liga':
            n = len(equipos)
            if n % 2 != 0:
                equipos.append(None)
                n += 1
                
            partidos_creados = 0
            fechas = n - 1
            partidos_por_fecha = n // 2
            
            fecha_inicial = timezone.now() + timedelta(days=1)
            
            for f in range(fechas):
                for p in range(partidos_por_fecha):
                    home = equipos[p]
                    away = equipos[n - 1 - p]
                    
                    if home is not None and away is not None:
                        if f % 2 == 1:
                            home, away = away, home
                            
                        vocal_asig = vocales[partidos_creados % len(vocales)]
                        arbitro_asig = arbitros[partidos_creados % len(arbitros)]
                        
                        hora_partido = fecha_inicial.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=f * 7, hours=p * 2)
                        
                        Partido.objects.create(
                            equipo_local=home,
                            equipo_visitante=away,
                            fecha_hora=hora_partido,
                            estadio="Campo Central",
                            vocal=vocal_asig,
                            arbitro=arbitro_asig,
                            jornada=f + 1,
                            temporada=torneo.temporada,
                            torneo=torneo,
                            fase='regular',
                            organizacion=torneo.organizacion or request.organizacion
                        )
                        partidos_creados += 1
                
                equipos = [equipos[0]] + [equipos[-1]] + equipos[1:-1]
                
            messages.success(request, f"Fixture de Liga generado exitosamente. Se crearon {partidos_creados} partidos en {fechas} jornadas.")
            
        elif tipo_gen == 'grupos':
            grupo_nombre = request.POST.get('grupo_nombre', 'Grupo A')
            equipos_grupo_ids = request.POST.getlist('equipos_grupo')
            
            equipos_grupo = [e for e in equipos if str(e.id) in equipos_grupo_ids]
            
            if len(equipos_grupo) < 2:
                messages.error(request, "Selecciona al menos 2 equipos para el grupo.")
                return redirect('detalle_torneo', torneo_id=torneo.id)
                
            n = len(equipos_grupo)
            if n % 2 != 0:
                equipos_grupo.append(None)
                n += 1
                
            partidos_creados = 0
            fechas = n - 1
            partidos_por_fecha = n // 2
            
            fecha_inicial = timezone.now() + timedelta(days=1)
            
            for f in range(fechas):
                for p in range(partidos_por_fecha):
                    home = equipos_grupo[p]
                    away = equipos_grupo[n - 1 - p]
                    
                    if home is not None and away is not None:
                        if f % 2 == 1:
                            home, away = away, home
                            
                        vocal_asig = vocales[partidos_creados % len(vocales)]
                        arbitro_asig = arbitros[partidos_creados % len(arbitros)]
                        
                        hora_partido = fecha_inicial.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=f * 7, hours=p * 2)
                        
                        Partido.objects.create(
                            equipo_local=home,
                            equipo_visitante=away,
                            fecha_hora=hora_partido,
                            estadio="Campo Central",
                            vocal=vocal_asig,
                            arbitro=arbitro_asig,
                            jornada=f + 1,
                            temporada=torneo.temporada,
                            torneo=torneo,
                            fase='grupos',
                            grupo=grupo_nombre,
                            organizacion=request.organizacion
                        )
                        partidos_creados += 1
                        
                equipos_grupo = [equipos_grupo[0]] + [equipos_grupo[-1]] + equipos_grupo[1:-1]
                
            messages.success(request, f"Fixture para '{grupo_nombre}' generado exitosamente. Se crearon {partidos_creados} partidos.")

        elif tipo_gen == 'todos_los_grupos':
            import random
            if not torneo.distribucion_grupos:
                num_grupos = max(2, torneo.numero_grupos or 2)
                group_names = [f"Grupo {chr(65 + i)}" for i in range(num_grupos)]
                equipos_shuffled = list(equipos)
                random.shuffle(equipos_shuffled)
                distribucion = {g: [] for g in group_names}
                for idx, eq in enumerate(equipos_shuffled):
                    distribucion[group_names[idx % num_grupos]].append(eq.id)
                torneo.distribucion_grupos = distribucion
                torneo.save()
                
            distribucion = torneo.distribucion_grupos
            partidos_totales = 0
            fecha_inicial = timezone.now() + timedelta(days=1)
            
            for g_name, eq_ids in distribucion.items():
                eqs_grupo = [e for e in equipos if e.id in eq_ids]
                if len(eqs_grupo) < 2:
                    continue
                n = len(eqs_grupo)
                if n % 2 != 0:
                    eqs_grupo.append(None)
                    n += 1
                fechas = n - 1
                partidos_por_fecha = n // 2
                for f in range(fechas):
                    for p in range(partidos_por_fecha):
                        home = eqs_grupo[p]
                        away = eqs_grupo[n - 1 - p]
                        if home is not None and away is not None:
                            if f % 2 == 1:
                                home, away = away, home
                            vocal_asig = vocales[partidos_totales % len(vocales)]
                            arbitro_asig = arbitros[partidos_totales % len(arbitros)]
                            hora_partido = fecha_inicial.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=f * 7, hours=(partidos_totales % 4) * 2)
                            Partido.objects.create(
                                equipo_local=home,
                                equipo_visitante=away,
                                fecha_hora=hora_partido,
                                estadio="Campo Central",
                                vocal=vocal_asig,
                                arbitro=arbitro_asig,
                                jornada=f + 1,
                                temporada=torneo.temporada,
                                torneo=torneo,
                                fase='grupos',
                                grupo=g_name,
                                organizacion=request.organizacion
                            )
                            partidos_totales += 1
                    eqs_grupo = [eqs_grupo[0]] + [eqs_grupo[-1]] + eqs_grupo[1:-1]
                    
            messages.success(request, f"Fixture multigrupo generado exitosamente. Se crearon {partidos_totales} partidos en todos los grupos.")
            
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
    return redirect('detalle_torneo', torneo_id=torneo.id)


@login_required
def sortear_grupos_torneo(request, torneo_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para administrar grupos.")
        return redirect('partidos_lista')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
    equipos = list(torneo.equipos.all())
    
    if len(equipos) < 2:
        messages.error(request, "Se necesitan al menos 2 equipos para realizar el sorteo de grupos.")
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
    import random
    num_grupos = max(2, torneo.numero_grupos or 2)
    group_names = [f"Grupo {chr(65 + i)}" for i in range(num_grupos)]
    
    random.shuffle(equipos)
    distribucion = {g: [] for g in group_names}
    for idx, eq in enumerate(equipos):
        g_name = group_names[idx % num_grupos]
        distribucion[g_name].append(eq.id)
        
    torneo.distribucion_grupos = distribucion
    torneo.save()
    
    messages.success(request, f"Se distribuyeron {len(equipos)} equipos en {num_grupos} grupos ({', '.join(group_names)}) exitosamente.")
    return redirect('detalle_torneo', torneo_id=torneo.id)


@login_required
def generar_cruces_eliminatorios(request, torneo_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para generar cruces de eliminatorias.")
        return redirect('partidos_lista')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
    vocales = list(User.objects.filter(role='vocal', organizaciones__organizacion=request.organizacion).distinct())
    arbitros = list(User.objects.filter(role='arbitro', organizaciones__organizacion=request.organizacion).distinct())
    
    if not vocales:
        vocales = [None]
    if not arbitros:
        arbitros = [None]

    # Calcular posiciones de cada grupo
    partidos_grupos = Partido.objects.filter(torneo=torneo, fase='grupos')
    grupos_dict = {}
    for p in partidos_grupos:
        g_name = p.grupo or "Grupo A"
        grupos_dict.setdefault(g_name, set()).add(p.equipo_local)
        grupos_dict.setdefault(g_name, set()).add(p.equipo_visitante)
        
    if not grupos_dict and torneo.distribucion_grupos:
        for g_name, eq_ids in torneo.distribucion_grupos.items():
            eqs = list(Equipo.objects.filter(id__in=eq_ids))
            if eqs:
                grupos_dict[g_name] = set(eqs)
                
    if not grupos_dict:
        messages.error(request, "No se encontraron grupos configurados ni partidos de grupo jugados.")
        return redirect('detalle_torneo', torneo_id=torneo.id)

    clasificados_por_grupo = {}
    num_clasifican = max(1, torneo.clasificados_por_grupo or 2)
    
    for g_name, eq_set in sorted(grupos_dict.items()):
        grupo_tabla = []
        for eq in eq_set:
            partidos_jugados = Partido.objects.filter(
                Q(equipo_local=eq) | Q(equipo_visitante=eq),
                torneo=torneo,
                fase='grupos',
                grupo=g_name,
                estado='finalizado'
            )
            
            pj = partidos_jugados.count()
            pg = pe = pp = gf = gc = 0
            for p in partidos_jugados:
                if p.equipo_local == eq:
                    gf += p.goles_local
                    gc += p.goles_visitante
                    if p.goles_local > p.goles_visitante: pg += 1
                    elif p.goles_local == p.goles_visitante: pe += 1
                    else: pp += 1
                else:
                    gf += p.goles_visitante
                    gc += p.goles_local
                    if p.goles_visitante > p.goles_local: pg += 1
                    elif p.goles_local == p.goles_visitante: pe += 1
                    else: pp += 1
            pts = (pg * 3) + pe
            gd = gf - gc
            grupo_tabla.append({
                'equipo': eq,
                'pts': pts,
                'gd': gd,
                'gf': gf
            })
        grupo_tabla = sorted(grupo_tabla, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
        clasificados_por_grupo[g_name] = [item['equipo'] for item in grupo_tabla[:num_clasifican]]

    g_names = sorted(list(clasificados_por_grupo.keys()))
    matchups = []
    
    for i in range(0, len(g_names), 2):
        g1 = g_names[i]
        g2 = g_names[i + 1] if i + 1 < len(g_names) else g_names[0]
        
        eqs1 = clasificados_por_grupo[g1]
        eqs2 = clasificados_por_grupo[g2]
        
        if len(eqs1) > 0 and len(eqs2) > 1:
            matchups.append((eqs1[0], eqs2[1]))
        elif len(eqs1) > 0 and len(eqs2) > 0:
            matchups.append((eqs1[0], eqs2[0]))
            
        if len(eqs2) > 0 and len(eqs1) > 1:
            matchups.append((eqs2[0], eqs1[1]))

    total_clasificados = len(matchups) * 2
    if total_clasificados > 16:
        fase_target = 'dieciseisavos'
    elif total_clasificados > 8:
        fase_target = 'octavos'
    elif total_clasificados > 4:
        fase_target = 'cuartos'
    elif total_clasificados > 2:
        fase_target = 'semifinal'
    else:
        fase_target = 'final'
        
    if torneo.fase_eliminatoria_inicial:
        fase_target = torneo.fase_eliminatoria_inicial

    Partido.objects.filter(torneo=torneo, fase=fase_target, estado='programado').delete()
    
    fecha_inicial = timezone.now() + timedelta(days=2)
    partidos_creados = 0
    for idx, (home, away) in enumerate(matchups):
        vocal_asig = vocales[idx % len(vocales)]
        arbitro_asig = arbitros[idx % len(arbitros)]
        hora_partido = fecha_inicial.replace(hour=15, minute=0, second=0, microsecond=0) + timedelta(hours=idx * 2)
        
        Partido.objects.create(
            equipo_local=home,
            equipo_visitante=away,
            fecha_hora=hora_partido,
            estadio="Estadio Principal",
            vocal=vocal_asig,
            arbitro=arbitro_asig,
            jornada=1,
            temporada=torneo.temporada,
            torneo=torneo,
            fase=fase_target,
            organizacion=request.organizacion
        )
        partidos_creados += 1

    messages.success(request, f"Cruces eliminatorios de {fase_target.upper()} generados exitosamente. Se crearon {partidos_creados} partidos de eliminación directa.")
    return redirect('detalle_torneo', torneo_id=torneo.id)


@login_required
def crear_partido_torneo(request, torneo_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para agregar partidos.")
        return redirect('partidos_lista')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
    
    if request.method == 'POST':
        eq_local_id = request.POST.get('equipo_local')
        eq_visitante_id = request.POST.get('equipo_visitante')
        fecha_hora = request.POST.get('fecha_hora')
        estadio = (request.POST.get('estadio') or 'Campo Principal').strip()
        org = getattr(request, 'organizacion', None) or torneo.organizacion
        estadio_obj = Estadio.buscar_por_nombre(org, estadio)
        vocal_id = request.POST.get('vocal')
        arbitro_id = request.POST.get('arbitro')
        fase = request.POST.get('fase', 'regular')
        grupo = request.POST.get('grupo')
        jornada = request.POST.get('jornada', '1')
        
        if eq_local_id == eq_visitante_id:
            messages.error(request, "El equipo local y visitante no pueden ser el mismo.")
            return redirect('detalle_torneo', torneo_id=torneo.id)
            
        eq_local = get_object_or_404(Equipo, id=eq_local_id)
        eq_visitante = get_object_or_404(Equipo, id=eq_visitante_id)
        vocal = User.objects.filter(id=vocal_id, role='vocal', organizaciones__organizacion=request.organizacion).first() if vocal_id else None
        arbitro = User.objects.filter(id=arbitro_id, role='arbitro', organizaciones__organizacion=request.organizacion).first() if arbitro_id else None
        
        Partido.objects.create(
            equipo_local=eq_local,
            equipo_visitante=eq_visitante,
            fecha_hora=fecha_hora,
            estadio=estadio,
            estadio_fk=estadio_obj,
            vocal=vocal,
            arbitro=arbitro,
            fase=fase,
            grupo=grupo if fase == 'grupos' else None,
            jornada=int(jornada) if jornada.isdigit() else 1,
            temporada=torneo.temporada,
            torneo=torneo,
            estado='programado',
            organizacion=torneo.organizacion or request.organizacion
        )
        
        messages.success(request, "Partido / Cruce de eliminatoria creado exitosamente.")
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
    return redirect('detalle_torneo', torneo_id=torneo.id)


@login_required
def estadisticas_torneo(request, torneo_id):
    from django.db.models import Count
    from matches.models import EventoPartido
    from teams.models import FichaJugador
    
    torneo = get_object_or_404(Torneo, id=torneo_id)
    
    def get_top_events(event_type):
        events = EventoPartido.objects.filter(
            partido__torneo=torneo, 
            tipo=event_type, 
            jugador__isnull=False
        ).values(
            'jugador__id', 
            'jugador__first_name', 
            'jugador__last_name', 
            'equipo__id',
            'equipo__nombre',
            'equipo__logo'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        stats = []
        for evt in events:
            # Primero intentar buscar la ficha asociada al torneo y equipo
            ficha = FichaJugador.objects.filter(
                user_id=evt['jugador__id'], 
                equipo_id=evt['equipo__id'], 
                torneo=torneo
            ).first()
            if not ficha:
                # Si no, buscar la ficha del jugador en ese equipo específico (retrocompatibilidad)
                ficha = FichaJugador.objects.filter(
                    user_id=evt['jugador__id'], 
                    equipo_id=evt['equipo__id']
                ).order_by('-id').first()
                
            numero_camiseta = ficha.numero_camiseta if ficha and ficha.numero_camiseta else '-'
            foto_url = ficha.foto.url if ficha and ficha.foto else None
            logo_url = '/media/' + evt['equipo__logo'] if evt['equipo__logo'] else None
            
            stats.append({
                'nombre_jugador': f"{evt['jugador__first_name']} {evt['jugador__last_name']}".strip(),
                'equipo': evt['equipo__nombre'],
                'numero_camiseta': numero_camiseta,
                'total': evt['total'],
                'foto_url': foto_url,
                'logo_url': logo_url
            })
        return stats

    top_goleadores = get_top_events('gol')
    top_asistidores = get_top_events('asistencia')
    top_amarillas = get_top_events('amarilla')
    top_rojas = get_top_events('roja')
        
    context = {
        'torneo': torneo,
        'top_goleadores': top_goleadores,
        'top_asistidores': top_asistidores,
        'top_amarillas': top_amarillas,
        'top_rojas': top_rojas
    }
    return render(request, 'matches/estadisticas_torneo.html', context)


@login_required
def gestion_estadios(request):
    if not (request.user.role in ['superadmin', 'comision', 'admin', 'organizador'] or request.user.has_module_access('estadios', request.organizacion)):
        messages.error(request, "No tienes autorización para acceder a la gestión de estadios.")
        return redirect('partidos_lista')

    if request.method == 'POST':
        form = EstadioForm(request.POST)
        if form.is_valid():
            estadio = form.save(commit=False)
            estadio.organizacion = request.organizacion
            estadio.save()
            messages.success(request, f"Estadio / Cancha '{estadio.nombre}' registrado con éxito.")
            return redirect('gestion_estadios')
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al registrar el estadio: {' | '.join(error_details)}")
    else:
        form = EstadioForm()

    estadios = Estadio.objects.filter(organizacion=request.organizacion).order_by('nombre')
    context = {
        'estadios': estadios,
        'form': form,
    }
    return render(request, 'matches/gestion_estadios.html', context)


@login_required
def editar_estadio(request, estadio_id):
    if not (request.user.role in ['superadmin', 'comision', 'admin', 'organizador'] or request.user.has_module_access('estadios', request.organizacion)):
        messages.error(request, "No tienes autorización para editar estadios.")
        return redirect('gestion_estadios')

    estadio = get_object_or_404(Estadio, id=estadio_id, organizacion=request.organizacion)
    if request.method == 'POST':
        form = EstadioForm(request.POST, instance=estadio)
        if form.is_valid():
            form.save()
            messages.success(request, f"Estadio '{estadio.nombre}' actualizado correctamente.")
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al actualizar el estadio: {' | '.join(error_details)}")
    return redirect('gestion_estadios')


@login_required
def eliminar_estadio(request, estadio_id):
    if not (request.user.role in ['superadmin', 'comision', 'admin', 'organizador'] or request.user.has_module_access('estadios', request.organizacion)):
        messages.error(request, "No tienes autorización para eliminar estadios.")
        return redirect('gestion_estadios')

    estadio = get_object_or_404(Estadio, id=estadio_id, organizacion=request.organizacion)
    if request.method == 'POST':
        nombre = estadio.nombre
        estadio.delete()
        messages.success(request, f"Estadio '{nombre}' eliminado correctamente.")
    return redirect('gestion_estadios')


@login_required
def editar_torneo(request, torneo_id):
    if not (request.user.role in ['superadmin', 'comision', 'admin', 'organizador'] or request.user.has_module_access('torneos', request.organizacion)):
        messages.error(request, "No tienes autorización para editar la configuración del torneo.")
        return redirect('gestion_torneos')

    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)

    if request.method == 'POST':
        form = TorneoEdicionForm(request.POST, instance=torneo)
        if form.is_valid():
            form.save()
            messages.success(
                request, 
                f"Configuración del torneo '{torneo.nombre}' actualizada exitosamente. "
                f"Costo amarilla: ${torneo.costo_amarilla} | Costo roja: ${torneo.costo_roja}."
            )
        else:
            error_details = []
            for field_name, errs in form.errors.items():
                label = form.fields[field_name].label if field_name in form.fields else field_name
                error_details.append(f"{label}: {', '.join(errs)}")
            messages.error(request, f"Error al actualizar el torneo: {' | '.join(error_details)}")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    if torneo.tipo == 'personalizado':
        return redirect('panel_torneo_personalizado', torneo_id=torneo.id)
    return redirect('detalle_torneo', torneo_id=torneo.id)

