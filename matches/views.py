from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from teams.models import Equipo, FichaJugador
from .models import Partido, EventoPartido, Torneo
from django.contrib.auth import get_user_model
from django.db.models import Q, F
from .forms import ArbitroForm, VocalForm, TorneoForm

User = get_user_model()


def partidos_lista(request):
    torneo_id = request.GET.get('torneo')
    torneos = Torneo.objects.all().order_by('-fecha_creacion')
    
    selected_torneo = None
    if torneo_id:
        selected_torneo = get_object_or_404(Torneo, id=torneo_id)
        partidos = Partido.objects.filter(torneo=selected_torneo).select_related('equipo_local', 'equipo_visitante').order_by('jornada', 'fecha_hora')
        equipos = selected_torneo.equipos.all()
    else:
        # Por defecto, si hay algún torneo, filtramos por el más reciente
        if torneos.exists():
            selected_torneo = torneos.first()
            partidos = Partido.objects.filter(torneo=selected_torneo).select_related('equipo_local', 'equipo_visitante').order_by('jornada', 'fecha_hora')
            equipos = selected_torneo.equipos.all()
        else:
            partidos = Partido.objects.all().select_related('equipo_local', 'equipo_visitante').order_by('jornada', 'fecha_hora')
            equipos = Equipo.objects.all()
    
    tabla_tipo = 'general'
    tabla_posiciones = []
    tablas_grupos = []
    
    if selected_torneo and selected_torneo.tipo == 'torneo':
        tabla_tipo = 'grupos'
        # Obtener todos los partidos de fase de grupos
        partidos_grupos = Partido.objects.filter(torneo=selected_torneo, fase='grupos')
        
        # Mapear qué equipos están en qué grupo
        grupos_dict = {}  # { 'Grupo A': set(equipos) }
        for p in partidos_grupos:
            g_name = p.grupo or "Grupo A"
            grupos_dict.setdefault(g_name, set()).add(p.equipo_local)
            grupos_dict.setdefault(g_name, set()).add(p.equipo_visitante)
            
        # Para cada grupo, calcular su tabla de posiciones
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
                pg = 0
                pe = 0
                pp = 0
                gf = 0
                gc = 0
                
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
                
                grupo_tabla.append({
                    'equipo': eq,
                    'pj': pj,
                    'pg': pg,
                    'pe': pe,
                    'pp': pp,
                    'gf': gf,
                    'gc': gc,
                    'gd': gd,
                    'pts': pts
                })
            
            grupo_tabla = sorted(grupo_tabla, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
            tablas_grupos.append({
                'grupo': g_name,
                'tabla': grupo_tabla
            })
    else:
        # Liga o sin torneo seleccionado (Tabla General)
        tabla_tipo = 'general'
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
            pg = 0
            pe = 0
            pp = 0
            gf = 0
            gc = 0
            
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
                'equipo': eq,
                'pj': pj,
                'pg': pg,
                'pe': pe,
                'pp': pp,
                'gf': gf,
                'gc': gc,
                'gd': gd,
                'pts': pts
            })
        
        tabla_posiciones = sorted(tabla_posiciones, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))

    context = {
        'partidos': partidos,
        'tabla': tabla_posiciones,
        'tablas_grupos': tablas_grupos,
        'tabla_tipo': tabla_tipo,
        'torneos': torneos,
        'selected_torneo': selected_torneo,
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
                    
                    # Asignar un vocal y árbitro de prueba al azar si existen en la BD
                    vocal = User.objects.filter(role='vocal').first()
                    arbitro = User.objects.filter(role='arbitro').first()
                    if not vocal:
                        vocal = User.objects.filter(is_superuser=True).first()
                    if not arbitro:
                        arbitro = User.objects.filter(is_superuser=True).first()

                    Partido.objects.create(
                        equipo_local=eq_local,
                        equipo_visitante=eq_vis,
                        fecha_hora=hora_partido,
                        estadio="Estadio Central de la Liga",
                        jornada=jornada,
                        temporada="Copa de Campeones 2026",
                        vocal=vocal,
                        arbitro=arbitro,
                        estado='programado'
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
        vocal=request.user
    ).exclude(estado='finalizado').select_related('equipo_local', 'equipo_visitante').order_by('fecha_hora')
    
    historial = Partido.objects.filter(
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
    
    if request.user.role not in ['vocal', 'superadmin'] or (partido.vocal != request.user and request.user.role != 'superadmin'):
        messages.error(request, "No estás asignado como vocal de este partido.")
        return redirect('vocalia_dashboard')
        
    # Si está programado, iniciamos el partido automáticamente al abrir la interfaz de campo
    if partido.estado == 'programado':
        partido.estado = 'en_curso'
        partido.save()
        messages.info(request, f"¡El partido entre {partido.equipo_local.nombre} y {partido.equipo_visitante.nombre} ha iniciado!")
        
    # Obtener jugadores habilitados (aprobados) de cada equipo
    jugadores_local = FichaJugador.objects.filter(equipo=partido.equipo_local, estado_validacion='aprobado').select_related('user')
    jugadores_visitante = FichaJugador.objects.filter(equipo=partido.equipo_visitante, estado_validacion='aprobado').select_related('user')
    
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
    
    if request.user.role not in ['vocal', 'superadmin'] or (partido.vocal != request.user and request.user.role != 'superadmin'):
        return redirect('vocalia_dashboard')
        
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        minuto = int(request.POST.get('minuto', 0))
        equipo_id = request.POST.get('equipo_id')
        jugador_id = request.POST.get('jugador_id')
        
        equipo = get_object_or_404(Equipo, id=equipo_id)
        jugador = get_object_or_404(User, id=jugador_id) if jugador_id else None
        
        # Registrar evento
        EventoPartido.objects.create(
            partido=partido,
            tipo=tipo,
            minuto=minuto,
            jugador=jugador,
            equipo=equipo
        )
        
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
def cerrar_partido(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    
    if request.user.role not in ['vocal', 'superadmin'] or (partido.vocal != request.user and request.user.role != 'superadmin'):
        return redirect('vocalia_dashboard')
        
    if request.method == 'POST':
        firma_vocal_data = request.POST.get('firma_vocal_data')
        firma_arbitro_data = request.POST.get('firma_arbitro_data')
        firma_local_data = request.POST.get('firma_local_data')
        firma_visitante_data = request.POST.get('firma_visitante_data')
        
        if firma_vocal_data and firma_arbitro_data and firma_local_data and firma_visitante_data:
            partido.firma_vocal = True
            partido.firma_capitan_local = True
            partido.firma_capitan_visitante = True
            
            partido.firma_vocal_img = firma_vocal_data
            partido.firma_arbitro_img = firma_arbitro_data
            partido.firma_entrenador_local_img = firma_local_data
            partido.firma_entrenador_visitante_img = firma_visitante_data
            
            partido.estado = 'finalizado'
            partido.save()
            
            messages.success(request, "Acta de partido cerrada y firmada digitalmente con firmas manuscritas.")
            return redirect('vocalia_dashboard')
        else:
            messages.error(request, "Faltan firmas manuscritas requeridas para cerrar el acta del partido.")
            
    return redirect('match_day', partido_id=partido.id)


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
    jugadores_local_count = FichaJugador.objects.filter(equipo=partido.equipo_local, estado_validacion='aprobado').count()
    jugadores_visitante_count = FichaJugador.objects.filter(equipo=partido.equipo_visitante, estado_validacion='aprobado').count()
    
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
            partido.estadio = estadio
            
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
        
    # Obtener usuarios con roles específicos para asignar
    arbitros = User.objects.filter(role__in=['arbitro', 'superadmin'])
    vocales = User.objects.filter(role__in=['vocal', 'superadmin'])
    
    context = {
        'partido': partido,
        'arbitros': arbitros,
        'vocales': vocales,
    }
    return render(request, 'matches/editar_partido.html', context)


@login_required
def detalle_partido(request, partido_id):
    partido = get_object_or_404(Partido, id=partido_id)
    eventos = EventoPartido.objects.filter(partido=partido).select_related('jugador', 'equipo').order_by('minuto', 'id')
    
    # Obtener jugadores alineados de cada equipo que están habilitados
    jugadores_local = FichaJugador.objects.filter(equipo=partido.equipo_local, estado_validacion='aprobado').select_related('user')
    jugadores_visitante = FichaJugador.objects.filter(equipo=partido.equipo_visitante, estado_validacion='aprobado').select_related('user')
    
    context = {
        'partido': partido,
        'eventos': eventos,
        'jugadores_local': jugadores_local,
        'jugadores_visitante': jugadores_visitante,
    }
    return render(request, 'matches/detalle_partido.html', context)


@login_required
def gestion_arbitros(request):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para acceder a la gestión de árbitros.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        form = ArbitroForm(request.POST)
        if form.is_valid():
            arbitro = form.save()
            messages.success(request, f"Árbitro '{arbitro.get_full_name() or arbitro.username}' registrado exitosamente.")
            return redirect('gestion_arbitros')
        else:
            messages.error(request, "Error al registrar al árbitro. Por favor, revisa los datos ingresados.")
    else:
        form = ArbitroForm()
        
    arbitros = User.objects.filter(role='arbitro').order_by('first_name', 'last_name')
    
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
        
    arbitro = get_object_or_404(User, id=arbitro_id, role='arbitro')
    
    if request.method == 'POST':
        nombre_arbitro = arbitro.get_full_name() or arbitro.username
        arbitro.delete()
        messages.warning(request, f"El árbitro '{nombre_arbitro}' ha sido eliminado del sistema.")
        return redirect('gestion_arbitros')
        
    return redirect('gestion_arbitros')


@login_required
def gestion_vocales(request):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para acceder a la gestión de vocales de mesa.")
        return redirect('partidos_lista')
        
    if request.method == 'POST':
        form = VocalForm(request.POST)
        if form.is_valid():
            vocal = form.save()
            messages.success(request, f"Vocal de Mesa '{vocal.get_full_name() or vocal.username}' registrado exitosamente.")
            return redirect('gestion_vocales')
        else:
            messages.error(request, "Error al registrar al vocal de mesa. Por favor, revisa los datos ingresados.")
    else:
        form = VocalForm()
        
    vocales = User.objects.filter(role='vocal').order_by('first_name', 'last_name')
    
    context = {
        'form': form,
        'vocales': vocales,
    }
    return render(request, 'matches/gestion_vocales.html', context)


@login_required
def eliminar_vocal(request, vocal_id):
    if request.user.role not in ['superadmin', 'comision']:
        messages.error(request, "No tienes autorización para eliminar vocales de mesa.")
        return redirect('partidos_lista')
        
    vocal = get_object_or_404(User, id=vocal_id, role='vocal')
    
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
        form = TorneoForm(request.POST)
        if form.is_valid():
            torneo = form.save()
            messages.success(request, f"Torneo/Liga '{torneo.nombre}' creado exitosamente.")
            return redirect('gestion_torneos')
        else:
            messages.error(request, "Error al crear el torneo. Por favor, revisa los datos.")
    else:
        form = TorneoForm()
        
    torneos = Torneo.objects.all().order_by('-fecha_creacion')
    
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
    equipos = torneo.equipos.all()
    partidos = Partido.objects.filter(torneo=torneo).select_related('equipo_local', 'equipo_visitante', 'vocal', 'arbitro').order_by('jornada', 'fecha_hora')
    
    todos_equipos = Equipo.objects.all().order_by('nombre')
    todos_arbitros = User.objects.filter(role='arbitro').order_by('first_name', 'last_name')
    todos_vocales = User.objects.filter(role='vocal').order_by('first_name', 'last_name')
    
    # Agrupar partidos por fase o fecha para el UI
    partidos_regular = partidos.filter(fase='regular')
    partidos_grupos = partidos.filter(fase='grupos')
    partidos_octavos = partidos.filter(fase='octavos')
    partidos_cuartos = partidos.filter(fase='cuartos')
    partidos_semis = partidos.filter(fase='semifinal')
    partidos_final = partidos.filter(fase='final')
    
    # Si es liga, agrupar por jornada
    partidos_por_jornada = {}
    if torneo.tipo == 'liga':
        for p in partidos:
            partidos_por_jornada.setdefault(p.jornada, []).append(p)
            
    # Equipos no asignados a este torneo
    equipos_no_asignados = Equipo.objects.exclude(id__in=equipos.values_list('id', flat=True))
    
    # Manejar POST para asignar equipos manualmente
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'agregar_equipo':
            equipo_id = request.POST.get('equipo_id')
            if equipo_id:
                equipo = get_object_or_404(Equipo, id=equipo_id)
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
        'partidos_regular': partidos_regular,
        'partidos_grupos': partidos_grupos,
        'partidos_octavos': partidos_octavos,
        'partidos_cuartos': partidos_cuartos,
        'partidos_semis': partidos_semis,
        'partidos_final': partidos_final,
        'partidos_por_jornada': sorted(partidos_por_jornada.items()),
        'todos_equipos': todos_equipos,
        'todos_arbitros': todos_arbitros,
        'todos_vocales': todos_vocales,
        'equipos_no_asignados': equipos_no_asignados,
    }
    return render(request, 'matches/detalle_torneo.html', context)


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
        
    # Obtener vocales y arbitros para asignación rotativa / aleatoria
    vocales = list(User.objects.filter(role='vocal'))
    arbitros = list(User.objects.filter(role='arbitro'))
    
    if not vocales or not arbitros:
        messages.error(request, "Debe registrar al menos un Vocal de Mesa y un Árbitro en el sistema primero.")
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
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
                            fase='regular'
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
                            grupo=grupo_nombre
                        )
                        partidos_creados += 1
                        
                equipos_grupo = [equipos_grupo[0]] + [equipos_grupo[-1]] + equipos_grupo[1:-1]
                
            messages.success(request, f"Fixture para '{grupo_nombre}' generado exitosamente. Se crearon {partidos_creados} partidos.")
            
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
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
        estadio = request.POST.get('estadio', 'Campo Principal')
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
        vocal = get_object_or_404(User, id=vocal_id, role='vocal')
        arbitro = get_object_or_404(User, id=arbitro_id, role='arbitro')
        
        Partido.objects.create(
            equipo_local=eq_local,
            equipo_visitante=eq_visitante,
            fecha_hora=fecha_hora,
            estadio=estadio,
            vocal=vocal,
            arbitro=arbitro,
            fase=fase,
            grupo=grupo if fase == 'grupos' else None,
            jornada=int(jornada) if jornada.isdigit() else 1,
            temporada=torneo.temporada,
            torneo=torneo,
            estado='programado'
        )
        
        messages.success(request, "Partido / Cruce de eliminatoria creado exitosamente.")
        return redirect('detalle_torneo', torneo_id=torneo.id)
        
    return redirect('detalle_torneo', torneo_id=torneo.id)


