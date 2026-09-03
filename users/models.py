from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

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

    @property
    def ficha_jugador(self):
        return self.fichas_jugador.first()

    @property
    def ficha_dt(self):
        return self.fichas_dt.first()

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


class Organizacion(models.Model):
    ESTADOS = (
        ('activa', 'Activa'),
        ('suspendida', 'Suspendida'),
        ('inactiva', 'Inactiva'),
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    nombre = models.CharField(max_length=150, verbose_name="Nombre de Organización")
    nombre_comercial = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre Comercial")
    razon_social = models.CharField(max_length=150, blank=True, null=True, verbose_name="Razón Social")
    ruc = models.CharField(max_length=50, blank=True, null=True, verbose_name="RUC / NIT")
    logo = models.ImageField(upload_to='organizaciones/logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='organizaciones/favicons/', null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    sitio_web = models.URLField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    municipio = models.CharField(max_length=100, blank=True, null=True)
    pais = models.CharField(max_length=100, default="Nicaragua")
    moneda = models.CharField(max_length=10, default="NIO")
    zona_horaria = models.CharField(max_length=50, default="America/Managua")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_activacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"

    def __str__(self):
        return self.nombre


class UsuarioOrganizacion(models.Model):
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='organizaciones')
    organizacion = models.ForeignKey(Organizacion, on_delete=models.CASCADE, related_name='usuarios')
    rol = models.CharField(max_length=20, choices=CustomUser.ROLE_CHOICES, default='espectador')
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Usuario por Organización"
        verbose_name_plural = "Usuarios por Organización"
        unique_together = ('usuario', 'organizacion')

    def __str__(self):
        return f"{self.usuario.username} - {self.organizacion.nombre} ({self.get_rol_display()})"
