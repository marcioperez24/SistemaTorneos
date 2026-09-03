from django.utils.deprecation import MiddlewareMixin
from users.models import Organizacion, UsuarioOrganizacion

class OrganizacionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.organizacion = None
        
        if request.user.is_authenticated:
            # Check if there is an organization in the session
            org_id = request.session.get('current_organizacion_id')
            
            if org_id:
                try:
                    request.organizacion = Organizacion.objects.get(id=org_id)
                except Organizacion.DoesNotExist:
                    pass
            
            # If still None, get the first one the user belongs to
            if not request.organizacion:
                usuario_org = UsuarioOrganizacion.objects.filter(usuario=request.user, activo=True).first()
                if usuario_org:
                    request.organizacion = usuario_org.organizacion
                    request.session['current_organizacion_id'] = request.organizacion.id
