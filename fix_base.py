import os

BASE_HTML_PATH = r'C:\Users\Marcio-adm\Documents\sistema_torneos\teams\templates\teams\base.html'

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

content = read_file(BASE_HTML_PATH)

# Replace the body tag and everything inside it to implement sidebar layout
import re

new_body = """<body>

    <!-- Loading Overlay -->
    <div id="global-loader">
        <div class="loader-content">
            <div class="loader-spinner"></div>
            <img src="{% static 'teams/images/logo.png' %}" alt="Logo" class="loader-logo">
        </div>
    </div>

    <!-- App Layout -->
    <div class="app-layout">
        
        <!-- Sidebar -->
        {% if not hide_navbar %}
        <aside class="sidebar">
            <div class="sidebar-header">
                <a class="sidebar-brand d-flex align-items-center" href="{% url 'club_portal' %}">
                    <img src="{% static 'teams/images/logo.png' %}" alt="Logo">
                    <span class="ms-2">Fútbol Pro</span>
                </a>
            </div>
            
            <div class="sidebar-menu">
                <ul class="nav flex-column">
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'partidos_lista' %}">
                            <i class="fa-solid fa-calendar-days text-warning"></i> Partidos y Resultados
                        </a>
                    </li>
                    
                    {% if user.is_authenticated %}
                        {% if user_perms.equipos %}
                            <li class="nav-item">
                                <a class="nav-link" href="{% url 'club_portal' %}">
                                    <i class="fa-solid fa-shield-halved text-info"></i> Portal del Club
                                </a>
                            </li>
                        {% endif %}
                        
                        {% if user_perms.vocalia %}
                            <li class="nav-item">
                                <a class="nav-link" href="{% url 'vocalia_dashboard' %}">
                                    <i class="fa-solid fa-clipboard-list text-warning"></i> Vocalía de Campo
                                </a>
                            </li>
                        {% endif %}
                        
                        {% if user_perms.secretaria or user_perms.tesoreria %}
                            <li class="nav-title mt-3 mb-1 px-3 text-muted" style="font-size: 0.75rem; font-weight: 700; letter-spacing: 1px;">ADMINISTRACIÓN</li>
                            
                            {% if user_perms.secretaria %}
                                <li class="nav-item">
                                    <a class="nav-link" href="{% url 'secretaria_dashboard' %}">
                                        <i class="fa-solid fa-user-check text-primary"></i> Secretaría
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" href="{% url 'gestion_arbitros' %}">
                                        <i class="fa-solid fa-bullhorn text-primary"></i> Árbitros
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" href="{% url 'gestion_vocales' %}">
                                        <i class="fa-solid fa-clipboard-list text-primary"></i> Vocales
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" href="{% url 'gestion_torneos' %}">
                                        <i class="fa-solid fa-trophy text-primary"></i> Torneos/Ligas
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" href="{% url 'lista_categorias' %}">
                                        <i class="fa-solid fa-tags text-primary"></i> Categorías
                                    </a>
                                </li>
                            {% endif %}
                            
                            {% if user_perms.tesoreria %}
                                <li class="nav-item">
                                    <a class="nav-link" href="{% url 'resumen_financiero' %}">
                                        <i class="fa-solid fa-file-invoice-dollar text-success"></i> Tesorería
                                    </a>
                                </li>
                            {% endif %}
                        {% endif %}
                        
                        {% if user.role == 'superadmin' %}
                            <li class="nav-title mt-3 mb-1 px-3 text-muted" style="font-size: 0.75rem; font-weight: 700; letter-spacing: 1px;">SISTEMA</li>
                            <li class="nav-item">
                                <a class="nav-link" href="{% url 'torre_control' %}">
                                    <i class="fa-solid fa-building text-danger"></i> Torre de Control
                                </a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="{% url 'gestion_usuarios' %}">
                                    <i class="fa-solid fa-users-gear text-danger"></i> Usuarios
                                </a>
                            </li>
                        {% endif %}
                    {% endif %}
                </ul>
            </div>
            
            <div class="sidebar-footer mt-auto p-3">
                {% if user.is_authenticated %}
                    <div class="d-flex align-items-center">
                        <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 40px; height: 40px; font-size: 1.2rem;">
                            {{ user.username|make_list|first|upper }}
                        </div>
                        <div class="ms-3 overflow-hidden">
                            <h6 class="mb-0 text-truncate text-white" style="font-size: 0.85rem;">{{ user.get_full_name|default:user.username }}</h6>
                            <small class="text-muted text-truncate d-block" style="font-size: 0.7rem;">{{ user.get_role_display }}</small>
                        </div>
                        <a href="{% url 'logout' %}" class="ms-auto text-danger" title="Cerrar Sesión">
                            <i class="fa-solid fa-sign-out-alt"></i>
                        </a>
                    </div>
                {% else %}
                    <a href="{% url 'login' %}" class="btn btn-custom-primary w-100">Iniciar Sesión</a>
                {% endif %}
            </div>
        </aside>
        {% endif %}
        
        <!-- Main Wrapper -->
        <div class="main-wrapper">
            
            <!-- Topbar (Compact) -->
            <header class="topbar d-flex align-items-center px-4">
                <div class="me-auto">
                    <!-- Hamburger (mobile) -->
                    <button class="btn btn-link text-dark d-lg-none" id="sidebarToggle">
                        <i class="fa-solid fa-bars fs-4"></i>
                    </button>
                    <!-- Orgnization context if any -->
                    {% if request.organizacion %}
                    <span class="badge bg-primary fs-6"><i class="fa-solid fa-building me-2"></i>{{ request.organizacion.nombre }}</span>
                    {% endif %}
                </div>
                
                <div class="ms-auto d-flex align-items-center">
                    {% if request.session.current_organizacion_id and user.role == 'superadmin' %}
                        <a href="{% url 'torre_control' %}" class="btn btn-sm btn-outline-danger me-3">
                            <i class="fa-solid fa-times me-1"></i> Salir de Organización
                        </a>
                    {% endif %}
                </div>
            </header>

            <!-- Main Content -->
            <main class="content p-4">
                {% if messages %}
                    <div class="container-fluid mb-3">
                        {% for message in messages %}
                            <div class="alert alert-{{ message.tags }} alert-dismissible fade show shadow-sm" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    </div>
                {% endif %}

                {% block content %}{% endblock %}
            </main>

            <!-- Footer -->
            <footer class="footer text-center p-3 mt-auto">
                <p class="mb-0 text-muted" style="font-size: 0.85rem;">&copy; 2026 Fútbol Pro SaaS. Diseño Premium.</p>
            </footer>

        </div> <!-- /.main-wrapper -->
    </div> <!-- /.app-layout -->
"""

# Now we need to update CSS to support app-layout, sidebar, main-wrapper, topbar.
css_additions = """
        /* SaaS Layout Variables */
        :root {
            --sidebar-width: 260px;
            --sidebar-bg: #0f172a;
            --topbar-height: 60px;
            --primary-gradient: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
            --accent-color: #f59e0b;
            --bg-color: #f8fafc;
            --card-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.04), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            --border-radius: 16px;
        }

        body {
            font-family: 'Roboto', sans-serif;
            background-color: var(--bg-color);
            color: #1e293b;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        .app-layout {
            display: flex;
            min-height: 100vh;
        }

        /* Sidebar Styling */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--sidebar-bg);
            color: white;
            display: flex;
            flex-direction: column;
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 1000;
            transition: var(--transition);
            box-shadow: 4px 0 24px rgba(0,0,0,0.1);
        }

        .sidebar-header {
            height: var(--topbar-height);
            display: flex;
            align-items: center;
            padding: 0 1.5rem;
            background: rgba(0,0,0,0.15);
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .sidebar-brand {
            color: white;
            text-decoration: none;
            font-weight: 900;
            font-size: 1.2rem;
            letter-spacing: 0.5px;
        }

        .sidebar-brand img {
            height: 32px;
        }
        
        .sidebar-brand:hover {
            color: white;
        }

        .sidebar-menu {
            flex: 1;
            overflow-y: auto;
            padding: 1rem 0;
        }

        .sidebar-menu .nav-link {
            color: #94a3b8;
            padding: 0.75rem 1.5rem;
            font-weight: 500;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            transition: var(--transition);
        }

        .sidebar-menu .nav-link i {
            width: 24px;
            text-align: center;
            margin-right: 12px;
            font-size: 1.1rem;
        }

        .sidebar-menu .nav-link:hover, .sidebar-menu .nav-link.active {
            color: white;
            background: rgba(255,255,255,0.05);
            border-left: 4px solid var(--accent-color);
        }

        /* Main Wrapper */
        .main-wrapper {
            flex: 1;
            margin-left: var(--sidebar-width);
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            transition: var(--transition);
        }

        /* Topbar */
        .topbar {
            height: var(--topbar-height);
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            z-index: 900;
            position: sticky;
            top: 0;
        }

        .content {
            flex: 1;
        }

        /* Mobile Adjustments */
        @media (max-width: 991.98px) {
            .sidebar {
                transform: translateX(-100%);
            }
            .sidebar.show {
                transform: translateX(0);
            }
            .main-wrapper {
                margin-left: 0;
            }
        }
"""

# Use regex to replace the old css vars and body
content = re.sub(r':root\s*\{.*?\}(?=\s*body)', css_additions, content, flags=re.DOTALL)
content = re.sub(r'<body>.*</body>', new_body + '\n' + re.search(r'(<script>.*?</script>.*?)</body>', content, flags=re.DOTALL).group(1) + '</body>', content, flags=re.DOTALL)

# Delete old navbar and footer from content (already handled by the regex replacement above since we replace the entire body)
write_file(BASE_HTML_PATH, content)
