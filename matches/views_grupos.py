from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.views.decorators.http import require_POST

from .models import Torneo, GrupoTorneo, EquipoGrupoTorneo, Partido
from teams.models import Equipo
from .forms import GrupoTorneoForm


def _verificar_permiso_gestion(request):
    """Auxiliar para comprobar permisos de superadmin o comisión."""
    return request.user.role in ['superadmin', 'comision']


@login_required
def configurar_grupos_torneo(request, torneo_id):
    """
    Vista principal de configuración de grupos para un torneo de tipo 'personalizado'.
    Muestra el resumen superior, la grilla de grupos con sus equipos y la lista de equipos disponibles.
    """
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para administrar grupos de torneos.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    grupos = GrupoTorneo.objects.filter(torneo=torneo).prefetch_related('equipos_asignados__equipo').order_by('orden', 'id')

    # Equipos asignados actualmente a cualquier grupo del torneo
    equipos_asignados_ids = EquipoGrupoTorneo.objects.filter(torneo=torneo).values_list('equipo_id', flat=True)

    # Equipos candidatos en la misma organización que no están en ningún grupo de este torneo
    equipos_candidatos = Equipo.objects.filter(
        organizacion=request.organizacion
    ).exclude(id__in=equipos_asignados_ids).order_by('nombre')

    # Respetar categoría principal y relaciones múltiples de categorías
    equipos_disponibles = [eq for eq in equipos_candidatos if eq.pertenece_a_categoria(torneo.categoria)]

    # Cálculo de métricas superiores
    grupos_activos_count = grupos.filter(activo=True).count()
    total_equipos_asignados = len(equipos_asignados_ids)
    total_equipos_disponibles = len(equipos_disponibles)
    total_cupos_clasificacion = sum(g.cupos_clasificacion for g in grupos)

    grupo_form = GrupoTorneoForm()

    context = {
        'torneo': torneo,
        'grupos': grupos,
        'equipos_disponibles': equipos_disponibles,
        'grupos_activos_count': grupos_activos_count,
        'total_equipos_asignados': total_equipos_asignados,
        'total_equipos_disponibles': total_equipos_disponibles,
        'total_cupos_clasificacion': total_cupos_clasificacion,
        'grupo_form': grupo_form,
    }
    return render(request, 'matches/configurar_grupos_torneo.html', context)


@login_required
@require_POST
def crear_grupo_torneo(request, torneo_id):
    """Crea un nuevo grupo dentro del torneo personalizado."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )

    form = GrupoTorneoForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                grupo = form.save(commit=False)
                grupo.torneo = torneo
                grupo.save()
                messages.success(request, f"Grupo '{grupo.nombre}' creado correctamente.")
        except Exception as e:
            messages.error(request, f"Error al crear el grupo: {str(e)}")
    else:
        for error in form.non_field_errors():
            messages.error(request, error)
        for field, errors in form.errors.items():
            if field != '__all__':
                field_label = form.fields[field].label or field
                for err in errors:
                    messages.error(request, f"{field_label}: {err}")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)


@login_required
@require_POST
def editar_grupo_torneo(request, torneo_id, grupo_id):
    """Edita la configuración de un grupo existente."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    grupo = get_object_or_404(GrupoTorneo, id=grupo_id, torneo=torneo)

    form = GrupoTorneoForm(request.POST, instance=grupo)
    if form.is_valid():
        try:
            with transaction.atomic():
                grupo_editado = form.save()
                messages.success(request, f"Grupo '{grupo_editado.nombre}' actualizado correctamente.")
        except Exception as e:
            messages.error(request, f"Error al actualizar el grupo: {str(e)}")
    else:
        for field, errors in form.errors.items():
            field_label = form.fields[field].label or field if field in form.fields else field
            for err in errors:
                messages.error(request, f"{field_label}: {err}")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)


@login_required
@require_POST
def eliminar_grupo_torneo(request, torneo_id, grupo_id):
    """Elimina un grupo únicamente si está vacío y no posee partidos registrados."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    grupo = get_object_or_404(GrupoTorneo, id=grupo_id, torneo=torneo)

    # Regla: No eliminar si tiene equipos asignados
    if grupo.equipos_asignados.exists():
        messages.error(request, "No puedes eliminar un grupo que todavía contiene equipos. Retira primero los equipos del grupo.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    # Regla: No eliminar si existen partidos del torneo asociados a este grupo
    if Partido.objects.filter(torneo=torneo, grupo=grupo.nombre).exists():
        messages.error(request, "No se puede eliminar un grupo que ya posee enfrentamientos registrados.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    with transaction.atomic():
        nombre_grupo = grupo.nombre
        grupo.delete()
        messages.success(request, f"El grupo '{nombre_grupo}' fue eliminado correctamente.")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)


@login_required
@require_POST
def cambiar_estado_grupo_torneo(request, torneo_id, grupo_id):
    """Activa o desactiva un grupo."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    grupo = get_object_or_404(GrupoTorneo, id=grupo_id, torneo=torneo)

    with transaction.atomic():
        grupo.activo = not grupo.activo
        grupo.save()
        estado_str = "activado" if grupo.activo else "desactivado"
        messages.success(request, f"Grupo '{grupo.nombre}' {estado_str} correctamente.")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)


@login_required
@require_POST
def agregar_equipo_grupo(request, torneo_id, grupo_id):
    """Asigna un equipo disponible a un grupo del torneo personalizado."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    grupo = get_object_or_404(GrupoTorneo, id=grupo_id, torneo=torneo)

    equipo_id = request.POST.get('equipo_id')
    if not equipo_id:
        messages.error(request, "Debes seleccionar un equipo válido.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    equipo = get_object_or_404(Equipo, id=equipo_id, organizacion=request.organizacion)

    # Validar categoría
    if not equipo.pertenece_a_categoria(torneo.categoria):
        messages.error(request, f"El equipo '{equipo.nombre}' no pertenece a la categoría de este torneo.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    # Validar que no esté ya asignado a ningún grupo de este torneo
    if EquipoGrupoTorneo.objects.filter(torneo=torneo, equipo=equipo).exists():
        messages.warning(request, f"El equipo '{equipo.nombre}' ya está asignado a un grupo en este torneo.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    with transaction.atomic():
        # Crear asignación
        EquipoGrupoTorneo.objects.create(
            torneo=torneo,
            grupo=grupo,
            equipo=equipo
        )
        # Regla coherente: Asegurar que el equipo también esté inscrito en torneo.equipos
        if not torneo.equipos.filter(id=equipo.id).exists():
            torneo.equipos.add(equipo)

        messages.success(request, f"Equipo '{equipo.nombre}' fue asignado al '{grupo.nombre}' correctamente.")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)


@login_required
@require_POST
def mover_equipo_grupo(request, torneo_id, asignacion_id):
    """Mueve un equipo de su grupo actual a un grupo de destino."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    asignacion = get_object_or_404(EquipoGrupoTorneo, id=asignacion_id, torneo=torneo)

    grupo_destino_id = request.POST.get('grupo_destino_id')
    if not grupo_destino_id:
        messages.error(request, "Debes seleccionar un grupo de destino.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    grupo_destino = get_object_or_404(GrupoTorneo, id=grupo_destino_id, torneo=torneo)

    if asignacion.grupo == grupo_destino:
        messages.warning(request, "El equipo ya se encuentra en ese grupo.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    # Bloqueo en Fase 2 si el equipo ya posee partidos registrados en el torneo
    partidos_existentes = Partido.objects.filter(torneo=torneo).filter(
        models.Q(equipo_local=asignacion.equipo) | models.Q(equipo_visitante=asignacion.equipo)
    )
    if partidos_existentes.exists():
        messages.warning(
            request, 
            "No se puede mover este equipo porque ya tiene enfrentamientos registrados en la fase de grupos. "
            "La modificación segura de grupos con fixtures existentes se implementará en la Fase 3."
        )
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    with transaction.atomic():
        grupo_origen_nombre = asignacion.grupo.nombre
        asignacion.grupo = grupo_destino
        asignacion.save()
        messages.success(request, f"Equipo '{asignacion.equipo.nombre}' fue movido del '{grupo_origen_nombre}' al '{grupo_destino.nombre}'.")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)


@login_required
@require_POST
def retirar_equipo_grupo(request, torneo_id, asignacion_id):
    """Retira un equipo de su grupo sin eliminar el equipo del sistema."""
    if not _verificar_permiso_gestion(request):
        messages.error(request, "No tienes autorización para realizar esta operación.")
        return redirect('partidos_lista')

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id,
        organizacion=request.organizacion,
        tipo='personalizado'
    )
    asignacion = get_object_or_404(EquipoGrupoTorneo, id=asignacion_id, torneo=torneo)

    # Bloqueo si el equipo ya posee partidos registrados en el torneo
    partidos_existentes = Partido.objects.filter(torneo=torneo).filter(
        models.Q(equipo_local=asignacion.equipo) | models.Q(equipo_visitante=asignacion.equipo)
    )
    if partidos_existentes.exists():
        messages.warning(request, f"No se puede retirar al equipo '{asignacion.equipo.nombre}' porque ya posee partidos registrados en este torneo.")
        return redirect('configurar_grupos_torneo', torneo_id=torneo.id)

    with transaction.atomic():
        equipo_nombre = asignacion.equipo.nombre
        grupo_nombre = asignacion.grupo.nombre
        asignacion.delete()
        messages.success(request, f"El equipo '{equipo_nombre}' fue retirado del '{grupo_nombre}'.")

    return redirect('configurar_grupos_torneo', torneo_id=torneo.id)
