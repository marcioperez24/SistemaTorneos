from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin / Organizador'),
        ('dirigente', 'Dirigente / Representante'),
        ('jugador', 'Jugador'),
        ('arbitro', 'Árbitro'),
        ('espectador', 'Espectador'),
        ('tesoreria', 'Tesorería'),
        ('comision', 'Comisión Técnica'),
        ('vocal', 'Vocal de Campo'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='espectador')
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
