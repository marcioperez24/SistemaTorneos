from django.db import migrations

def populate_and_migrate_categories(apps, schema_editor):
    Categoria = apps.get_model('teams', 'Categoria')
    Equipo = apps.get_model('teams', 'Equipo')
    Torneo = apps.get_model('matches', 'Torneo')

    CATEGORIAS_DICT = {
        'senior': 'Senior / Libre',
        'master': 'Máster (Mayores de 40)',
        'supermaster': 'Supermáster (Mayores de 50)',
        'juvenil': 'Juvenil (Sub-18)',
        'u15': 'Sub-15 (U-15)',
        'u12': 'Sub-12 (U-12)',
        'femenino': 'Femenino Libre',
    }

    # Create Categories
    category_instances = {}
    for code, name in CATEGORIAS_DICT.items():
        cat, created = Categoria.objects.get_or_create(nombre=name)
        category_instances[code] = cat

    # Fallback default category for anything else or senior
    default_cat, created = Categoria.objects.get_or_create(nombre='Senior / Libre')

    # Update Equipos
    for equipo in Equipo.objects.all():
        old_cat = equipo.categoria
        equipo.categoria_fk = category_instances.get(old_cat, default_cat)
        equipo.save()

    # Update Torneos
    for torneo in Torneo.objects.all():
        old_cat = torneo.categoria
        torneo.categoria_fk = category_instances.get(old_cat, default_cat)
        torneo.save()

def rollback_categories(apps, schema_editor):
    Equipo = apps.get_model('teams', 'Equipo')
    Torneo = apps.get_model('matches', 'Torneo')

    # Revert FKs to CharFields (approximate mapping)
    for equipo in Equipo.objects.all():
        if equipo.categoria_fk:
            # Try to map back or default
            name = equipo.categoria_fk.nombre
            # Find key
            for code, n in {
                'senior': 'Senior / Libre',
                'master': 'Máster (Mayores de 40)',
                'supermaster': 'Supermáster (Mayores de 50)',
                'juvenil': 'Juvenil (Sub-18)',
                'u15': 'Sub-15 (U-15)',
                'u12': 'Sub-12 (U-12)',
                'femenino': 'Femenino Libre',
            }.items():
                if n == name:
                    equipo.categoria = code
                    break
            equipo.save()

    for torneo in Torneo.objects.all():
        if torneo.categoria_fk:
            name = torneo.categoria_fk.nombre
            for code, n in {
                'senior': 'Senior / Libre',
                'master': 'Máster (Mayores de 40)',
                'supermaster': 'Supermáster (Mayores de 50)',
                'juvenil': 'Juvenil (Sub-18)',
                'u15': 'Sub-15 (U-15)',
                'u12': 'Sub-12 (U-12)',
                'femenino': 'Femenino Libre',
            }.items():
                if n == name:
                    torneo.categoria = code
                    break
            torneo.save()

class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0014_categoria_alter_equipo_categoria_equipo_categoria_fk'),
        ('matches', '0010_torneo_categoria_fk_alter_torneo_categoria'),
    ]

    operations = [
        migrations.RunPython(populate_and_migrate_categories, rollback_categories),
    ]
