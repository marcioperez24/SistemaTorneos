# Manual Técnico y Funcional: Torneo Personalizado por Grupos

## 1. Visión General
El módulo de **Torneo Personalizado por Grupos** de `SistemaTorneos` permite organizar campeonatos con estructuras de grupos flexibles (asimétricos o simétricos), generar fixtures de ida o ida/vuelta, resolver empates mediante criterios administrativos, clasificar equipos con formato Champions o manual, ejecutar un cuadro eliminatorio directo hasta la final y consagrar al campeón.

---

## 2. Flujo Deportivo por Fases

```
[Fase 1: Configuración] ➔ [Fase 2: Grupos] ➔ [Fase 3: Fixture] ➔ [Fase 4: Fase de Grupos]
                                                                        │
[Fase 7: Centro Control] ◄─ [Fase 6: Campeón] ◄─ [Fase 5: Eliminatorias] ┘
```

1. **Fase 1 (Creación de Torneo)**: Definición del torneo con `tipo='personalizado'`, categoría, temporada y costos de amonestaciones.
2. **Fase 2 (Gestión de Grupos)**: Creación de grupos (`GrupoTorneo`) con cupos de clasificación e inserción/movimiento de equipos (`EquipoGrupoTorneo`).
3. **Fase 3 (Generación de Fixture)**: Algoritmo de Round-Robin adaptado para grupos pares e impares, con opción de una vuelta o ida y vuelta.
4. **Fase 4 (Fase de Grupos y Estadísticas)**: Registro de resultados de partidos, actualización de tablas de posiciones (`PJ`, `PG`, `PE`, `PP`, `GF`, `GC`, `DG`, `PTS`) y resolución de empates.
5. **Fase 5 (Sorteo y Cuadro Eliminatorio)**: Confirmación de clasificados definitivos (`ClasificadoTorneo`), creación de bombos, sorteo automático o armado manual de llaves eliminatorias (`LlaveEliminatoria`).
6. **Fase 6 (Desarrollo Eliminatorio y Campeón)**: Registro de marcadores en llaves (partido único o ida y vuelta), prórroga, penales, avance automático de ganadores y coronación de campeón (`ResultadoFinalTorneo`).
7. **Fase 7 (Centro de Control Operativo y Vista Pública)**: Panel unificado con barra de 7 pasos, alertas administrativas, exportación Excel multi-hoja, vista de impresión y portal público seguro vía UUID.

---

## 3. Seguridad Multi-Tenant y Permisos
- Todas las consultas administrativas filtran estrictamente por `organizacion=request.organizacion`.
- El middleware `OrganizacionMiddleware` inyecta `request.organizacion`, `request.usuario_organizacion` y `request.rol_organizacion` validando que la relación del usuario con la organización esté activa (`activo=True`).
- El portal público accesible en `/publico/torneo/<uuid:public_uuid>/` es anónimo y no expone números telefónicos, cédulas, datos médicos ni información financiera.

---

## 4. Comandos de Administración
- **Auditoría de Datos**:
  ```bash
  python manage.py auditar_torneo_personalizado --torneo <ID>
  ```
  Comprueba de forma segura (solo lectura) que no existan equipos duplicados en grupos, partidos huérfanos, llaves inconsistentes ni eventos financieros duplicados.
