import os

filepath = 'finances/models.py'
with open(filepath, 'rb') as f:
    text = f.read().decode('utf-8', 'ignore')

idx = text.find('class CobroEquipo')
if idx != -1:
    text = text[:idx]

text += '''
class CobroEquipo(models.Model):
    CONCEPTO_CHOICES = (
        ('arbitraje', 'Cuota de Arbitraje'),
        ('inscripcion', 'Cuota de Inscripción'),
        ('multa', 'Multa / Sanción Disciplinaria'),
        ('otro', 'Otro Cobro'),
    )
    ESTADOS = (
        ('pendiente', 'Pendiente de Pago'),
        ('pagado', 'Pagado'),
    )

    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='cobros_adicionales', verbose_name="Equipo")
    concepto = models.CharField(max_length=50, choices=CONCEPTO_CHOICES, verbose_name="Concepto")
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción Detallada")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto ($)")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name="Estado")
    fecha_emision = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Emisión")
    fecha_pago = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Pago")

    class Meta:
        verbose_name = "Cobro a Equipo"
        verbose_name_plural = "Cobros a Equipos"
        ordering = ['-fecha_emision']

    def __str__(self):
        return f"{self.get_concepto_display()} - {self.equipo.nombre} ({self.monto} $)"
'''

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)
