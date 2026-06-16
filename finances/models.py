from django.db import models
from django.conf import settings
from teams.models import Equipo
from matches.models import Partido, EventoPartido

class PagoInscripcion(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
    )
    METODOS = (
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'),
        ('billetera_movil', 'Billetera Móvil'),
    )

    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='pagos_inscripcion', verbose_name="Equipo")
    monto = models.DecimalField(max_digits=10, decimal_places=2, default=1500.00, verbose_name="Monto (C$)")
    fecha_pago = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Pago")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name="Estado de Pago")
    metodo_pago = models.CharField(max_length=50, choices=METODOS, null=True, blank=True, verbose_name="Método de Pago")
    comprobante = models.ImageField(upload_to="comprobantes/", null=True, blank=True, verbose_name="Comprobante / Recibo")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas/Observaciones")

    class Meta:
        verbose_name = "Pago de Inscripción"
        verbose_name_plural = "Pagos de Inscripciones"

    def __str__(self):
        return f"Inscripción {self.equipo.nombre} - {self.get_estado_display()} ({self.monto} C$)"


class MultaTarjeta(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente de Pago'),
        ('pagado', 'Pagado'),
    )
    MOTIVOS = (
        ('amarilla', 'Tarjeta Amarilla (C$ 50.00)'),
        ('roja', 'Tarjeta Roja (C$ 150.00)'),
    )

    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='multas', verbose_name="Partido")
    evento = models.OneToOneField(EventoPartido, on_delete=models.CASCADE, related_name='multa_tarjeta', verbose_name="Incidencia de Tarjeta")
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='multas', verbose_name="Equipo Sancionado")
    jugador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='multas', verbose_name="Jugador Sancionado")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto de Multa (C$)")
    motivo = models.CharField(max_length=20, choices=MOTIVOS, verbose_name="Motivo Sanción")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name="Estado de Pago")
    fecha_pago = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Pago de Multa")

    class Meta:
        verbose_name = "Multa por Tarjeta"
        verbose_name_plural = "Multas por Tarjetas"

    def __str__(self):
        return f"Multa {self.get_motivo_display()} - {self.jugador.username} ({self.get_estado_display()})"


class MovimientoCaja(models.Model):
    TIPOS = (
        ('ingreso', 'Ingreso (+)'),
        ('egreso', 'Egreso (-)'),
    )

    tipo = models.CharField(max_length=20, choices=TIPOS, verbose_name="Tipo de Movimiento")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto (C$)")
    concepto = models.CharField(max_length=255, verbose_name="Concepto/Descripción")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='movimientos_caja',
        verbose_name="Registrado Por"
    )

    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.concepto} ({self.monto} C$)"
