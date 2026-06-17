from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import models

@receiver(pre_save)
def auto_uppercase_fields(sender, instance, **kwargs):
    # Solo aplicar a los modelos de nuestras aplicaciones para evitar corromper datos internos de Django (como sesiones o permisos)
    mis_apps = ['users', 'teams', 'matches', 'finances']
    if instance._meta.app_label not in mis_apps:
        return

    for field in instance._meta.fields:
        if isinstance(field, (models.CharField, models.TextField)):
            # Skip fields with predefined choices to avoid breaking form validation/display
            if field.choices:
                continue
                
            val = getattr(instance, field.name)
            if val and isinstance(val, str):
                # Exclude sensitive system fields, emails, passwords, and Base64 media data
                exclude_fields = [
                    'password', 'email', 'token', 'username',
                    'firma_vocal_img', 'firma_arbitro_img', 
                    'firma_entrenador_local_img', 'firma_entrenador_visitante_img',
                    'firma_imagen'
                ]
                if field.name not in exclude_fields and not field.name.endswith('_hash'):
                    setattr(instance, field.name, val.upper())
