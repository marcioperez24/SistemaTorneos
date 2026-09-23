# Plan de Reversión y Restauralización (Rollback) - SistemaTorneos

## 1. Criterios para Iniciar una Reversión
Se debe iniciar el procedimiento de reversión si tras un despliegue se presenta alguna de las siguientes situaciones:
- El endpoint `/health/` responde con un error HTTP 500 o no responde.
- La aplicación lanza errores de base de datos no recuperables tras aplicar una migración.
- Falla el arranque del servicio Gunicorn (`systorneos`).
- Se identifica una regresión crítica que afecte a torneos en curso o aislamiento multi-tenant.

---

## 2. Procedimiento Paso a Paso de Reversión

### Paso 1: Activar Modo Mantenimiento en Nginx (Opcional)
```bash
sudo touch /home/marcio/apps/SistemaTorneos/maintenance.enable
sudo systemctl reload nginx
```

### Paso 2: Volver al Commit Anterior Estable
```bash
cd /home/marcio/apps/SistemaTorneos
# Obtener el hash del commit previo
git log -n 5 --oneline
# Regresar al commit previo deseado (ejemplo: 3c69344)
git checkout <COMMIT_HASH_ANTERIOR>
```

### Paso 3: Revertir Migración de Base de Datos (Si Aplica)
Si la migración introducida es reversible y destructiva:
```bash
source .venv/bin/activate
# Revertir a la migración estable previa (ejemplo: matches 0020)
python manage.py migrate matches 0020
```
*Nota: Si se realizó un respaldo con mysqldump antes del despliegue, restaurar el dump MySQL si es necesario.*

### Paso 4: Restaurar Base de Datos desde Respaldo SQL (Si Fuere Necesario)
```bash
mysql -u sistematorneos_usr -p sistematorneos_prod < /home/marcio/backups/sistematorneos_pre_deploy.sql
```

### Paso 5: Reiniciar Servicios y Verificar Health Check
```bash
python manage.py collectstatic --noinput
sudo systemctl restart systorneos
sudo systemctl reload nginx

# Verificar que el sistema esté operativo
curl -f http://127.0.0.1:8000/health/
```

### Paso 6: Desactivar Modo Mantenimiento
```bash
sudo rm -f /home/marcio/apps/SistemaTorneos/maintenance.enable
sudo systemctl reload nginx
```
