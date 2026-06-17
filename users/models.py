from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin / Organizador'),
        ('dirigente', 'Dirigente / Representante'),
        ('jugador', 'Jugador'),
        ('dt', 'Director Técnico / Staff'),
        ('arbitro', 'Árbitro'),
        ('espectador', 'Espectador'),
        ('tesoreria', 'Tesorería'),
        ('comision', 'Comisión Técnica'),
        ('vocal', 'Vocal de Campo'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='espectador')
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = 'superadmin'
        super().save(*args, **kwargs)

    def has_module_access(self, module_name):
        if self.is_superuser or self.role == 'superadmin':
            return True
        try:
            perm = RolePermission.objects.get(role=self.role, module=module_name)
            return perm.allowed
        except RolePermission.DoesNotExist:
            # Fallback to hardcoded defaults
            defaults = {
                'partidos': ['superadmin', 'comision', 'vocal'],
                'equipos': ['dirigente'],
                'vocalia': ['vocal'],
                'secretaria': ['comision'],
                'tesoreria': ['tesorero', 'tesoreria'],
            }
            return self.role in defaults.get(module_name, [])

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class RolePermission(models.Model):
    role = models.CharField(max_length=20)
    module = models.CharField(max_length=50)
    allowed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('role', 'module')

    def __str__(self):
        return f"{self.role} - {self.module}: {self.allowed}"
