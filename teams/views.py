from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import Equipo, InvitacionEquipo, FichaJugador
from .forms import EquipoForm, PlayerRegistrationForm
from django.contrib.auth.forms import AuthenticationForm

def login_view(request):
    if request.user.is_authenticated:
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
    # Redireccionar jugadores a su carnet o estado de validación
    if request.user.role == 'jugador':
        try:
            ficha = request.user.ficha_jugador
            if ficha.estado_validacion == 'aprobado':
                return redirect('ver_carnet', ficha_id=ficha.id)
            else:
                return render(request, 'teams/registro_exito.html', {'ficha': ficha, 'hide_navbar': False})
        except FichaJugador.DoesNotExist:
            messages.error(request, "No tienes una ficha de registro asociada a tu cuenta.")
            logout(request)
            return redirect('login')

    if not request.user.has_module_access('equipos'):
        messages.error(request, "No tienes permisos para acceder al Portal del Club.")
        return redirect('gestion_usuarios') if request.user.role == 'superadmin' else redirect('/login/')

    # Equipos que administra: si es superadmin, comision o superuser ve todos
    if request.user.role in ['superadmin', 'comision'] or request.user.is_superuser:
        equipos = Equipo.objects.all()
    else:
        equipos = Equipo.objects.filter(dirigente=request.user)
    
    # Obtener el nuevo enlace de la sesión y eliminarlo para que solo aparezca una vez
    nuevo_enlace = request.session.pop('nuevo_enlace', None)
    nuevo_enlace_equipo_id = request.session.pop('nuevo_enlace_equipo_id', None)
    
    context = {
        'equipos': equipos,
        'nuevo_enlace': nuevo_enlace,
        'nuevo_enlace_equipo_id': nuevo_enlace_equipo_id,
    }
    return render(request, 'teams/club_portal.html', context)

@login_required
def crear_equipo(request):
    if not request.user.has_module_access('equipos'):
        return redirect('club_portal')
        
    if request.method == 'POST':
        form = EquipoForm(request.POST, request.FILES)
        if form.is_valid():
            equipo = form.save(commit=False)
            equipo.dirigente = request.user
            equipo.save()
            messages.success(request, f"Equipo '{equipo.nombre}' creado exitosamente.")
            return redirect('club_portal')
    else:
        form = EquipoForm()
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
        form = EquipoForm(request.POST, request.FILES, instance=equipo)
        if form.is_valid():
            form.save()
            messages.success(request, f"Equipo '{equipo.nombre}' actualizado exitosamente.")
            return redirect('club_portal')
    else:
        form = EquipoForm(instance=equipo)
    return render(request, 'teams/crear_equipo.html', {'form': form, 'edit_mode': True, 'equipo': equipo})

@login_required
def generar_invitacion(request, equipo_id):
    if request.user.role == 'superadmin' or request.user.is_superuser:
        equipo = get_object_or_404(Equipo, id=equipo_id)
    else:
        equipo = get_object_or_404(Equipo, id=equipo_id, dirigente=request.user)
    
    # Desactivar invitaciones anteriores para este equipo
    InvitacionEquipo.objects.filter(equipo=equipo, activo=True).update(activo=False)
    
    # Crear nueva invitación válida por 48 horas
    expira = timezone.now() + timedelta(hours=48)
    invitacion = InvitacionEquipo.objects.create(
        equipo=equipo,
        expira_en=expira
    )
    
    # Construir URL absoluta del enlace
    enlace = request.build_absolute_uri(f"/invitacion/{invitacion.token}/")
    messages.success(request, f"¡Enlace de invitación generado con éxito! Válido por 48 horas.")
    
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
        
    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            ficha = form.save(equipo=invitacion.equipo)
            # Inscribimos al jugador firmando digitalmente con la fecha actual
            ficha.fecha_firma = timezone.now()
            ficha.save()
            return redirect('registro_exito')
    else:
        form = PlayerRegistrationForm()
        
    return render(request, 'teams/registro_jugador.html', {
        'form': form,
        'equipo': invitacion.equipo,
        'hide_navbar': True
    })

def registro_exito(request):
    return render(request, 'teams/registro_exito.html', {'hide_navbar': True})

@login_required
def secretaria_dashboard(request):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No tienes permisos para acceder al Módulo de Secretaría.")
        return redirect('club_portal')
        
    pendientes = FichaJugador.objects.filter(estado_validacion='pendiente').select_related('user', 'equipo')
    historial = FichaJugador.objects.exclude(estado_validacion='pendiente').select_related('user', 'equipo').order_by('-id')[:50] # Traer últimos 50
    
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
        
    ficha = get_object_or_404(FichaJugador, id=ficha_id)
    ficha.estado_validacion = 'aprobado'
    ficha.motivo_rechazo = None
    ficha.fecha_aprobacion = timezone.now()
    ficha.aprobado_por = request.user
    ficha.save()
    messages.success(request, f"El carnet de {ficha.user.get_full_name() or ficha.user.username} ha sido Aprobado y Habilitado.")
    return redirect('secretaria_dashboard')

@login_required
def rechazar_jugador(request, ficha_id):
    if not request.user.has_module_access('secretaria'):
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    ficha = get_object_or_404(FichaJugador, id=ficha_id)
    if request.method == 'POST':
        motivo = request.POST.get('motivo_rechazo', 'Documentación ilegible o incompleta.')
        ficha.estado_validacion = 'rechazado'
        ficha.motivo_rechazo = motivo
        ficha.save()
        messages.warning(request, f"El carnet de {ficha.user.get_full_name() or ficha.user.username} ha sido Rechazado.")
    return redirect('secretaria_dashboard')

@login_required
def ver_carnet(request, ficha_id):
    ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    # Validar permisos para ver el carnet
    es_propietario = request.user == ficha.user
    es_su_dirigente = ficha.equipo and request.user == ficha.equipo.dirigente
    es_comision_o_admin = request.user.role in ['comision', 'superadmin']
    
    if not (es_propietario or es_su_dirigente or es_comision_o_admin):
        messages.error(request, "No tienes permisos para ver el carnet de este jugador.")
        return redirect('club_portal')
        
    if ficha.estado_validacion != 'aprobado':
        messages.error(request, "Este carnet aún no está habilitado.")
        return redirect('club_portal')
        
    # URL de verificación pública
    verif_url = request.build_absolute_uri(f"/verificar/jugador/{ficha.id}/")
    # Generamos la URL del código QR dinámico
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={verif_url}"
    
    context = {
        'ficha': ficha,
        'qr_url': qr_url
    }
    return render(request, 'teams/carnet.html', context)

def verificar_jugador(request, ficha_id):
    ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    context = {
        'ficha': ficha,
    }
    return render(request, 'teams/verificar_jugador.html', context)

@login_required
def ver_ficha(request, ficha_id):
    ficha = get_object_or_404(FichaJugador, id=ficha_id)
    
    es_propietario = request.user == ficha.user
    es_su_dirigente = ficha.equipo and request.user == ficha.equipo.dirigente
    es_comision_o_admin = request.user.role in ['comision', 'superadmin'] or request.user.is_superuser
    
    if not (es_propietario or es_su_dirigente or es_comision_o_admin):
        messages.error(request, "No tienes permisos para ver la ficha de este jugador.")
        return redirect('club_portal')
        
    context = {
        'ficha': ficha,
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

