from django.db import migrations
from django.contrib.auth.hashers import make_password

def fix_marcio_superuser_profile(apps, schema_editor):
    CustomUser = apps.get_model('users', 'CustomUser')
    FichaJugador = apps.get_model('teams', 'FichaJugador')
    FichaDT = apps.get_model('teams', 'FichaDT')
    UsuarioOrganizacion = apps.get_model('users', 'UsuarioOrganizacion')

    # 1. Localizar al superusuario principal (marcio)
    marcio = CustomUser.objects.filter(username__iexact='marcio').first()
    if not marcio:
        marcio = CustomUser.objects.filter(is_superuser=True).order_by('id').first()

    if marcio:
        # Guardar nombres que se le habían asignado indebidamente (ej. JOSÉ TUAREZ)
        player_first_name = marcio.first_name if marcio.first_name and marcio.first_name.strip().upper() != 'MARCIO' else 'JOSÉ'
        player_last_name = marcio.last_name if marcio.last_name else 'TUAREZ'

        # 2. Desvincular cualquier FichaJugador asignada erróneamente a marcio
        fichas_j = list(FichaJugador.objects.filter(user=marcio))
        for fj in fichas_j:
            cedula = fj.nro_cedula or f"jug_{fj.id}"
            uname = f"jug_{cedula}"
            base_uname = uname
            c = 1
            while CustomUser.objects.filter(username=uname).exclude(id=marcio.id).exists():
                uname = f"{base_uname}_{c}"
                c += 1

            # Crear usuario exclusivo para el jugador deportista
            raw_pwd = cedula if str(cedula).isdigit() else "123456"
            player_user = CustomUser.objects.create(
                username=uname,
                password=make_password(raw_pwd),
                first_name=player_first_name,
                last_name=player_last_name,
                role='jugador',
                is_active=True,
                is_staff=False,
                is_superuser=False
            )

            fj.user = player_user
            fj.save()

            if fj.organizacion:
                UsuarioOrganizacion.objects.get_or_create(
                    usuario=player_user,
                    organizacion=fj.organizacion,
                    defaults={'rol': 'jugador', 'activo': True}
                )

        # 3. Desvincular cualquier FichaDT asignada erróneamente a marcio
        fichas_dt = list(FichaDT.objects.filter(user=marcio))
        for fdt in fichas_dt:
            cedula = fdt.nro_cedula or f"dt_{fdt.id}"
            uname = f"dt_{cedula}"
            base_uname = uname
            c = 1
            while CustomUser.objects.filter(username=uname).exclude(id=marcio.id).exists():
                uname = f"{base_uname}_{c}"
                c += 1

            raw_pwd = cedula if str(cedula).isdigit() else "123456"
            dt_user = CustomUser.objects.create(
                username=uname,
                password=make_password(raw_pwd),
                first_name=player_first_name,
                last_name=player_last_name,
                role='dt',
                is_active=True,
                is_staff=False,
                is_superuser=False
            )

            fdt.user = dt_user
            fdt.save()

            if fdt.organizacion:
                UsuarioOrganizacion.objects.get_or_create(
                    usuario=dt_user,
                    organizacion=fdt.organizacion,
                    defaults={'rol': 'dt', 'activo': True}
                )

        # 4. Restaurar el perfil limpio del superusuario MARCIO
        marcio.first_name = "MARCIO"
        marcio.last_name = ""
        marcio.role = "superadmin"
        marcio.is_superuser = True
        marcio.is_staff = True
        marcio.save()

        # Asegurar que en UsuarioOrganizacion tenga rol superadmin
        UsuarioOrganizacion.objects.filter(usuario=marcio).update(rol='superadmin')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_alter_customuser_role_alter_usuarioorganizacion_rol'),
        ('teams', '0019_alter_equipo_unique_together_equipo_categorias_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_marcio_superuser_profile, reverse_code=migrations.RunPython.noop),
    ]
