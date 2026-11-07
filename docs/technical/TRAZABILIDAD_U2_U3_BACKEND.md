# Hotel Costa Azul — Matriz de trazabilidad técnica U2/U3

**Base:** BRD_2, User_Stories2, Glosario, BPMN y ADR-001 a ADR-006 de Unidades 2 y 3. Los datos de tarifas del hotel y credenciales de proveedores NO se inventaron.

| US | Funcionalidad existente en esta entrega | Situación y alcance real |
|---|---|---|
| US-01 | `GET /api/v1/rooms/available` | Parcial: API sin interfaz gráfica; se busca por fechas, tipo y huéspedes. |
| US-02 | Disponibilidad PostgreSQL, filtro por reservas y bloqueos grupales | Parcial: consulta central; no integración OTA activa. |
| US-03 | `TariffCalculationService`, `staff/tariffs/configuration`, `staff/tariffs/quote` | Parcial: BAR alta/baja, viernes/sábado, canal/tipo; los multiplicadores los configura Gerencia. No se verifican contratos corporativos. |
| US-04 | `POST/GET/PATCH /reservations` | Implementada confirmación secuencial y bloqueo PostgreSQL por habitación; cotización aceptada tiene endpoint separado. |
| US-05 | `staff/reservations/{id}/cancel-policy` | Penalización 48 h calculada y persistida; cobro y reembolso externos PENDIENTES. |
| US-06 | `staff/reservations/{id}/no-show` | Transición después de 23:59 y cálculo con garantía; cargo a tarjeta externo PENDIENTE. |
| US-07 | `staff/reservations/{id}/check-in-documentation`, `check-in` | Registro cifrado, confirmación, ID vigente, habitación ocupada y folio transaccional. |
| US-08 | `guarantee` y registro de riesgo en documentación | Parcial: constancia y decisión de no habilitar folio sin garantía, no verificación de PSP. |
| US-09 | Early check-in si `AVAILABLE`, y `late-checkout-charge` | Parcial: política 14:00/18:00 y pago antes de salida, faltan salidas anticipadas/fechas extraordinarias. |
| US-10 | `staff/folios/{id}/charges`, `payments`, `folios/{id}` | Datos obligatorios de vale, estado de cuenta y pagos; firmas no verificadas criptográficamente. |
| US-11 | `staff/reservations/{id}/change-room` | Cambio de habitación transaccional y auditoría; la anterior queda sucia. |
| US-12 | `staff/reservations/{id}/extend` | Ampliación con disponibilidad y tarifa de noches adicionales; Gerencia autoriza para respetar RN-08. |
| US-13 | `staff/reservations/{id}/check-out` | Cierre de folio saldo cero, estado `CHECK_OUT` y habitación `DIRTY` en una transacción. **Hospedaje automático pendiente**. |
| US-14 | `staff/rooms/dirty` | Lista de pendientes por rol HOUSEKEEPING. |
| US-15 | `staff/rooms/{id}/clean`, `inspect` | Limpieza auditada, inspección opcional; `AVAILABLE` e `INSPECTED` aptas para reservar. |
| US-16 | `staff/reports/daily` | Llegadas, salidas, estatus actuales y **ocupación estimada**; no histórico operativo certificado. |
| US-17 | `staff/reports/weekly` | Pagos registrados y conteos; **ADR/RevPAR se devuelven nulos** para no confundir ingresos de habitación con pagos de folio. |
| US-18 | Roles JWT; configuración de tarifa solo Gerencia | Parcial: falta flujo general de descuentos y exenciones con autorización. |
| US-19 | Agregados Folio y validaciones | Pendiente ajuste en moneda USD con umbral 50 y conversión/autorización; no se finge MXN=USD. |
| US-20 | `staff/rooms/{id}/out-of-service` | Estado fuera de servicio, incidente y auditoría; excluido de disponibilidad. |
| US-21 | `staff/incidents/{id}/resolve`, `staff/rooms/{id}/restore` | Mantenimiento confirma resolución, Gerencia reactiva, requiere limpieza opcional. |
| US-22 | `staff/groups` y depósitos, grupos >=10 | Bloqueo, 30 %, confirmación manual, cancelación 7 días, liberación automática **en consulta** al vencer plazo; pago/contrato electrónico no verificados externamente. |
| US-23 | `staff/reservations/{id}/walk-plan`, `staff/walk-cases/{id}/confirm-partner` | Plan de walk + confirmación humana del hotel aliado; no reserva automática con hotel externo. |
| US-24 | Auditoría de limpieza | Pendiente métrica exacta: 45 minutos habitual, **tiempo para suites pendiente de validación en U2/U3**. |
| US-25 | Bloqueo transaccional y `availability_outbox` | Evita dos confirmaciones locales simultáneas; **publicación OTA/channel manager externa no implementada**. |
| US-26 | `staff/reservations/{id}/possible-duplicates` | Alerta por mismo `guest_id` y fechas; similitud de contacto y validación manual todavía pendiente. |

## ADR y patrones

- **ADR-001:** dominio con entidades, Value Objects y servicios de cálculo separados.
- **ADR-002:** agregados `Reservation` y `Folio`; habitación por ID; coordinaciones transaccionales.
- **ADR-003:** `TariffCalculationService` sin tarifas inventadas; registro de `walk` limitado a confirmación externa manual.
- **ADR-004:** repositorios y UoW de recepción/limpieza; operaciones transaccionales SQLAlchemy.
- **ADR-005:** Commands/Queries y DTO separados; consultas de disponibilidad, folios e informes.
- **ADR-006:** autorización en API y restricciones de dominio; ajustes USD >50 aún bloqueados por falta de tasa/regla de moneda.

## Pendientes que NO deben presentarse como terminados

- Integración bidireccional real con channel manager/OTA (credenciales, API y contratos externos).
- Pasarela de pagos para cargos reales, captura de garantía, devoluciones y conciliación.
- Facturación fiscal con el proveedor y requisitos tributarios vigentes del hotel.
- Tarifa corporativa validada por contratos firmados y renovación de acuerdos.
- Automatización completa de cargos de hospedaje, salidas anticipadas y permisos de exención.
- Cálculo real de ADR/RevPAR y métricas históricas con ingresos nocturnos registrados.
- Gestión formal de usuarios de huéspedes y prevención de duplicados por contacto semejante.
- Operación 24/7 en producción (monitoreo, backups, SLA, DR, HTTPS, límites de tráfico, pruebas de carga/concurrencia PostgreSQL).
- Auditoría de lectura de datos personales, retención/borrado autorizado, firma electrónica verificable.

**No hay un porcentaje general de completitud del PIA validado.** Las pruebas evalúan lo implementado, no demuestran cobertura de todas las historias de usuario.
