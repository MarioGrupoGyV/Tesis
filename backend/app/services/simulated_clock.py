"""Evaluación retrospectiva: `as_of` en el pasado simula el instante de la evaluación.

predicted_at/opened_at siguen siendo el instante real; as_of_at/detected_at guardan el simulado. En una corrida normal el
`as_of` del cliente solo difiere del reloj en segundos y no se guarda (la base lo iguala al instante real).
"""
from datetime import UTC, datetime, timedelta

TOLERANCE = timedelta(minutes=5)
LABEL = 'simulación retrospectiva'


def simulated_instant(as_of):
    """as_of_at a guardar: solo si el as_of es claramente pasado; si no, None (= instante real)."""
    return as_of if as_of is not None and as_of < datetime.now(UTC) - TOLERANCE else None


def is_retrospective(simulated_at, real_at):
    return simulated_at is not None and real_at is not None and real_at - simulated_at > TOLERANCE
