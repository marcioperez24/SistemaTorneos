from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import urllib.parse
from django.db import models, transaction, IntegrityError
import logging
from .models import Equipo, InvitacionEquipo, FichaJugador, FichaDT, Categoria
from .forms import EquipoForm, PlayerRegistrationForm, DTRegistrationForm, CategoriaForm
from django.contrib.auth.forms import AuthenticationForm
from matches.models import Torneo
from finances.models import PagoInscripcion, MultaTarjeta, CobroEquipo

logger = logging.getLogger(__name__)

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
        equipos_qs = Equipo.objects.filter(organizacion=request.organizacion)
    elif request.user.role == 'jugador':
        # Mostrar únicamente el equipo al que pertenece el jugador
        if request.user.ficha_jugador.equipo:
            equipos_qs = Equipo.objects.filter(id=request.user.ficha_jugador.equipo.id)
        else:
            equipos_qs = Equipo.objects.none()
    else:
        equipos_qs = Equipo.objects.filter(organizacion=request.organizacion, dirigente=request.user)
    
    equipos = list(equipos_qs.select_related('categoria', 'dirigente').prefetch_related(
        'categorias',
        'cuerpo_tecnico__user',
        'jugadores__user',
        'jugadores__torneo'
    ))
    
    # Obtener el nuevo enlace de la sesión y eliminarlo para que solo aparezca una vez
    nuevo_enlace = request.session.pop('nuevo_enlace', None)
    nuevo_enlace_equipo_id = request.session.pop('nuevo_enlace_equipo_id', None)
    
    torneos = Torneo.objects.filter(organizacion=request.organizacion).order_by('-fecha_creacion')
    
    # Procesar historial de pagos para cada equipo en bloque (evita cientos de queries N+1)
    equipos_ids = [e.id for e in equipos]
    pagos_by_equipo = defaultdict(list)
    if equipos_ids:
        # 1. Inscripciones
        for pago in PagoInscripcion.objects.filter(equipo_id__in=equipos_ids):
            pagos_by_equipo[pago.equipo_id].append({
                'concepto': "Inscripción de Torneo",
                'monto': pago.monto,
                'estado': pago.estado,
                'fecha': pago.fecha_pago,
                'tipo': 'inscripcion'
            })
            
        # 2. Multas por tarjetas
        for multa in MultaTarjeta.objects.filter(equipo_id__in=equipos_ids).select_related('jugador'):
            nombre_jugador = multa.jugador.get_full_name() or multa.jugador.username
            pagos_by_equipo[multa.equipo_id].append({
                'concepto': f"{multa.get_motivo_display()} - {nombre_jugador}",
                'monto': multa.monto,
                'estado': multa.estado,
                'fecha': multa.fecha_pago,
                'tipo': 'multa'
            })
            
        # 3. Cobros Adicionales (Arbitraje, etc)
        for cobro in CobroEquipo.objects.filter(equipo_id__in=equipos_ids):
            desc = f" ({cobro.descripcion})" if cobro.descripcion else ""
            pagos_by_equipo[cobro.equipo_id].append({
                'concepto': f"{cobro.get_concepto_display()}{desc}",
                'monto': cobro.monto,
                'estado': cobro.estado,
                'fecha': cobro.fecha_pago or cobro.fecha_emision,
                'tipo': 'cobro_adicional'
            })
            
    now = timezone.now()
    for equipo in equipos:
        historial = pagos_by_equipo.get(equipo.id, [])
        historial.sort(key=lambda item: item['fecha'] or now, reverse=True)
        equipo.historial_pagos = historial
    
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
        form = EquipoForm(request.POST, request.FILES, user=request.user, organizacion=request.organizacion)
        if form.is_valid():
            equipo = form.save(commit=False)
            equipo.dirigente = request.user
            equipo.organizacion = request.organizacion
            equipo.save()
            form.save_m2m()
            messages.success(request, f"Equipo '{equipo.nombre}' creado exitosamente.")
            return redirect('club_portal')
    else:
        form = EquipoForm(user=request.user, organizacion=request.organizacion)
    return render(request, 'teams/crear_equipo.html', {'form': form})

@login_required
def editar_equipo(request, equipo_id):
    if not request.user.has_module_access('equipos'):
        messages.error(request, "No tienes permisos para acceder al Módulo de Equipos.")
        return redirect('club_portal')
        
    # Obtener equipo. Permitir edición si es superadmin, superuser, o el dirigente del equipo
    if request.user.role == 'superadmin' or request.user.is_superuser:
        equipo = get_object_or_404(Equipo, id=equipo_id, organizacion=request.organizacion)
    else:
        equipo = get_object_or_404(Equipo, id=equipo_id, organizacion=request.organizacion, dirigente=request.user)
        
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES, instance=equipo, user=request.user, organizacion=request.organizacion)
        if form.is_valid():
            form.save()
            messages.success(request, f"Equipo '{equipo.nombre}' actualizado exitosamente.")
            return redirect('club_portal')
    else:
        form = EquipoForm(instance=equipo, user=request.user, organizacion=request.organizacion)
    return render(request, 'teams/crear_equipo.html', {'form': form, 'edit_mode': True, 'equipo': equipo})

@login_required
def generar_invitacion(request, equipo_id):
    if request.user.role == 'superadmin' or request.user.is_superuser:
        equipo = get_object_or_404(Equipo, id=equipo_id, organizacion=request.organizacion)
    else:
        equipo = get_object_or_404(Equipo, id=equipo_id, organizacion=request.organizacion, dirigente=request.user)
    
    tipo = request.GET.get('tipo', 'jugador')
    if tipo not in ['jugador', 'dt']:
        tipo = 'jugador'
        
    torneo_id = request.GET.get('torneo_id')
    if not torneo_id:
        messages.error(request, "Debe seleccionar un torneo para generar la invitación.")
        return redirect('club_portal')
        
    torneo = get_object_or_404(Torneo, id=torneo_id, organizacion=request.organizacion)
        
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
    
    # Crear nueva invitación válida por 72 horas
    expira = timezone.now() + timedelta(hours=72)
    invitacion = InvitacionEquipo.objects.create(
        equipo=equipo,
        torneo=torneo,
        tipo=tipo,
        expira_en=expira,
        organizacion=request.organizacion
    )
    
    # Construir URL absoluta del enlace
    enlace = request.build_absolute_uri(f"/invitacion/{invitacion.token}/")
    tipo_display = "Director Técnico" if tipo == 'dt' else "Jugador"
    messages.success(request, f"¡Enlace de invitación para {tipo_display} generado con éxito! Válido por 72 horas.")
    
    # Guardamos en la sesión para poder mostrarlo fácilmente en la redirección
    request.session['nuevo_enlace'] = enlace
    request.session['nuevo_enlace_equipo_id'] = equipo.id
    return redirect('club_portal')

def registro_jugador(request, token):
    invitacion = get_object_or_404(InvitacionEquipo, token=token)
    
    if not invitacion.esta_valida():
        return render(request, 'teams/registro_error.html', {
            'titulo': 'Enlace Expirado o Inactivo',
            'error': 'Este enlace de invitación ha expirado o ya no está activo.',
            'es_expirado': True,
            'hide_navbar': True
        })
        
    tipo = invitacion.tipo
    org = invitacion.organizacion or (invitacion.equipo.organizacion if invitacion.equipo else None)
    if not org:
        from users.models import Organizacion
        org = Organizacion.objects.first()
    
    # 1. Si el usuario ya está autenticado (tiene cuenta en el sistema)
    if request.user.is_authenticated:
        # Validar si ya está registrado en este torneo (independientemente del equipo)
        if invitacion.torneo:
            if tipo == 'dt':
                ficha_existente = FichaDT.objects.filter(user=request.user, torneo=invitacion.torneo).select_related('equipo').first()
            else:
                ficha_existente = FichaJugador.objects.filter(user=request.user, torneo=invitacion.torneo).select_related('equipo').first()
                
            if ficha_existente:
                nombre_torneo = invitacion.torneo.nombre if invitacion.torneo else "el torneo"
                if ficha_existente.equipo == invitacion.equipo:
                    request.session['last_registro_ficha_id'] = ficha_existente.id
                    request.session['last_registro_tipo'] = tipo
                    messages.info(request, f'Ya te encuentras registrado en el equipo {invitacion.equipo.nombre} para {nombre_torneo}.')
                    return redirect('registro_exito')
                else:
                    return render(request, 'teams/registro_error.html', {
                        'titulo': 'Ya registrado en otro equipo',
                        'error': f'Ya te encuentras registrado en el equipo "{ficha_existente.equipo.nombre if ficha_existente.equipo else "otro club"}" para el torneo {nombre_torneo}. Un participante no puede estar en dos equipos distintos en el mismo torneo.',
                        'hide_navbar': True
                    })
        else:
            # Si la invitación no está ligada a un torneo específico, verificar si ya está en este equipo
            if tipo == 'dt':
                ficha_en_equipo = FichaDT.objects.filter(user=request.user, equipo=invitacion.equipo).first()
            else:
                ficha_en_equipo = FichaJugador.objects.filter(user=request.user, equipo=invitacion.equipo).first()
            if ficha_en_equipo:
                request.session['last_registro_ficha_id'] = ficha_en_equipo.id
                request.session['last_registro_tipo'] = tipo
                messages.info(request, f'Ya te encuentras registrado en el equipo {invitacion.equipo.nombre}.')
                return redirect('registro_exito')
            
        if tipo == 'jugador':
            if invitacion.torneo:
                # Validar límite de jugadores por torneo
                num_jugadores_actuales = FichaJugador.objects.filter(
                    equipo=invitacion.equipo, 
                    torneo=invitacion.torneo,
                    es_lesionado=False
                ).exclude(estado_validacion='rechazado').count()
                
                if num_jugadores_actuales >= invitacion.torneo.max_jugadores_por_equipo:
                    return render(request, 'teams/registro_error.html', {
                        'titulo': 'Límite de Jugadores Alcanzado',
                        'error': f'El equipo {invitacion.equipo.nombre} ya ha alcanzado el límite máximo de jugadores ({invitacion.torneo.max_jugadores_por_equipo}) permitidos en el torneo {invitacion.torneo.nombre}.',
                        'hide_navbar': True
                    })
            elif invitacion.equipo and invitacion.equipo.max_jugadores:
                # Validar límite por plantilla del equipo
                num_jugadores_actuales = FichaJugador.objects.filter(
                    equipo=invitacion.equipo,
                    es_lesionado=False
                ).exclude(estado_validacion='rechazado').count()
                if num_jugadores_actuales >= invitacion.equipo.max_jugadores:
                    return render(request, 'teams/registro_error.html', {
                        'titulo': 'Plantilla Completa',
                        'error': f'El equipo {invitacion.equipo.nombre} ya ha alcanzado el límite de su plantilla ({invitacion.equipo.max_jugadores} jugadores).',
                        'hide_navbar': True
                    })
            
        # Buscar su registro anterior para copiar archivos
        if tipo == 'dt':
            ficha_anterior = FichaDT.objects.filter(user=request.user).order_by('-id').first()
        else:
            ficha_anterior = FichaJugador.objects.filter(user=request.user).order_by('-id').first()
            
        # Si tiene un registro anterior, mostramos la pantalla simplificada y rápida
        if ficha_anterior:
            if request.method == 'POST':
                if not request.POST.get('acepto_lopdp'):
                    messages.error(request, 'Debes autorizar el tratamiento de tus datos personales (LOPDP) para continuar.')
                    return redirect(request.path)
                
                nc_raw = request.POST.get('numero_camiseta')
                numero_camiseta = int(str(nc_raw).strip()) if (nc_raw and str(nc_raw).strip().isdigit()) else None

                if tipo == 'jugador' and numero_camiseta is not None:
                    qs_cam = FichaJugador.objects.filter(
                        equipo=invitacion.equipo,
                        numero_camiseta=numero_camiseta
                    ).exclude(user=request.user).exclude(estado_validacion='rechazado')
                    if qs_cam.exists():
                        jugador_ocupante = qs_cam.first()
                        nombre_ocupante = jugador_ocupante.user.get_full_name() or jugador_ocupante.user.username
                        messages.error(request, f"El dorsal #{numero_camiseta} ya está ocupado por {nombre_ocupante} en el equipo '{invitacion.equipo.nombre}'. Por favor elige otro número.")
                        return redirect(request.path)

                try:
                    with transaction.atomic():
                        firma_img = request.POST.get('firma_imagen') or getattr(ficha_anterior, 'firma_imagen', None)
                        if tipo == 'dt':
                            nueva_ficha, created = FichaDT.objects.get_or_create(
                                user=request.user,
                                organizacion=org,
                                torneo=invitacion.torneo,
                                defaults={
                                    'equipo': invitacion.equipo,
                                    'estado_validacion': 'pendiente',
                                    'fecha_firma': timezone.now(),
                                    'firma_digital': True,
                                    'firma_imagen': firma_img,
                                    'foto': ficha_anterior.foto,
                                    'cedula_frontal': ficha_anterior.cedula_frontal,
                                    'cedula_posterior': ficha_anterior.cedula_posterior,
                                    'nro_cedula': ficha_anterior.nro_cedula,
                                    'tipo_sangre': ficha_anterior.tipo_sangre,
                                    'contacto_emergencia': ficha_anterior.contacto_emergencia,
                                    'telefono_emergencia': ficha_anterior.telefono_emergencia,
                                }
                            )
                            if not created:
                                nueva_ficha.equipo = invitacion.equipo
                                nueva_ficha.fecha_firma = timezone.now()
                                if firma_img:
                                    nueva_ficha.firma_imagen = firma_img
                                nueva_ficha.save()
                        else:
                            nueva_ficha, created = FichaJugador.objects.get_or_create(
                                user=request.user,
                                organizacion=org,
                                torneo=invitacion.torneo,
                                defaults={
                                    'equipo': invitacion.equipo,
                                    'numero_camiseta': numero_camiseta,
                                    'estado_validacion': 'pendiente',
                                    'fecha_firma': timezone.now(),
                                    'firma_digital': True,
                                    'firma_imagen': firma_img,
                                    'foto': ficha_anterior.foto,
                                    'cedula_frontal': ficha_anterior.cedula_frontal,
                                    'cedula_posterior': ficha_anterior.cedula_posterior,
                                    'nro_cedula': ficha_anterior.nro_cedula,
                                    'tipo_sangre': ficha_anterior.tipo_sangre,
                                    'contacto_emergencia': ficha_anterior.contacto_emergencia,
                                    'telefono_emergencia': ficha_anterior.telefono_emergencia,
                                }
                            )
                            if not created:
                                nueva_ficha.equipo = invitacion.equipo
                                nueva_ficha.fecha_firma = timezone.now()
                                if numero_camiseta is not None:
                                    nueva_ficha.numero_camiseta = numero_camiseta
                                if firma_img:
                                    nueva_ficha.firma_imagen = firma_img
                                nueva_ficha.save()

                        # Vinculación con UsuarioOrganizacion
                        if org:
                            from users.models import UsuarioOrganizacion
                            UsuarioOrganizacion.objects.get_or_create(
                                usuario=request.user,
                                organizacion=org,
                                defaults={'rol': tipo, 'activo': True}
                            )

                        request.session['last_registro_ficha_id'] = nueva_ficha.id
                        request.session['last_registro_tipo'] = tipo
                        return redirect('registro_exito')
                except Exception as e:
                    logger.exception("Error al guardar ficha en registro_existente: %s", e)
                    messages.error(request, f'No se pudo completar el registro: {str(e)}')
                    return redirect(request.path)
                
            return render(request, 'teams/registro_existente.html', {
                'equipo': invitacion.equipo,
                'tipo': tipo,
                'ficha_anterior': ficha_anterior,
                'hide_navbar': True
            })
            
    # 2. Si no tiene cuenta o está logueado pero es su primera ficha
    if request.method == 'POST':
        if not request.POST.get('acepto_lopdp'):
            messages.error(request, 'Debes autorizar el tratamiento de tus datos personales (LOPDP) para continuar.')
            return redirect(request.path)

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
            form = PlayerRegistrationForm(request.POST, request.FILES, user=user_to_use, equipo=invitacion.equipo)
            
        if form.is_valid():
            # Check tournament constraints again for unauthenticated flow
            if invitacion.torneo and user_to_use:
                if tipo == 'dt':
                    ficha_existente = FichaDT.objects.filter(user=user_to_use, torneo=invitacion.torneo).select_related('equipo').first()
                else:
                    ficha_existente = FichaJugador.objects.filter(user=user_to_use, torneo=invitacion.torneo).select_related('equipo').first()
                    
                if ficha_existente:
                    nombre_torneo = invitacion.torneo.nombre
                    if ficha_existente.equipo == invitacion.equipo:
                        request.session['last_registro_ficha_id'] = ficha_existente.id
                        request.session['last_registro_tipo'] = tipo
                        messages.info(request, f'Ya te encuentras registrado en el equipo {invitacion.equipo.nombre} para el torneo {nombre_torneo}.')
                        return redirect('registro_exito')
                    else:
                        messages.error(request, f'Ya te encuentras registrado en el equipo "{ficha_existente.equipo.nombre if ficha_existente.equipo else "otro club"}" para el torneo {nombre_torneo}.')
                        return redirect(request.path)
            elif user_to_use:
                # Si no tiene torneo asignado, verificar si ya está en este equipo
                if tipo == 'dt':
                    ficha_existente = FichaDT.objects.filter(user=user_to_use, equipo=invitacion.equipo).first()
                else:
                    ficha_existente = FichaJugador.objects.filter(user=user_to_use, equipo=invitacion.equipo).first()
                if ficha_existente:
                    request.session['last_registro_ficha_id'] = ficha_existente.id
                    request.session['last_registro_tipo'] = tipo
                    messages.info(request, f'Ya te encuentras registrado en el equipo {invitacion.equipo.nombre}.')
                    return redirect('registro_exito')
                    
            if tipo == 'jugador':
                if invitacion.torneo:
                    num_jugadores_actuales = FichaJugador.objects.filter(
                        equipo=invitacion.equipo, 
                        torneo=invitacion.torneo,
                        es_lesionado=False
                    ).exclude(estado_validacion='rechazado').count()
                    if num_jugadores_actuales >= invitacion.torneo.max_jugadores_por_equipo:
                        messages.error(request, f'El equipo ya alcanzó el máximo de jugadores ({invitacion.torneo.max_jugadores_por_equipo}) permitidos en el torneo {invitacion.torneo.nombre}.')
                        return redirect(request.path)
                elif invitacion.equipo and invitacion.equipo.max_jugadores:
                    num_jugadores_actuales = FichaJugador.objects.filter(
                        equipo=invitacion.equipo,
                        es_lesionado=False
                    ).exclude(estado_validacion='rechazado').count()
                    if num_jugadores_actuales >= invitacion.equipo.max_jugadores:
                        messages.error(request, f'El equipo ya alcanzó el límite máximo de jugadores ({invitacion.equipo.max_jugadores}) permitidos.')
                        return redirect(request.path)
                    
            try:
                with transaction.atomic():
                    ficha = form.save(commit=False, equipo=invitacion.equipo, organizacion=org)
                    ficha.torneo = invitacion.torneo
                    ficha.organizacion = org
                    ficha.fecha_firma = timezone.now()

                    # Prevenir colisión de unique_together ('organizacion', 'user', 'torneo')
                    ModelClass = FichaDT if tipo == 'dt' else FichaJugador
                    ficha_previa = ModelClass.objects.filter(
                        organizacion=org,
                        user=ficha.user,
                        torneo=invitacion.torneo
                    ).first()

                    if ficha_previa:
                        ficha_previa.equipo = invitacion.equipo
                        ficha_previa.fecha_firma = timezone.now()
                        if getattr(ficha, 'numero_camiseta', None) is not None:
                            ficha_previa.numero_camiseta = ficha.numero_camiseta
                        if ficha.foto:
                            ficha_previa.foto = ficha.foto
                        if ficha.cedula_frontal:
                            ficha_previa.cedula_frontal = ficha.cedula_frontal
                        if ficha.cedula_posterior:
                            ficha_previa.cedula_posterior = ficha.cedula_posterior
                        if ficha.nro_cedula:
                            ficha_previa.nro_cedula = ficha.nro_cedula
                        if ficha.tipo_sangre:
                            ficha_previa.tipo_sangre = ficha.tipo_sangre
                        if ficha.contacto_emergencia:
                            ficha_previa.contacto_emergencia = ficha.contacto_emergencia
                        if ficha.telefono_emergencia:
                            ficha_previa.telefono_emergencia = ficha.telefono_emergencia
                        if ficha.firma_imagen:
                            ficha_previa.firma_imagen = ficha.firma_imagen
                            ficha_previa.firma_digital = True
                        elif getattr(ficha, 'firma_digital', False):
                            ficha_previa.firma_digital = True
                        ficha_previa.save()
                        ficha = ficha_previa
                    else:
                        ficha.save()

                    # Asegurar vinculación con UsuarioOrganizacion
                    if org and ficha.user:
                        from users.models import UsuarioOrganizacion
                        UsuarioOrganizacion.objects.get_or_create(
                            usuario=ficha.user,
                            organizacion=org,
                            defaults={'rol': tipo, 'activo': True}
                        )

                    request.session['last_registro_ficha_id'] = ficha.id
                    request.session['last_registro_tipo'] = tipo
                    return redirect('registro_exito')
            except IntegrityError as e:
                logger.exception("IntegrityError en registro_jugador: %s", e)
                messages.error(request, 'Ya existe un registro con estos datos en el sistema.')
                return redirect(request.path)
            except Exception as e:
                logger.exception("Error en registro_jugador: %s", e)
                messages.error(request, f'Ocurrió un error al procesar el registro: {str(e)}')
                return redirect(request.path)
    else:
        form_user = request.user if request.user.is_authenticated else None
        if tipo == 'dt':
            form = DTRegistrationForm(user=form_user)
        else:
            form = PlayerRegistrationForm(user=form_user, equipo=invitacion.equipo)
            
    template_name = 'teams/registro_dt.html' if tipo == 'dt' else 'teams/registro_jugador.html'
    return render(request, template_name, {
        'form': form,
        'equipo': invitacion.equipo,
        'hide_navbar': True
    })

def registro_exito(request):
    ficha_id = request.session.get('last_registro_ficha_id')
    tipo = request.session.get('last_registro_tipo', 'jugador')
    ficha = None
    if ficha_id:
        if tipo == 'dt':
            ficha = FichaDT.objects.filter(id=ficha_id).select_related('user', 'equipo', 'torneo').first()
        else:
            ficha = FichaJugador.objects.filter(id=ficha_id).select_related('user', 'equipo', 'torneo').first()

    return render(request, 'teams/registro_exito.html', {
        'hide_navbar': True,
        'ficha': ficha,
        'tipo': tipo
    })

@login_required
def secretaria_dashboard(request):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No tienes permisos para acceder al Módulo de Secretaría.")
        return redirect('club_portal')
        
    pendientes_jugadores = FichaJugador.objects.filter(organizacion=request.organizacion, estado_validacion='pendiente').select_related('user', 'equipo')
    pendientes_dt = FichaDT.objects.filter(organizacion=request.organizacion, estado_validacion='pendiente').select_related('user', 'equipo')
    
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

    # Historial reciente limitado a 25 registros en BD para máxima velocidad
    historial_jugadores = list(FichaJugador.objects.filter(organizacion=request.organizacion)
                               .exclude(estado_validacion='pendiente')
                               .select_related('user', 'equipo')
                               .order_by('-id')[:25])
    historial_dt = list(FichaDT.objects.filter(organizacion=request.organizacion)
                        .exclude(estado_validacion='pendiente')
                        .select_related('user', 'equipo')
                        .order_by('-id')[:25])
    
    # Historial reciente (sidebar rápido)
    historial = []
    for hj in historial_jugadores[:25]:
        hj.es_dt = False
        historial.append(hj)
    for hdt in historial_dt[:25]:
        hdt.es_dt = True
        historial.append(hdt)
    historial.sort(key=lambda x: x.id, reverse=True)
    historial = historial[:25]
    
    # Historial completo (para el modal "Ver Todos los Aceptados y Rechazados")
    todos_validados_jug = FichaJugador.objects.filter(
        organizacion=request.organizacion
    ).exclude(estado_validacion='pendiente').select_related('user', 'equipo').order_by('-id')
    
    todos_validados_dt = FichaDT.objects.filter(
        organizacion=request.organizacion
    ).exclude(estado_validacion='pendiente').select_related('user', 'equipo').order_by('-id')
    
    todos_validados = []
    aprobados_count = 0
    rechazados_count = 0
    for vj in todos_validados_jug:
        vj.es_dt = False
        if vj.estado_validacion == 'aprobado':
            aprobados_count += 1
        elif vj.estado_validacion == 'rechazado':
            rechazados_count += 1
        todos_validados.append(vj)
        
    for vdt in todos_validados_dt:
        vdt.es_dt = True
        if vdt.estado_validacion == 'aprobado':
            aprobados_count += 1
        elif vdt.estado_validacion == 'rechazado':
            rechazados_count += 1
        todos_validados.append(vdt)
        
    clubes_unicos = sorted(list(set([p.equipo.nombre for p in pendientes if p.equipo and p.equipo.nombre])))
    todos_validados.sort(key=lambda x: x.id, reverse=True)
    
    context = {
        'pendientes': pendientes,
        'jugador_actual': pendientes[0] if pendientes else None,
        'total_pendientes': len(pendientes),
        'clubes_unicos': clubes_unicos,
        'historial': historial,
        'todos_validados': todos_validados,
        'aprobados_count': aprobados_count,
        'rechazados_count': rechazados_count,
        'total_validados': len(todos_validados),
    }
    return render(request, 'teams/secretaria_dashboard.html', context)

@login_required
def aprobar_jugador(request, ficha_id):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    tipo = request.GET.get('tipo', 'jugador')
    if tipo == 'dt':
        ficha = get_object_or_404(FichaDT, id=ficha_id, organizacion=request.organizacion)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id, organizacion=request.organizacion)
        
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
        ficha = get_object_or_404(FichaDT, id=ficha_id, organizacion=request.organizacion)
    else:
        ficha = get_object_or_404(FichaJugador, id=ficha_id, organizacion=request.organizacion)
        
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
def aprobar_masivo(request):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        jugador_ids = request.POST.getlist('fichas_jugador')
        dt_ids = request.POST.getlist('fichas_dt')
        
        count_j = 0
        count_dt = 0
        ahora = timezone.now()
        
        if jugador_ids:
            count_j = FichaJugador.objects.filter(
                id__in=jugador_ids, 
                organizacion=request.organizacion,
                estado_validacion='pendiente'
            ).update(
                estado_validacion='aprobado',
                motivo_rechazo=None,
                fecha_aprobacion=ahora,
                aprobado_por=request.user
            )
            
        if dt_ids:
            count_dt = FichaDT.objects.filter(
                id__in=dt_ids, 
                organizacion=request.organizacion,
                estado_validacion='pendiente'
            ).update(
                estado_validacion='aprobado',
                motivo_rechazo=None,
                fecha_aprobacion=ahora,
                aprobado_por=request.user
            )
            
        total = count_j + count_dt
        if total > 0:
            messages.success(request, f"¡Éxito! Se han aprobado y habilitado {total} postulante(s) correctamente.")
        else:
            messages.warning(request, "No seleccionaste ninguna ficha para aprobar.")
            
    return redirect('secretaria_dashboard')

@login_required
def rechazar_masivo(request):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        jugador_ids = request.POST.getlist('fichas_jugador')
        dt_ids = request.POST.getlist('fichas_dt')
        motivo = request.POST.get('motivo_rechazo', 'Documentación incompleta o ilegible.')
        
        count_j = 0
        count_dt = 0
        
        if jugador_ids:
            count_j = FichaJugador.objects.filter(
                id__in=jugador_ids, 
                organizacion=request.organizacion,
                estado_validacion='pendiente'
            ).update(
                estado_validacion='rechazado',
                motivo_rechazo=motivo
            )
            
        if dt_ids:
            count_dt = FichaDT.objects.filter(
                id__in=dt_ids, 
                organizacion=request.organizacion,
                estado_validacion='pendiente'
            ).update(
                estado_validacion='rechazado',
                motivo_rechazo=motivo
            )
            
        total = count_j + count_dt
        if total > 0:
            messages.warning(request, f"Se han rechazado {total} postulante(s) con el motivo indicado.")
        else:
            messages.warning(request, "No seleccionaste ninguna ficha para rechazar.")
            
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
    
    categorias = Categoria.objects.filter(organizacion=request.organizacion).order_by('nombre')
    return render(request, 'teams/lista_categorias.html', {'categorias': categorias})


@login_required
def crear_categoria(request):
    if not (request.user.role in ['superadmin', 'secretaria'] or request.user.is_superuser):
        messages.error(request, "No tienes permisos para acceder a este módulo.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.organizacion = request.organizacion
            categoria.save()
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
        
    categoria = get_object_or_404(Categoria, id=categoria_id, organizacion=request.organizacion)
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
        
    categoria = get_object_or_404(Categoria, id=categoria_id, organizacion=request.organizacion)
    if request.method == 'POST':
        try:
            categoria.delete()
            messages.success(request, "Categoría eliminada con éxito.")
        except models.ProtectedError:
            messages.error(request, "No se puede eliminar la categoría porque hay equipos o torneos asociados a ella.")
        
    return redirect('lista_categorias')


@login_required
def descargar_plantilla_equipos(request):
    import io
    from django.http import HttpResponse

    if not request.user.has_module_access('equipos'):
        messages.error(request, "No tienes permiso para acceder a este módulo.")
        return redirect('club_portal')

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError:
        messages.error(request, "El generador de Excel (openpyxl) no está disponible en el servidor. Por favor ejecute pip install openpyxl.")
        return redirect('club_portal')

    try:
        categorias = list(Categoria.objects.filter(organizacion=request.organizacion).order_by('nombre'))
        cat_names = [c.nombre for c in categorias]

        wb = openpyxl.Workbook()

        # Hoja 1: Equipos
        ws_equipos = wb.active
        ws_equipos.title = "Equipos"
        ws_equipos.views.sheetView[0].showGridLines = True

        # Hoja 2: Categorías Habilitadas
        ws_cats = wb.create_sheet(title="Categorias_Habilitadas")
        ws_cats.views.sheetView[0].showGridLines = True
        ws_cats.append(["ID Categoría", "Nombre de Categoría"])

        header_fill_cats = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        header_font_cats = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        for col in range(1, 3):
            cell = ws_cats.cell(row=1, column=col)
            cell.fill = header_fill_cats
            cell.font = header_font_cats
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, c in enumerate(categorias, start=2):
            ws_cats.cell(row=idx, column=1, value=c.id)
            ws_cats.cell(row=idx, column=2, value=c.nombre)

        ws_cats.column_dimensions['A'].width = 15
        ws_cats.column_dimensions['B'].width = 30

        # Estilos para Hoja Equipos
        header_fill = PatternFill(start_color="1E3C72", end_color="1E3C72", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        headers = [
            "Nombre del Equipo (Obligatorio)",
            "Categorías (Obligatorio / Separadas por coma)",
            "Nombre Entrenador / DT (Opcional)",
            "Teléfono Entrenador (Opcional)",
            "Máximo Jugadores (Opcional)"
        ]
        ws_equipos.append(headers)

        for col_idx, h in enumerate(headers, start=1):
            cell = ws_equipos.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Filas de ejemplo
        ejemplos = [
            ["Real Madrid FC", cat_names[0] if cat_names else "Senior", "Zinedine Zidane", "+593987654321", 25],
            ["FC Barcelona", ", ".join(cat_names[:2]) if len(cat_names) >= 2 else "Senior, Máster", "Pep Guardiola", "+593987654322", 25],
        ]

        for row_data in ejemplos:
            ws_equipos.append(row_data)

        # Añadir DataValidation para la columna B (Categorías) en Excel usando rango dinámico
        if cat_names:
            last_row = len(cat_names) + 1
            formula_cats = f"Categorias_Habilitadas!$B$2:$B${last_row}"
            dv = DataValidation(type="list", formula1=formula_cats, allow_blank=True)
            dv.error = 'Por favor selecciona una categoría válida de la lista'
            dv.errorTitle = 'Categoría no válida'
            dv.prompt = 'Selecciona una categoría de la lista'
            dv.promptTitle = 'Categoría'
            ws_equipos.add_data_validation(dv)
            dv.add("B2:B100")

        # Anchos de columna
        column_widths = {'A': 32, 'B': 42, 'C': 30, 'D': 22, 'E': 22}
        for col_letter, width in column_widths.items():
            ws_equipos.column_dimensions[col_letter].width = width

        # Bordes y alineación para filas 2 a 100
        for row in range(2, 101):
            for col in range(1, 6):
                cell = ws_equipos.cell(row=row, column=col)
                cell.border = thin_border
                if col == 5:
                    cell.alignment = Alignment(horizontal="center")

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="Plantilla_Equipos_FutbolPro.xlsx"'
        return response
    except Exception as e:
        messages.error(request, f"Error al generar la plantilla Excel: {str(e)}")
        return redirect('club_portal')


@login_required
def cargar_equipos_excel(request):
    try:
        import openpyxl
    except ImportError:
        messages.error(request, "El módulo openpyxl no está instalado en el servidor.")
        return redirect('club_portal')

    if not request.user.has_module_access('equipos'):
        messages.error(request, "No tienes permiso para acceder a este módulo.")
        return redirect('club_portal')

    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']
        if not (archivo.name.endswith('.xlsx') or archivo.name.endswith('.xls')):
            messages.error(request, "El archivo debe ser en formato Excel (.xlsx o .xls).")
            return redirect('club_portal')

        try:
            wb = openpyxl.load_workbook(archivo, data_only=True)
            ws = wb.active
        except Exception as e:
            messages.error(request, f"Error al abrir el archivo Excel: {str(e)}")
            return redirect('club_portal')

        cats_org = Categoria.objects.filter(organizacion=request.organizacion)
        cat_map = {c.nombre.strip().lower(): c for c in cats_org}

        creados = 0
        omitidos = 0
        errores = []

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not any(row):
                continue

            nombre_equipo = str(row[0]).strip() if row[0] is not None else ""
            cat_str = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            entrenador = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            telefono_dt = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            max_jug = row[4] if len(row) > 4 and row[4] is not None else 25

            if not nombre_equipo or nombre_equipo.lower() in ['none', 'null']:
                continue

            if Equipo.objects.filter(organizacion=request.organizacion, nombre__iexact=nombre_equipo).exists():
                omitidos += 1
                errores.append(f"Fila {row_idx}: El equipo '{nombre_equipo}' ya existe en tu organización.")
                continue

            try:
                max_jugadores_val = int(max_jug)
                if max_jugadores_val < 5 or max_jugadores_val > 100:
                    max_jugadores_val = 25
            except (ValueError, TypeError):
                max_jugadores_val = 25

            equipo = Equipo.objects.create(
                nombre=nombre_equipo,
                entrenador=entrenador if entrenador and entrenador.lower() != 'none' else None,
                telefono_entrenador=telefono_dt if telefono_dt and telefono_dt.lower() != 'none' else None,
                max_jugadores=max_jugadores_val,
                dirigente=request.user,
                organizacion=request.organizacion
            )

            if cat_str and cat_str.lower() != 'none':
                raw_cats = [c.strip().lower() for c in cat_str.split(',') if c.strip()]
                matched_cats = []
                for rc in raw_cats:
                    if rc in cat_map:
                        matched_cats.append(cat_map[rc])
                    else:
                        for c_name, c_obj in cat_map.items():
                            if rc in c_name or c_name in rc:
                                matched_cats.append(c_obj)
                                break
                if matched_cats:
                    equipo.categorias.add(*matched_cats)

            creados += 1

        if creados > 0:
            messages.success(request, f"¡Importación exitosa! Se registraron {creados} equipo(s) en tu organización.")
        
        if omitidos > 0 or errores:
            detalles = "<br>".join(errores[:5])
            if len(errores) > 5:
                detalles += f"<br>... y {len(errores) - 5} observaciones más."
            messages.warning(request, f"Se omitieron {omitidos} registro(s) por duplicidad o formato:<br>{detalles}")

        return redirect('club_portal')

    messages.error(request, "No se seleccionó ningún archivo Excel para subir.")
    return redirect('club_portal')

