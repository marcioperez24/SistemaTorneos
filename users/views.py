from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import RolePermission

User = get_user_model()

@login_required
def gestion_usuarios(request):
    if request.user.role != 'superadmin' and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para acceder a la gestión de usuarios.")
        return redirect('club_portal')

    usuarios = User.objects.all().order_by('-id')
    role_choices = User.ROLE_CHOICES
    
    modules = [
        ('partidos', '⚽ Partidos y Fixture'),
        ('equipos', '🛡️ Portal del Club / Registro'),
        ('vocalia', '📝 Vocalía de Campo'),
        ('secretaria', '📋 Secretaría (Validación de Carnets)'),
        ('tesoreria', '💳 Tesorería y Caja chica'),
    ]
    
    permisos_roles = {}
    for r_code, r_name in role_choices:
        permisos_roles[r_code] = {}
        for m_code, m_name in modules:
            perm = RolePermission.objects.filter(role=r_code, module=m_code).first()
            if perm:
                permisos_roles[r_code][m_code] = perm.allowed
            else:
                defaults = {
                    'partidos': ['superadmin', 'comision', 'vocal'],
                    'equipos': ['dirigente'],
                    'vocalia': ['vocal'],
                    'secretaria': ['comision'],
                    'tesoreria': ['tesorero', 'tesoreria'],
                }
                permisos_roles[r_code][m_code] = r_code in defaults.get(m_code, [])

    context = {
        'usuarios': usuarios,
        'role_choices': role_choices,
        'modules': modules,
        'permisos_roles': permisos_roles,
    }
    return render(request, 'users/gestion_usuarios.html', context)

@login_required
def crear_usuario(request):
    if request.user.role != 'superadmin' and not request.user.is_superuser:
        return redirect('club_portal')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        role = request.POST.get('role')
        password = request.POST.get('password')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f"El nombre de usuario '{username}' ya existe.")
            return redirect('gestion_usuarios')
            
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            role=role,
            telefono=telefono
        )
        messages.success(request, f"Usuario '{user.username}' creado con éxito.")
    return redirect('gestion_usuarios')

@login_required
def editar_usuario(request, user_id):
    if request.user.role != 'superadmin' and not request.user.is_superuser:
        return redirect('club_portal')
        
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.telefono = request.POST.get('telefono')
        user.role = request.POST.get('role')
        
        password = request.POST.get('password')
        if password and password.strip() != "":
            user.set_password(password)
            
        user.save()
        messages.success(request, f"Usuario '{user.username}' actualizado.")
    return redirect('gestion_usuarios')

@login_required
def eliminar_usuario(request, user_id):
    if request.user.role != 'superadmin' and not request.user.is_superuser:
        return redirect('club_portal')
        
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, "No puedes eliminarte a ti mismo.")
    else:
        username = user.username
        user.delete()
        messages.warning(request, f"Usuario '{username}' eliminado permanentemente.")
    return redirect('gestion_usuarios')

@login_required
def guardar_permisos(request):
    if request.user.role != 'superadmin' and not request.user.is_superuser:
        return redirect('club_portal')
        
    if request.method == 'POST':
        role_choices = User.ROLE_CHOICES
        modules = ['partidos', 'equipos', 'vocalia', 'secretaria', 'tesoreria']
        
        for r_code, _ in role_choices:
            for m_code in modules:
                checkbox_name = f"perm_{r_code}_{m_code}"
                allowed = checkbox_name in request.POST
                
                RolePermission.objects.update_or_create(
                    role=r_code,
                    module=m_code,
                    defaults={'allowed': allowed}
                )
                
        messages.success(request, "Permisos de roles actualizados y aplicados con éxito.")
    return redirect('gestion_usuarios')
