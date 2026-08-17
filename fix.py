import codecs
f='teams/templates/teams/base.html'
text=codecs.open(f, 'r', 'utf-8', errors='ignore').read()
text=text.replace("Vocala", "Vocalía").replace("VocalÃ­a", "Vocalía")
text=text.replace("Administracin", "Administración").replace("AdministraciÃ³n", "Administración")
text=text.replace("Secretara", "Secretaría").replace("SecretarÃ­a", "Secretaría")
text=text.replace("Validacin", "Validación").replace("ValidaciÃ³n", "Validación")
text=text.replace("rbitros", "Árbitros").replace("Ã rbitros", "Árbitros")
text=text.replace("Tesorera", "Tesorería").replace("TesorerÃ­a", "Tesorería")
text=text.replace("Sesin", "Sesión").replace("SesiÃ³n", "Sesión")
text=text.replace("Diseado", "Diseñado").replace("DiseÃ±ado", "Diseñado")
codecs.open(f, 'w', 'utf-8').write(text)
