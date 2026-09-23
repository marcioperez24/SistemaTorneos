# Guía de Despliegue en Producción - SistemaTorneos

## 1. Requisitos Previos del Servidor VPS
- Sistema Operativo: Ubuntu 22.04 LTS / 24.04 LTS.
- Python 3.12+ con entorno virtual (`.venv`).
- Base de datos MySQL 8.0+ / MariaDB 10.6+.
- Servidor Web Nginx + Gunicorn.
- Certificado SSL habilitado (Let's Encrypt / Certbot).

---

## 2. Variables de Entorno (`.env`)
Crear o verificar el archivo `/home/marcio/apps/SistemaTorneos/.env` con los secretos reales del servidor:

```ini
DJANGO_SECRET_KEY=clave_secreta_generada_aleatoria_y_larga
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=torneos.sysacadep.win,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://torneos.sysacadep.win

DB_NAME=sistematorneos_prod
DB_USER=sistematorneos_usr
DB_PASSWORD=contrasena_db_produccion
DB_HOST=127.0.0.1
DB_PORT=3306

SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

---

## 3. Procedimiento de Migración y Despliegue Manual

```bash
# 1. Acceder al directorio de la aplicación
cd /home/marcio/apps/SistemaTorneos

# 2. Obtener los últimos cambios probados
git fetch origin main
git pull --ff-only origin main

# 3. Activar el entorno virtual
source .venv/bin/activate

# 4. Instalar dependencias exactas
pip install -r requirements.txt

# 5. Aplicar migraciones pendientes
python manage.py migrate --noinput

# 6. Recopilar archivos estáticos
python manage.py collectstatic --noinput

# 7. Ejecutar comando de auditoría de seguridad
python manage.py auditar_torneo_personalizado --torneo 1

# 8. Reiniciar los servicios de producción
sudo systemctl restart systorneos
sudo systemctl reload nginx

# 9. Verificar estado de salud (Health Check)
curl -f http://127.0.0.1:8000/health/
```

---

## 4. Despliegue Automatizado con GitHub Actions
El archivo `.github/workflows/deploy.yml` ejecuta automáticamente las siguientes fases en cada `push` a `main`:
1. **Job `test`**: Ejecuta `python manage.py check` y `python manage.py test` en Ubuntu.
2. **Job `deploy`**: Se ejecuta únicamente si las pruebas tuvieron éxito. Realiza el `pull --ff-only`, migraciones, `collectstatic`, reinicio de `systorneos` / `nginx` y prueba de salud vía `/health/`.
