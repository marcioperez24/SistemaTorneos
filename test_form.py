import os
import sys
import django

# Add workspace to path
sys.path.append(r'c:\Users\Marcio-adm\Documents\sistema_torneos')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'torneos_project.settings')
django.setup()

from matches.forms import TorneoForm
from teams.models import Equipo
from matches.models import Torneo

# Get some teams
teams = list(Equipo.objects.all()[:2])
team_ids = [t.id for t in teams]
print("Found teams:", teams)
print("Team IDs:", team_ids)

# Test POST data simulation
post_data = {
    'nombre': 'TORNEO DE PRUEBA MAYUSCULAS',
    'tipo': 'liga',
    'temporada': 'TEMPORADA 2026',
    'equipos': team_ids
}

form = TorneoForm(data=post_data)
if form.is_valid():
    print("Form is valid! Saving...")
    torneo = form.save()
    print("Saved tournament:", torneo)
    print("Tournament teams count:", torneo.equipos.count())
    # Delete it so we don't mess up database
    torneo.delete()
else:
    print("Form is invalid!")
    print("Errors:", form.errors)
