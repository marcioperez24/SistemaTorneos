from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import PagoInscripcion, MultaTarjeta, MovimientoCaja
from teams.models import Equipo
from matches.models import EventoPartido
from django.db.models import Sum
from decimal import Decimal

@login_required
def resumen_financiero(request):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No tienes autorización para acceder al Módulo de Tesorería.")
        return redirect('club_portal')

    # Garantizar que todos los equipos tengan un registro de PagoInscripcion creado (incluso si está pendiente)
    equipos = Equipo.objects.filter(organizacion=request.organizacion)
    for eq in equipos:
        PagoInscripcion.objects.get_or_create(
            equipo=eq,
            defaults={'monto': Decimal('1500.00'), 'estado': 'pendiente', 'organizacion': request.organizacion}
        )

    # Sincronizar automáticamente cualquier tarjeta roja o amarilla existente que no tenga multa generada
    eventos_tarjeta = EventoPartido.objects.filter(
        partido__organizacion=request.organizacion,
        tipo__in=['amarilla', 'roja', 'AMARILLA', 'ROJA']
    ).exclude(multa_tarjeta__isnull=False).select_related('partido', 'partido__torneo', 'equipo', 'jugador')

    for ev in eventos_tarjeta:
        tipo_str = str(ev.tipo).lower().strip()
        torneo = ev.partido.torneo if ev.partido else None
        if tipo_str == 'amarilla':
            costo = torneo.costo_amarilla if (torneo and torneo.costo_amarilla is not None) else Decimal('50.00')
        else:
            costo = torneo.costo_roja if (torneo and torneo.costo_roja is not None) else Decimal('150.00')

        eq = ev.equipo
        if not eq and ev.jugador:
            fichas = getattr(ev.jugador, 'fichas_jugador', None)
            if fichas:
                f = fichas.filter(torneo=torneo).first() if torneo else fichas.first()
                if f:
                    eq = f.equipo
        if not eq and ev.partido:
            eq = ev.partido.equipo_local

        if eq:
            MultaTarjeta.objects.get_or_create(
                evento=ev,
                defaults={
                    'partido': ev.partido,
                    'equipo': eq,
                    'jugador': ev.jugador,
                    'organizacion': request.organizacion,
                    'monto': Decimal(str(costo)),
                    'motivo': tipo_str,
                    'estado': 'pendiente'
                }
            )

    # Totales y Cálculos Financieros
    total_inscripciones = PagoInscripcion.objects.filter(organizacion=request.organizacion, estado='pagado').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    total_multas = MultaTarjeta.objects.filter(organizacion=request.organizacion, estado='pagado').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    
    # Egresos registrados en caja
    total_egresos = MovimientoCaja.objects.filter(organizacion=request.organizacion, tipo='egreso').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')

    total_ingresos = total_inscripciones + total_multas
    # Sumar otros ingresos cargados manualmente a la caja
    total_otros_ingresos = MovimientoCaja.objects.filter(organizacion=request.organizacion, tipo='ingreso', concepto__startswith='Ingreso Extra:').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    total_ingresos += total_otros_ingresos

    balance_caja = total_ingresos - total_egresos

    # Consultas detalladas
    pagos_inscripcion = PagoInscripcion.objects.filter(organizacion=request.organizacion).select_related('equipo')
    multas = MultaTarjeta.objects.filter(organizacion=request.organizacion).select_related('jugador', 'equipo', 'partido').order_by('-id')
    movimientos = MovimientoCaja.objects.filter(organizacion=request.organizacion).select_related('registrado_por').order_by('-fecha')[:50]

    context = {
        'total_inscripciones': total_inscripciones,
        'total_multas': total_multas,
        'total_egresos': total_egresos,
        'total_ingresos': total_ingresos,
        'balance': balance_caja,
        'pagos_inscripcion': pagos_inscripcion,
        'multas': multas,
        'movimientos': movimientos,
        'equipos': equipos,
    }
    return render(request, 'finances/resumen.html', context)


@login_required
def modificar_cuota_equipo(request, pago_id):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No tienes autorización para modificar cuotas.")
        return redirect('club_portal')
        
    pago = get_object_or_404(PagoInscripcion, id=pago_id, organizacion=request.organizacion)
    if request.method == 'POST':
        try:
            nuevo_monto = Decimal(request.POST.get('monto', '0'))
            if nuevo_monto < Decimal('0'):
                messages.error(request, "El monto de la cuota no puede ser negativo.")
                return redirect('resumen_financiero')
            pago.monto = nuevo_monto
            if 'notas' in request.POST:
                pago.notas = request.POST.get('notas')
            pago.save()
            messages.success(request, f"Cuota de inscripción de '{pago.equipo.nombre}' actualizada a $ {pago.monto:.2f}.")
        except Exception as e:
            messages.error(request, f"Error al modificar monto de cuota: {str(e)}")
            
    return redirect('resumen_financiero')


@login_required
def registrar_pago_inscripcion(request, pago_id):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    pago = get_object_or_404(PagoInscripcion, id=pago_id, organizacion=request.organizacion)
    if request.method == 'POST':
        monto_post = request.POST.get('monto')
        if monto_post:
            try:
                nuevo_monto = Decimal(monto_post)
                if nuevo_monto >= Decimal('0'):
                    pago.monto = nuevo_monto
            except Exception:
                pass
        metodo = request.POST.get('metodo_pago', 'efectivo')
        pago.estado = 'pagado'
        pago.metodo_pago = metodo
        pago.fecha_pago = timezone.now()
        pago.save()

        # Registrar en la Bitácora de Caja General
        MovimientoCaja.objects.create(
            organizacion=request.organizacion,
            tipo='ingreso',
            monto=pago.monto,
            concepto=f"Pago Inscripción - Club: {pago.equipo.nombre}",
            registrado_por=request.user
        )

        messages.success(request, f"¡Pago de inscripción del club {pago.equipo.nombre} registrado con éxito ($ {pago.monto:.2f})!")
    return redirect('resumen_financiero')


@login_required
def pagar_multa(request, multa_id):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    multa = get_object_or_404(MultaTarjeta, id=multa_id, organizacion=request.organizacion)
    multa.estado = 'pagado'
    multa.fecha_pago = timezone.now()
    multa.save()

    jugador_nom = (multa.jugador.get_full_name() or multa.jugador.username) if multa.jugador else (multa.equipo.nombre if multa.equipo else "Equipo")

    # Registrar en la Bitácora de Caja
    MovimientoCaja.objects.create(
        organizacion=request.organizacion,
        tipo='ingreso',
        monto=multa.monto,
        concepto=f"Cobro Multa ({multa.get_motivo_display()}) - {jugador_nom}",
        registrado_por=request.user
    )

    messages.success(request, f"Multa cobrada y registrada con éxito ($ {multa.monto:.2f}).")
    return redirect('resumen_financiero')


@login_required
def registrar_multa_manual(request):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No tienes autorización para registrar multas.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        equipo_id = request.POST.get('equipo_id')
        equipo = get_object_or_404(Equipo, id=equipo_id, organizacion=request.organizacion)
        motivo = request.POST.get('motivo', 'roja')
        monto = request.POST.get('monto')
        
        try:
            monto_dec = Decimal(monto) if monto else Decimal('150.00')
            multa = MultaTarjeta.objects.create(
                organizacion=request.organizacion,
                equipo=equipo,
                motivo=motivo,
                monto=monto_dec,
                estado='pendiente'
            )
            messages.success(request, f"Sanción / Multa ({multa.get_motivo_display()}) registrada con éxito para {equipo.nombre} por $ {monto_dec:.2f}.")
        except Exception as e:
            messages.error(request, f"Error al registrar multa: {str(e)}")
            
    return redirect('resumen_financiero')


@login_required
def registrar_egreso(request):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    if request.method == 'POST':
        monto = request.POST.get('monto')
        concepto = request.POST.get('concepto')
        
        MovimientoCaja.objects.create(
            organizacion=request.organizacion,
            tipo='egreso',
            monto=monto,
            concepto=f"Gasto: {concepto}",
            registrado_por=request.user
        )
        messages.warning(request, f"Egreso de $ {monto} registrado en la caja chica.")
        
    return redirect('resumen_financiero')
