"""Bloque 3B-3 (A): PDER y CRA se deciden con la predicción de cada corte, no con la alerta única de la matrícula.

Filas ficticias (solo códigos), sin base de datos: ejercitan las reglas de `detection_before_close` y `summarize`.
"""
from datetime import UTC, datetime, timedelta

from app.services.indicators import detection_before_close, summarize

CLOSE = datetime(2026, 5, 9, 5, 0, tzinfo=UTC)          # inicio del día siguiente al cierre (Lima)
LEAD = 3


def row(code, predicted, reference, instant, decision=None, alert=True):
    base = dict(anon_code=code, eligible=True, snapshot_id=code, predicted_risk=predicted, reference=reference, nia=0,
                alert_id='A-' + code if alert else None, opportune=None, days=None, average_grade=10, attendance_pct=80,
                prediction_instant=instant, followup_decision=decision)
    base['before_close'] = detection_before_close(base, CLOSE, LEAD)
    base['covered'] = predicted == 'LOW' or decision in ('CREATED', 'UPDATED')
    return base


def pder(rows):
    return summarize(rows).pder


def test_alert_in_b1_does_not_count_for_b2_when_b2_prediction_is_low():
    early = CLOSE - timedelta(days=30)
    b1 = row('E001', 'MEDIUM', 'MEDIUM', early, 'CREATED')
    b2 = row('E001', 'LOW', 'MEDIUM', early, 'RETAINED_LOW')          # la alerta de B1 sigue abierta (alert_id), pero B2 no detectó
    assert pder([b1]).numerator == 1 and pder([b1]).denominator == 1
    assert pder([b2]).numerator == 0 and pder([b2]).denominator == 1


def test_medium_then_high_with_single_updated_alert_counts_once_per_bimester_with_its_own_prediction():
    b1 = row('E002', 'MEDIUM', 'MEDIUM', CLOSE - timedelta(days=30), 'CREATED')
    b2 = row('E002', 'HIGH', 'HIGH', CLOSE - timedelta(days=20), 'UPDATED')
    assert (pder([b1]).numerator, pder([b1]).denominator) == (1, 1)
    assert (pder([b2]).numerator, pder([b2]).denominator) == (1, 1)


def test_low_in_b1_then_high_in_b2_is_not_detected_in_b1():
    b1 = row('E003', 'LOW', 'MEDIUM', CLOSE - timedelta(days=30), 'NO_ALERT', alert=False)
    b2 = row('E003', 'HIGH', 'HIGH', CLOSE - timedelta(days=20), 'CREATED')
    assert (pder([b1]).numerator, pder([b1]).denominator) == (0, 1)
    assert (pder([b2]).numerator, pder([b2]).denominator) == (1, 1)


def test_prediction_after_close_or_inside_the_lead_margin_is_not_timely():
    assert row('E004', 'HIGH', 'HIGH', CLOSE + timedelta(hours=1), 'CREATED')['before_close'] is False
    assert row('E005', 'HIGH', 'HIGH', CLOSE - timedelta(days=2), 'CREATED')['before_close'] is False     # dentro del margen de 3 días
    assert row('E006', 'HIGH', 'HIGH', CLOSE - timedelta(days=4), 'CREATED')['before_close'] is True
    assert pder([row('E004', 'HIGH', 'HIGH', CLOSE + timedelta(hours=1), 'CREATED')]).numerator == 0


def test_each_student_counts_once_inside_a_bimester_and_without_prediction_is_not_detected():
    rows = [row('E007', 'HIGH', 'HIGH', CLOSE - timedelta(days=10), 'CREATED'),
            row('E008', 'MEDIUM', 'MEDIUM', CLOSE - timedelta(days=10), 'CREATED'),
            row('E009', None, 'HIGH', None, None, alert=False)]
    result = pder(rows)
    assert (result.numerator, result.denominator) == (2, 3)
    assert row('E009', None, 'HIGH', None, None, alert=False)['before_close'] is False


def test_cra_counts_low_or_medium_high_reflected_in_an_alert_not_an_inherited_one():
    early = CLOSE - timedelta(days=30)
    rows = [row('E010', 'LOW', 'LOW', early, 'RETAINED_LOW'),
            row('E011', 'HIGH', 'HIGH', early, 'CREATED'),
            row('E012', 'MEDIUM', 'MEDIUM', early, None)]            # alerta heredada (alert_id) sin decisión propia: no cubre
    cra = summarize(rows).cra
    assert (cra.numerator, cra.denominator) == (2, 3)
