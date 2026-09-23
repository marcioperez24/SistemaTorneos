# Lista de Comprobación de Pruebas de Aceptación (Fase 8)

## 1. Verificación Operativa por Organización

### 🏢 Organización A (Ej: "Liga Central")
- [ ] **Crear Torneo Personalizado**: Creación del torneo con categoría "Máster" y costos de tarjetas ($50/$150).
- [ ] **Configurar 4 Grupos**: Grupos A, B, C, D con cupos de clasificación = 4.
- [ ] **Asignar Equipos Asimétricos**: 7, 6, 5 y 8 equipos asignados respectivamente.
- [ ] **Mover Equipos**: Mover equipo de Grupo A a Grupo B manteniendo integridad de asignaciones.
- [ ] **Generar Fixture**: Calendario generado correctamente (ida y vuelta).
- [ ] **Registrar Resultados**: Ingresar marcadores de partidos de grupo y verificar actualización instantánea de la tabla de posiciones.
- [ ] **Resolver Empates Pendientes**: Crear resolución administrativa de empates sin duplicados.
- [ ] **Confirmar Clasificados Definitivos**: Generar 16 clasificados con sus respectivos bombos de sorteo.
- [ ] **Ejecutar Sorteo de Eliminatorias**: Asignación automática estilo Champions a llaves de Octavos de Final.
- [ ] **Registrar Llaves Eliminatorias**: Definición por penales o prórroga en empates globales.
- [ ] **Avance a Semifinales y Final**: Confirmación de ganadores y generación de la siguiente ronda.
- [ ] **Coronación de Campeón**: Registro del resultado final, campeón y subcampeón.
- [ ] **Reportes y Vista Pública**: Exportar Excel consolidado, imprimir cuadro y compartir vista pública por WhatsApp.

---

### 🏢 Organización B (Ej: "Liga Norte")
- [ ] **Aislamiento Multi-Tenant**: Intentar acceder mediante modificación de URL/ID a objetos de Organización A. Debe responder HTTP 404 o 403.
- [ ] **Crear Categorías y Equipos Homónimos**: Crear categoría "Máster" y equipos con nombres idénticos sin colisión de nombres entre organizaciones.
- [ ] **Verificar Roles Independientes**: Mismo usuario registrado como `admin` en Org A y `espectador` en Org B. Debe denegar acciones administrativas en Org B.

---

## 2. Verificación Móvil y Responsive
- [ ] **Login y Dashboard**: Navegación fluida y menú lateral (drawer) funcional en pantalla táctil (< 576px).
- [ ] **Centro de Control**: Pasos de progreso y recomendaciones legibles sin desbordamiento horizontal.
- [ ] **Partidos y Cuadro Eliminatorio**: Visualización de llaves en scroll horizontal limpio o acordeones colapsables.
- [ ] **Vista Pública Anónima**: Visualización pública en smartphone sin exponer datos privados de dirigentes o jugadores.
