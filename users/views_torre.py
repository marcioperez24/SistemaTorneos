from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Organizacion

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def torre_control(request):
    organizaciones = Organizacion.objects.all().order_by('-fecha_creacion')
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        codigo = request.POST.get('codigo')
        if nombre and codigo:
            Organizacion.objects.create(nombre=nombre, codigo=codigo)
            messages.success(request, f"Organización {nombre} creada.")
            return redirect('torre_control')
    return render(request, 'users/torre_control.html', {'organizaciones': organizaciones})

@login_required
@user_passes_test(is_superuser)
def editar_org(request, org_id):
    org = get_object_or_404(Organizacion, id=org_id)
    if request.method == 'POST':
        org.nombre = request.POST.get('nombre', org.nombre)
        org.codigo = request.POST.get('codigo', org.codigo)
        org.estado = request.POST.get('estado', org.estado)
        org.save()
        messages.success(request, f"Organización {org.nombre} actualizada correctamente.")
        return redirect('torre_control')
    return render(request, 'users/editar_org.html', {'org': org})

@login_required
@user_passes_test(is_superuser)
def ver_org(request, org_id):
    org = get_object_or_404(Organizacion, id=org_id)
    return render(request, 'users/ver_org.html', {'org': org})

@login_required
@user_passes_test(is_superuser)
def entrar_org(request, org_id):
    org = get_object_or_404(Organizacion, id=org_id)
    request.session['current_organizacion_id'] = org.id
    messages.success(request, f"Has entrado a la organización {org.nombre} como Superadministrador.")
    return redirect('club_portal')
