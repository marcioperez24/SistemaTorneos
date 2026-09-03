from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import urllib.parse
from django.db import models
from .models import Equipo, InvitacionEquipo, FichaJugador, FichaDT, Categoria
from .forms import EquipoForm, PlayerRegistrationForm, DTRegistrationForm, CategoriaForm
from django.contrib.auth.forms import AuthenticationForm
from matches.models import Torneo
from finances.models import PagoInscripcion, MultaTarjeta, CobroEquipo

def clean_phone_for_whatsapp(phone):
    if not phone:
        return None
    # Remove all non-digits
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if not digits:
        return None
    # If starts with 0 and has 10 digits (Ecuadorian mobile: 09xxxxxxxx), remove leading 0
    if len(digits) == 10 and digits.startswith('0'):
        digits = digits[1:]
    # Prepend Ecuador country code 593 if not present
    if not digits.startswith('593'):
        digits = '593' + digits
    return digits

def login_view(request):
    if request.user.is_authenticated:
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        if request.user.is_superuser:
            return redirect('torre_control')
        return redirect('club_portal')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"¡Bienvenido, {user.username}!")
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                if user.is_superuser:
                    return redirect('torre_control')
                return redirect('club_portal')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    return render(request, 'teams/login.html', {'form': form, 'hide_navbar': True})

def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('login')

@login_required
def club_portal(request):
    # Si el usuario tiene el rol de 'jugador'
    if request.user.role == 'jugador':
        try:
            ficha = request.user.ficha_jugador
            # Si no está aprobado, lo mandamos a la pantalla de validación en curso/rechazo
            if ficha.estado_validacion != 'aprobado':
                return render(request, 'teams/registro_exito.html', {'ficha': ficha, 'hide_navbar': False})
        except FichaJugador.DoesNotExist:
            messages.error(request, "No tienes una ficha de registro asociada a tu cuenta.")
            logout(request)
            return redirect('login')

    if not request.user.has_module_access('equipos'):
        messages.error(request, "No tienes permisos para acceder al Portal del Club.")
        return redirect('gestion_usuarios') if request.user.role == 'superadmin' else redirect('/login/')

    # Equipos que administra o a los que pertenece
    if request.user.role in ['superadmin', 'comision'] or request.user.is_superuser:
        equipos = Equipo.objects.all()
    elif request.user.role == 'jugador':
        # Mostrar únicamente el equipo al que pertenece el jugador
        if request.user.ficha_jugador.equipo:
            equipos = Equipo.objects.filter(id=request.user.ficha_jugador.equipo.id)
        else:
            equipos = Equipo.objects.none()
    else:
        equipos = Equipo.objects.filter(dirigente=request.user)
    
    # Obtener el nuevo enlace de la sesión y eliminarlo para que solo aparezca una vez
    nuevo_enlace = request.session.pop('nuevo_enlace', None)
    nuevo_enlace_equipo_id = request.session.pop('nuevo_enlace_equipo_id', None)
    
    torneos = Torneo.objects.all().order_by('-fecha_creacion')
    
    # Procesar historial de pagos para cada equipo
    for equipo in equipos:
        historial = []
        
        # 1. Inscripciones
        for pago in PagoInscripcion.objects.filter(equipo=equipo):
            historial.append({
                'concepto': "Inscripción de Torneo",
                'monto': pago.monto,
                'estado': pago.estado,
                'fecha': pago.fecha_pago,
                'tipo': 'inscripcion'
            })
            
        # 2. Multas por tarjetas
        for multa in MultaTarjeta.objects.filter(equipo=equipo).select_related('jugador'):
            nombre_jugador = multa.jugador.get_full_name() or multa.jugador.username
            historial.append({
                'concepto': f"{multa.get_motivo_display()} - {nombre_jugador}",
                'monto': multa.monto,
                'estado': multa.estado,
                'fecha': multa.fecha_pago,
                'tipo': 'multa'
            })
            
        # 3. Cobros Adicionales (Arbitraje, etc)
        for cobro in CobroEquipo.objects.filter(equipo=equipo):
            desc = f" ({cobro.descripcion})" if cobro.descripcion else ""
            historial.append({
                'concepto': f"{cobro.get_concepto_display()}{desc}",
                'monto': cobro.monto,
                'estado': cobro.estado,
                'fecha': cobro.fecha_pago or cobro.fecha_emision,
                'tipo': 'cobro_adicional'
            })
            
        # Ordenar historial por fecha (los nulos al principio o usar timezone.now() para comparables)
        def sort_date(item):
            # Si no hay fecha (ej. pendiente), usar la fecha actual para que aparezcan primero
            return item['fecha'] or timezone.now()
            
        historial.sort(key=sort_date, reverse=True)
        equipo.historial_pagos = historial
    
    torneos = Torneo.objects.all().order_by('-fecha_creacion')
    
    context = {
        'equipos': equipos,
        'torneos': torneos,
        'nuevo_enlace': nuevo_enlace,
        'nuevo_enlace_equipo_id': nuevo_enlace_equipo_id,
    }
    return render(request, 'teams/club_portal.html', context)

@login_required
def crear_equipo(request):
    if not request.user.has_module_access('equipos'):
        return redirect('club_portal')
        
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            equipo = form.save(commit=False)
            equipo.dirigente = request.user
            equipo.save()
            messages.success(request, f"Equipo '{equipo.nombre}' creado exitosamente.")
            return redirect('club_portal')
    else:
        form = EquipoForm(user=request.user)
    return render(request, 'teams/crear_equipo.html', {'form': form})

@login_required
def editar_equipo(request, equipo_id):
    if not request.user.has_module_access('equipos'):
        messages.error(request, "No tienes permisos para acceder al Módulo de Equipos.")
        return redirect('club_portal')
        
    # Obtener equipo. Permitir edición si es superadmin, superuser, o el dirigente del equipo
    if request.user.role == 'superadmin' or request.user.is_superuser:
        equipo = get_object_or_404(Equipo, id=equipo_id)
    else:
        equipo = get_object_or_404(Equipo, id=equipo_id, dirigente=request.user)
        
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES, instance=equipo, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Equipo '{equipo.nombre}' actualizado exitosamente.")
            return redirect('club_portal')
    else:
        form = EquipoForm(instance=equipo, user=request.user)
    return render(request, 'teams/crear_equipo.html', {'form': form, 'edit_mode': True, 'equipo': equipo})

@login_required
def generar_invitacion(request, equipo_id):
    if request.user.role == 'superadmin' or request.user.is_superuser:
        equipo = get_object_or_404(Equipo, id=equipo_id)
    else:
        equipo = get_object_or_404(Equipo, id=equipo_id, dirigente=request.user)
    
    tipo = request.GET.get('tipo', 'jugador')
    if tipo not in ['jugador', 'dt']:
        tipo = 'jugador'
        
    torneo_id = request.GET.get('torneo_id')
    if not torneo_id:
        messages.error(request, "Debe seleccionar un torneo para generar la invitación.")
        return redirect('club_portal')
        
    torneo = get_object_or_404(Torneo, id=torneo_id)
        
    if tipo == 'jugador':
        # Validar límite de jugadores excluyendo lesionados y rechazados
        from django.db.models import Q
        num_jugadores_actuales = FichaJugador.objects.filter(
            equipo=equipo, 
            torneo=torneo,
            es_lesionado=False
        ).exclude(estado_validacion='rechazado').count()
        
        if num_jugadores_actuales >= torneo.max_jugadores_por_equipo:
            messages.error(request, f"No se puede generar invitación. El equipo ya ha alcanzado el límite de {torneo.max_jugadores_por_equipo} jugadores activos.")
            return redirect('club_portal')
        
    # Desactivar invitaciones anteriores para este equipo, torneo y tipo
    InvitacionEquipo.objects.filter(equipo=equipo, torneo=torneo, tipo=tipo, activo=True).update(activo=False)
    
    # Crear nueva invitación válida por 48 horas
    expira = timezone.now() + timedelta(hours=48)
    invitacion = InvitacionEquipo.objects.create(
        equipo=equipo,
        torneo=torneo,
        tipo=tipo,
        expira_en=expira
    )
    
    # Construir URL absoluta del enlace
    enlace = request.build_absolute_uri(f"/invitacion/{invitacion.token}/")
    tipo_display = "Director Técnico" if tipo == 'dt' else "Jugador"
    messages.success(request, f"¡Enlace de invitación para {tipo_display} generado con éxito! Válido por 48 horas.")
    
    # Guardamos en la sesión para poder mostrarlo fácilmente en la redirección
    request.session['nuevo_enlace'] = enlace
    request.session['nuevo_enlace_equipo_id'] = equipo.id
    return redirect('club_portal')

def registro_jugador(request, token):
    invitacion = get_object_or_404(InvitacionEquipo, token=token)
    
    if not invitacion.esta_valida():
        return render(request, 'teams/registro_error.html', {
            'error': 'Este enlace de invitación ha expirado o ya no está activo.',
            'hide_navbar': True
        })
        
    tipo = invitacion.tipo
    
    # Si el usuario ya está autenticado (tiene cuenta en el sistema)
    if request.user.is_authenticated:
        # Validar si ya está registrado en este torneo (independientemente del equipo)
        if tipo == 'dt':
            ya_registrado_torneo = FichaDT.objects.filter(user=request.user, torneo=invitacion.torneo).exists()
        else:
            ya_registrado_torneo = FichaJugador.objects.filter(user=request.user, torneo=invitacion.torneo).exists()
            
        if ya_registrado_torneo:
            return render(request, 'teams/registro_error.html', {
                'error': f'Ya te encuentras registrado en otro equipo para el torneo {invitacion.torneo.nombre}. Un jugador/DT no puede estar en dos equipos distintos en el mismo torneo.',
                'hide_navbar': False
            })
            
        if tipo == 'jugador' and invitacion.torneo:
            # Validar límite de jugadores
            num_jugadores_actuales = FichaJugador.objects.filter(
                equipo=invitacion.equipo, 
                torneo=invitacion.torneo,
                es_lesionado=False
            ).exclude(estado_validacion='rechazado').count()
            
            if num_jugadores_actuales >= invitacion.torneo.max_jugadores_por_equipo:
                return render(request, 'teams/registro_error.html', {
                    'error': f'El equipo {invitacion.equipo.nombre} ya ha alcanzado el límite máximo de jugadores ({invitacion.torneo.max_jugadores_por_equipo}) permitidos en el torneo {invitacion.torneo.nombre}.',
                    'hide_navbar': False
                })
            
        # Buscar su registro anterior para copiar archivos
        if tipo == 'dt':
            ficha_anterior = FichaDT.objects.filter(user=request.user).order_by('-id').first()
        else:
            ficha_anterior = FichaJugador.objects.filter(user=request.user).order_by('-id').first()
            
        # Si tiene un registro anterior, mostramos la pantalla simplificada y rápida
        if ficha_anterior:
            if request.method == 'POST':
                if tipo == 'dt':
                    nueva_ficha = FichaDT(
                        user=request.user,
                        equipo=invitacion.equipo,
                        torneo=invitacion.torneo,
                        estado_validacion='pendiente',
                        fecha_firma=timezone.now(),
                        firma_digital=True,
                        firma_imagen=request.POST.get('firma_imagen')
                    )
                    nueva_ficha.foto = ficha_anterior.foto
                    nueva_ficha.cedula_frontal = ficha_anterior.cedula_frontal
                    nueva_ficha.cedula_posterior = ficha_anterior.cedula_posterior
                    nueva_ficha.nro_cedula = ficha_anterior.nro_cedula
                    nueva_ficha.tipo_sangre = ficha_anterior.tipo_sangre
                    nueva_ficha.contacto_emergencia = ficha_anterior.contacto_emergencia
                    nueva_ficha.telefono_emergencia = ficha_anterior.telefono_emergencia
                    nueva_ficha.save()
                else:
                    nueva_ficha = FichaJugador(
                        user=request.user,
                        equipo=invitacion.equipo,
                        torneo=invitacion.torneo,
                        numero_camiseta=request.POST.get('numero_camiseta'),
                        estado_validacion='pendiente',
                        fecha_firma=timezone.now(),
                        firma_digital=True,
                        firma_imagen=request.POST.get('firma_imagen')
                    )
                    nueva_ficha.foto = ficha_anterior.foto
                    nueva_ficha.cedula_frontal = ficha_anterior.cedula_frontal
                    nueva_ficha.cedula_posterior = ficha_anterior.cedula_posterior
                    nueva_ficha.nro_cedula = ficha_anterior.nro_cedula
                    nueva_ficha.tipo_sangre = ficha_anterior.tipo_sangre
                    nueva_ficha.contacto_emergencia = ficha_anterior.contacto_emergencia
                    nueva_ficha.telefono_emergencia = ficha_anterior.telefono_emergencia
                    nueva_ficha.save()
                    
                return redirect('registro_exito')
                
            return render(request, 'teams/registro_existente.html', {
                'equipo': invitacion.equipo,
                'tipo': tipo,
                'ficha_anterior': ficha_anterior,
                'hide_navbar': False
            })
            
    # Si no tiene cuenta o está logueado pero es su primera ficha (ej. admin o nuevo usuario)
    if request.method == 'POST':
        nro_cedula = request.POST.get('nro_cedula', '').strip()
        existing_user = None
        if nro_cedula:
            f_jug = FichaJugador.objects.filter(nro_cedula=nro_cedula).first()
            if f_jug:
                existing_user = f_jug.user
            else:
                f_dt = FichaDT.objects.filter(nro_cedula=nro_cedula).first()
                if f_dt:
                    existing_user = f_dt.user
                    
        user_to_use = request.user if request.user.is_authenticated else existing_user
        
        if tipo == 'dt':
            form = DTRegistrationForm(request.POST, request.FILES, user=user_to_use)
        else:
            form = PlayerRegistrationForm(request.POST, request.FILES, user=user_to_use)
            
        if form.is_valid():
            # Check tournament constraints again for unauthenticated flow
            if tipo == 'dt':
                ya_registrado_torneo = FichaDT.objects.filter(user=user_to_use, torneo=invitacion.torneo).exists() if user_to_use else False
            else:
                ya_registrado_torneo = FichaJugador.objects.filter(user=user_to_use, torneo=invitacion.torneo).exists() if user_to_use else False
                
            if ya_registrado_torneo:
                messages.error(request, f'Ya te encuentras registrado en el torneo {invitacion.torneo.nombre}.')
                return redirect(request.path)
                
            if tipo == 'jugador' and invitacion.torneo:
                num_jugadores_actuales = FichaJugador.objects.filter(equipo=invitacion.equipo, torneo=invitacion.torneo).count()
                if num_jugadores_actuales >= invitacion.torneo.max_jugadores_por_equipo:
                    messages.error(request, f'El equipo ya alcanzó el máximo de jugadores ({invitacion.torneo.max_jugadores_por_equipo}) permitidos en este torneo.')
                    return redirect(request.path)
                    
            ficha = form.save(equipo=invitacion.equipo)
            ficha.torneo = invitacion.torneo
            # Firmando digitalmente con la fecha actual
            ficha.fecha_firma = timezone.now()
            ficha.save()
            return redirect('registro_exito')
    else:
        form_user = request.user if request.user.is_authenticated else None
        if tipo == 'dt':
            form = DTRegistrationForm(user=form_user)
        else:
            form = PlayerRegistrationForm(user=form_user)
            
    template_name = 'teams/registro_dt.html' if tipo == 'dt' else 'teams/registro_jugador.html'
    return render(request, template_name, {
        'form': form,
        'equipo': invitacion.equipo,
        'hide_navbar': False if request.user.is_authenticated else True
    })

def registro_exito(request):
    return render(request, 'teams/registro_exito.html', {'hide_navbar': True})

@login_required
def secretaria_dashboard(request):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No tienes permisos para acceder al Módulo de Secretaría.")
        return redirect('club_portal')
        
    pendientes_jugadores = FichaJugador.objects.filter(estado_validacion='pendiente').select_related('user', 'equipo')
    pendientes_dt = FichaDT.objects.filter(estado_validacion='pendiente').select_related('user', 'equipo')
    
    # Combinar listas de pendientes con un tag para identificar el tipo
    pendientes = []
    for pj in pendientes_jugadores:
        pj.es_dt = False
        pendientes.append(pj)
    for pdt in pendientes_dt:
        pdt.es_dt = True
        pendientes.append(pdt)
        
    # Ordenar por fecha_firma o fecha de registro (o id)
    # FichaDT no tiene fecha_firma en la base de datos pero sí firma_digital, usemos el ID
    pendientes.sort(key=lambda x: x.id)

    historial_jugadores = FichaJugador.objects.exclude(estado_validacion='pendiente').select_related('user', 'equipo')
    historial_dt = FichaDT.objects.exclude(estado_validacion='pendiente').select_related('user', 'equipo')
    
    historial = []
    for hj in historial_jugadores:
        hj.es_dt = False
        historial.append(hj)
    for hdt in historial_dt:
        hdt.es_dt = True
        historial.append(hdt)
        
    historial.sort(key=lambda x: x.id, reverse=True)
    historial = historial[:50]
    
    context = {
        'pendientes': pendientes,
        'historial': historial
    }
    return render(request, 'teams/secretaria_dashboard.html', context)

@login_required
def aprobar_jugador(request, ficha_id):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    tipo = request.GET.get('tipo', 'jugador')
    if tipo == 'dt':
        ficha = get_object_or_404(FichaDT, id=ficha_id)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id)
        
    ficha.estado_validacion = 'aprobado'
    ficha.motivo_rechazo = None
    ficha.fecha_aprobacion = timezone.now()
    ficha.aprobado_por = request.user
    ficha.save()
    
    rol_str = "Director Técnico" if tipo == 'dt' else "Jugador"
    nombre_completo = ficha.user.get_full_name() or ficha.user.username
    equipo_nombre = ficha.equipo.nombre if ficha.equipo else "su club"
    
    messages.success(request, f"El carnet de {nombre_completo} ({rol_str}) ha sido Aprobado y Habilitado.")
    
    telefono = clean_phone_for_whatsapp(ficha.user.telefono)
    if telefono:
        mensaje = f"¡Hola {nombre_completo}! Tu registro como {rol_str} para el equipo '{equipo_nombre}' ha sido APROBADO y HABILITADO con éxito. ðâ½"
        url_mensaje = f"https://api.whatsapp.com/send?phone={telefono}&text={urllib.parse.quote(mensaje)}"
        return redirect(url_mensaje)
        
    return redirect('secretaria_dashboard')

@login_required
def rechazar_jugador(request, ficha_id):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    tipo = request.GET.get('tipo', 'jugador')
    if tipo == 'dt':
        ficha = get_object_or_404(FichaDT, id=ficha_id)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id)
        
    if request.method == 'POST':
        motivo = request.POST.get('motivo_rechazo', 'Documentación ilegible o incompleta.')
        ficha.estado_validacion = 'rechazado'
        ficha.motivo_rechazo = motivo
        ficha.save()
        rol_str = "Director Técnico" if tipo == 'dt' else "Jugador"
        nombre_completo = ficha.user.get_full_name() or ficha.user.username
        equipo_nombre = ficha.equipo.nombre if ficha.equipo else "su club"
        
        messages.warning(request, f"El carnet de {nombre_completo} ({rol_str}) ha sido Rechazado.")
        
        telefono = clean_phone_for_whatsapp(ficha.user.telefono)
        if telefono:
            mensaje = f"¡Hola {nombre_completo}! Tu registro como {rol_str} para el equipo '{equipo_nombre}' ha sido RECHAZADO.\n\nMotivo del rechazo: {motivo}\n\nPor favor, ingresa al portal del club para corregir tu información."
            url_mensaje = f"https://api.whatsapp.com/send?phone={telefono}&text={urllib.parse.quote(mensaje)}"
            return redirect(url_mensaje)
            
    return redirect('secretaria_dashboard')

@login_required
def ver_carnet(request, ficha_id):
    tipo = request.GET.get('tipo', 'jugador')
    if tipo == 'dt':
        ficha = get_object_or_404(FichaDT, id=ficha_id)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    # Validar permisos para ver el carnet
    es_propietario = request.user == ficha.user
    es_su_dirigente = ficha.equipo and request.user == ficha.equipo.dirigente
    es_comision_o_admin = request.user.role in ['comision', 'superadmin']
    
    if not (es_propietario or es_su_dirigente or es_comision_o_admin):
        messages.error(request, "No tienes permisos para ver el carnet de esta persona.")
        return redirect('club_portal')
        
    if ficha.estado_validacion != 'aprobado':
        messages.error(request, "Este carnet aún no está habilitado.")
        return redirect('club_portal')
        
    # URL de verificación pública
    verif_url = request.build_absolute_uri(f"/verificar/jugador/{ficha.id}/?tipo={tipo}")
    # Generamos la URL del código QR dinámico
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={verif_url}"
    
    context = {
        'ficha': ficha,
        'qr_url': qr_url,
        'tipo': tipo
    }
    return render(request, 'teams/carnet.html', context)

def verificar_jugador(request, ficha_id):
    tipo = request.GET.get('tipo', 'jugador')
    if tipo == 'dt':
        ficha = get_object_or_404(FichaDT, id=ficha_id)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    context = {
        'ficha': ficha,
        'tipo': tipo
    }
    return render(request, 'teams/verificar_jugador.html', context)

@login_required
def ver_ficha(request, ficha_id):
    tipo = request.GET.get('tipo', 'jugador')
    if tipo == 'dt':
        ficha = get_object_or_404(FichaDT, id=ficha_id)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    es_propietario = request.user == ficha.user
    es_su_dirigente = ficha.equipo and request.user == ficha.equipo.dirigente
    es_comision_o_admin = request.user.role in ['comision', 'superadmin'] or request.user.is_superuser
    
    if not (es_propietario or es_su_dirigente or es_comision_o_admin):
        messages.error(request, "No tienes permisos para ver la ficha de esta persona.")
        return redirect('club_portal')
        
    context = {
        'ficha': ficha,
        'tipo': tipo
    }
    return render(request, 'teams/ficha_jugador_print.html', context)

@login_required
def guardar_alineacion(request, equipo_id):
    import json
    from django.http import JsonResponse
    equipo = get_object_or_404(Equipo, id=equipo_id)
    
    es_dirigente = request.user == equipo.dirigente
    es_admin = request.user.role == 'superadmin' or request.user.is_superuser
    if not (es_dirigente or es_admin):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            equipo.alineacion = data
            equipo.save()
            return JsonResponse({'status': 'success', 'message': 'Alineación guardada con éxito.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

def buscar_cedula(request):
    from django.http import JsonResponse
    cedula = request.GET.get('cedula', '').strip()
    if not cedula or len(cedula) < 3:
        return JsonResponse({'results': []})
        
    fichas_jugador = FichaJugador.objects.filter(nro_cedula__startswith=cedula).select_related('user')[:5]
    fichas_dt = FichaDT.objects.filter(nro_cedula__startswith=cedula).select_related('user')[:5]
    
    resultados = {}
    
    for ficha in fichas_jugador:
        resultados[ficha.nro_cedula] = {
            'cedula': ficha.nro_cedula,
            'first_name': ficha.user.first_name,
            'last_name': ficha.user.last_name,
            'username': ficha.user.username,
            'email': ficha.user.email,
            'telefono': ficha.user.telefono or '',
            'tipo_sangre': ficha.tipo_sangre or '',
            'contacto_emergencia': ficha.contacto_emergencia or '',
            'telefono_emergencia': ficha.telefono_emergencia or '',
        }
        
    for ficha in fichas_dt:
        if ficha.nro_cedula not in resultados:
            resultados[ficha.nro_cedula] = {
                'cedula': ficha.nro_cedula,
                'first_name': ficha.user.first_name,
                'last_name': ficha.user.last_name,
                'username': ficha.user.username,
                'email': ficha.user.email,
                'telefono': ficha.user.telefono or '',
                'tipo_sangre': ficha.tipo_sangre or '',
                'contacto_emergencia': ficha.contacto_emergencia or '',
                'telefono_emergencia': ficha.telefono_emergencia or '',
            }
            
    return JsonResponse({'results': list(resultados.values())})


@login_required
def toggle_lesion(request, ficha_id):
    ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    # Solo el dirigente del equipo o un admin pueden hacer esto
    es_admin = request.user.role in ['superadmin', 'secretaria']
    if not es_admin and getattr(ficha.equipo, 'dirigente', None) != request.user:
        messages.error(request, "No tienes permiso para modificar el estado de este jugador.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        if ficha.es_lesionado:
            # Dar de alta: Verificar si hay cupo disponible
            from django.db.models import Q
            num_jugadores_actuales = FichaJugador.objects.filter(
                equipo=ficha.equipo, 
                torneo=ficha.torneo,
                es_lesionado=False
            ).exclude(estado_validacion='rechazado').count()
            
            if ficha.torneo and num_jugadores_actuales >= ficha.torneo.max_jugadores_por_equipo:
                messages.error(request, f"No puedes dar de alta a {ficha.user.get_full_name()} porque el equipo ya alcanzó el límite de {ficha.torneo.max_jugadores_por_equipo} jugadores activos.")
            else:
                ficha.es_lesionado = False
                ficha.save()
                messages.success(request, f"{ficha.user.get_full_name()} ha sido dado de alta exitosamente.")
        else:
            # Reportar lesión
            ficha.es_lesionado = True
            ficha.save()
            messages.warning(request, f"{ficha.user.get_full_name()} ha sido reportado como lesionado. Se ha liberado un cupo temporal, por lo que ahora puedes inscribir a otro jugador más.")
            
    return redirect('club_portal')


@login_required
def lista_categorias(request):
    if not (request.user.role in ['superadmin', 'secretaria'] or request.user.is_superuser):
        messages.error(request, "No tienes permisos para acceder a este módulo.")
        return redirect('club_portal')
    
    categorias = Categoria.objects.all().order_by('nombre')
    return render(request, 'teams/lista_categorias.html', {'categorias': categorias})


@login_required
def crear_categoria(request):
    if not (request.user.role in ['superadmin', 'secretaria'] or request.user.is_superuser):
        messages.error(request, "No tienes permisos para acceder a este módulo.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría creada con éxito.")
            return redirect('lista_categorias')
    else:
        form = CategoriaForm()
    return render(request, 'teams/form_categoria.html', {'form': form, 'title': 'Crear Categoría'})


@login_required
def editar_categoria(request, categoria_id):
    if not (request.user.role in ['superadmin', 'secretaria'] or request.user.is_superuser):
        messages.error(request, "No tienes permisos para acceder a este módulo.")
        return redirect('club_portal')
        
    categoria = get_object_or_404(Categoria, id=categoria_id)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría actualizada con éxito.")
            return redirect('lista_categorias')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'teams/form_categoria.html', {'form': form, 'title': 'Editar Categoría', 'categoria': categoria})


@login_required
def eliminar_categoria(request, categoria_id):
    if not (request.user.role in ['superadmin', 'secretaria'] or request.user.is_superuser):
        messages.error(request, "No tienes permisos para acceder a este módulo.")
        return redirect('club_portal')
        
    categoria = get_object_or_404(Categoria, id=categoria_id)
    if request.method == 'POST':
        try:
            categoria.delete()
            messages.success(request, "Categoría eliminada con éxito.")
        except models.ProtectedError:
            messages.error(request, "No se puede eliminar la categoría porque hay equipos o torneos asociados a ella.")
        
    return redirect('lista_categorias')

