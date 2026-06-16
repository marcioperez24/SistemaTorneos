def permissions_context(request):
    if not request.user.is_authenticated:
        return {'user_perms': {}}

    # If superuser or superadmin, they get access to all modules automatically
    is_admin = request.user.is_superuser or request.user.role == 'superadmin'

    modules = ['partidos', 'equipos', 'vocalia', 'secretaria', 'tesoreria']

    if is_admin:
        user_perms = {m: True for m in modules}
    else:
        user_perms = {}
        for m in modules:
            user_perms[m] = request.user.has_module_access(m)

    return {'user_perms': user_perms}
