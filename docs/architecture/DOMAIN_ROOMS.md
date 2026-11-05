# Dominio: Habitaciones

## Elementos implementados

- Room: entidad del dominio.
- RoomNumber: Value Object para el número de habitación.
- Capacity: Value Object para la capacidad.
- Money: Value Object para importes en MXN.
- RoomStatus: estados de la habitación.

## Estados iniciales

- AVAILABLE: disponible.
- OCCUPIED: ocupada.
- OUT_OF_ORDER: fuera de servicio.

## Reglas implementadas

1. El número de habitación es obligatorio.
2. La capacidad debe ser mayor que cero.
3. El importe base no puede ser negativo.
4. El tipo de habitación es obligatorio.
5. Solo una habitación disponible puede ocuparse.
6. Solo una habitación ocupada puede liberarse.
7. Una habitación ocupada no puede marcarse fuera de servicio.

## Pendiente de validación

Estas reglas constituyen la primera implementación técnica.
Se contrastarán con el BRD, BPMN y ADRs de las unidades 2 y 3.