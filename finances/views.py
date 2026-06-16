from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import PagoInscripcion, MultaTarjeta, MovimientoCaja
from teams.models import Equipo
from django.db.models import Sum

from decimal import Decimal

@login_required
def resumen_financiero(request):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No tienes autorización para acceder al Módulo de Tesorería.")
        return redirect('club_portal')

    # Garantizar que todos los equipos tengan un registro de PagoInscripcion creado (incluso si está pendiente)
    equipos = Equipo.objects.all()
    for eq in equipos:
        PagoInscripcion.objects.get_or_create(
            equipo=eq,
            defaults={'monto': Decimal('1500.00'), 'estado': 'pendiente'}
        )

    # Totales y Cálculos Financieros
    total_inscripciones = PagoInscripcion.objects.filter(estado='pagado').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    total_multas = MultaTarjeta.objects.filter(estado='pagado').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    
    # Egresos registrados en caja
    total_egresos = MovimientoCaja.objects.filter(tipo='egresó').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    # O por si registramos el egreso genérico
    total_egresos_caja = MovimientoCaja.objects.filter(tipo='egreso').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    total_egresos = total_egresos + total_egresos_caja

    total_ingresos = total_inscripciones + total_multas
    # Sumar otros ingresos cargados manualmente a la caja
    total_otros_ingresos = MovimientoCaja.objects.filter(tipo='ingreso', concepto__startswith='Ingreso Extra:').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.00')
    total_ingresos += total_otros_ingresos

    balance_caja = total_ingresos - total_egresos

    # Consultas detalladas
    pagos_inscripcion = PagoInscripcion.objects.all().select_related('equipo')
    multas = MultaTarjeta.objects.all().select_related('jugador', 'equipo', 'partido')
    movimientos = MovimientoCaja.objects.all().select_related('registrado_por').order_by('-fecha')[:50]

    context = {
        'total_inscripciones': total_inscripciones,
        'total_multas': total_multas,
        'total_egresos': total_egresos,
        'total_ingresos': total_ingresos,
        'balance': balance_caja,
        'pagos_inscripcion': pagos_inscripcion,
        'multas': multas,
        'movimientos': movimientos
    }
    return render(request, 'finances/resumen.html', context)


@login_required
def registrar_pago_inscripcion(request, pago_id):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    pago = get_object_or_404(PagoInscripcion, id=pago_id)
    if request.method == 'POST':
        metodo = request.POST.get('metodo_pago', 'efectivo')
        pago.estado = 'pagado'
        pago.metodo_pago = metodo
        pago.fecha_pago = timezone.now()
        pago.save()

        # Registrar en la Bitácora de Caja General
        MovimientoCaja.objects.create(
            tipo='ingreso',
            monto=pago.monto,
            concepto=f"Pago Inscripción - Club: {pago.equipo.nombre}",
            registrado_por=request.user
        )

        messages.success(request, f"¡Pago de inscripción del club {pago.equipo.nombre} registrado con éxito!")
    return redirect('resumen_financiero')


@login_required
def pagar_multa(request, multa_id):
    if request.user.role not in ['tesorero', 'tesoreria', 'superadmin']:
        messages.error(request, "No autorizado.")
        return redirect('club_portal')
        
    multa = get_object_or_404(MultaTarjeta, id=multa_id)
    multa.estado = 'pagado'
    multa.fecha_pago = timezone.now()
    multa.save()

    # Registrar en la Bitácora de Caja
    MovimientoCaja.objects.create(
        tipo='ingreso',
        monto=multa.monto,
        concepto=f"Cobro Multa ({multa.get_motivo_display()}) - Jugador: {multa.jugador.get_full_name() or multa.jugador.username}",
        registrado_por=request.user
    )

    messages.success(request, f"Multa cobrada y registrada con éxito.")
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
            tipo='egreso',
            monto=monto,
            concepto=f"Gasto: {concepto}",
            registrado_por=request.user
        )
        messages.warning(request, f"Egreso de C$ {monto} registrado en la caja chica.")
        
    return redirect('resumen_financiero')
