from django.utils.deprecation import MiddlewareMixin
from users.models import Organizacion, UsuarioOrganizacion

class OrganizacionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.organizacion = None
        request.usuario_organizacion = None
        request.rol_organizacion = None

        if request.user.is_authenticated:
            org_id = request.session.get('current_organizacion_id')

            if org_id:
                try:
                    org = Organizacion.objects.get(id=org_id)
                    if request.user.is_superuser:
                        request.organizacion = org
                        request.usuario_organizacion = UsuarioOrganizacion.objects.filter(usuario=request.user, organizacion=org).first()
                        request.rol_organizacion = request.usuario_organizacion.rol if request.usuario_organizacion else 'superadmin'
                    else:
                        usuario_org = UsuarioOrganizacion.objects.filter(
                            usuario=request.user, organizacion=org, activo=True
                        ).first()
                        if usuario_org:
                            request.organizacion = org
                            request.usuario_organizacion = usuario_org
                            request.rol_organizacion = usuario_org.rol
                        else:
                            request.session.pop('current_organizacion_id', None)
                except Organizacion.DoesNotExist:
                    request.session.pop('current_organizacion_id', None)

            if not request.organizacion:
                if request.user.is_superuser:
                    first_org = Organizacion.objects.first()
                    if first_org:
                        request.organizacion = first_org
                        request.session['current_organizacion_id'] = first_org.id
                        request.rol_organizacion = 'superadmin'
                else:
                    usuario_org = UsuarioOrganizacion.objects.filter(
                        usuario=request.user, activo=True
                    ).select_related('organizacion').first()
                    if usuario_org:
                        request.organizacion = usuario_org.organizacion
                        request.usuario_organizacion = usuario_org
                        request.rol_organizacion = usuario_org.rol
                        request.session['current_organizacion_id'] = request.organizacion.id
                    else:
                        request.rol_organizacion = request.user.role
