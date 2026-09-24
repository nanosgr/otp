from datetime import date
from decimal import Decimal

from app.services import retroactivo as r


def test_meses_calendario_completos():
    assert r.meses(date(2022, 7, 1), date(2022, 7, 31)) == 1
    assert r.meses(date(2022, 2, 1), date(2022, 2, 28)) == 1     # febrero no bisiesto
    assert r.meses(date(2024, 2, 1), date(2024, 2, 29)) == 1     # bisiesto
    assert r.meses(date(2022, 1, 1), date(2022, 2, 28)) == 2
    assert r.meses(date(2022, 7, 1), date(2022, 12, 31)) == 6
    assert r.meses(date(2015, 3, 1), date(2015, 6, 30)) == 4


def test_meses_parciales_comerciales():
    assert r.meses(date(2022, 7, 16), date(2022, 7, 31)) == Decimal("0.5")
    assert r.meses(date(2022, 7, 1), date(2022, 7, 15)) == Decimal("0.5")
    assert r.meses(date(2022, 7, 31), date(2022, 8, 1)) == Decimal(2) / 30
    assert r.meses(date(2022, 8, 1), date(2022, 7, 1)) == 0


def test_dividir_en_tramos():
    cortes = [date(2022, 8, 1), date(2022, 12, 1), date(2021, 1, 1), date(2023, 1, 1), date(2022, 8, 1)]
    assert r.dividir_en_tramos(date(2022, 7, 1), date(2022, 12, 31), cortes) == [
        (date(2022, 7, 1), date(2022, 7, 31)), (date(2022, 8, 1), date(2022, 11, 30)), (date(2022, 12, 1), date(2022, 12, 31))]
    # un corte igual al inicio no genera un tramo vacío
    assert r.dividir_en_tramos(date(2022, 8, 1), date(2022, 8, 31), [date(2022, 8, 1)]) == [(date(2022, 8, 1), date(2022, 8, 31))]
    assert r.dividir_en_tramos(date(2022, 8, 1), date(2022, 8, 1), []) == [(date(2022, 8, 1), date(2022, 8, 1))]


def test_semestres_completos():
    assert r.semestres_completos(date(2022, 7, 1), date(2023, 3, 31)) == [(date(2022, 7, 1), date(2022, 12, 31))]
    assert r.semestres_completos(date(2022, 5, 1), date(2023, 6, 30)) == [
        (date(2022, 1, 1), date(2022, 6, 30)), (date(2022, 7, 1), date(2022, 12, 31)), (date(2023, 1, 1), date(2023, 6, 30))]
    assert r.semestres_completos(date(2022, 7, 1), date(2022, 12, 30)) == []


def test_sac_completo_y_proporcional():
    assert r.sac(Decimal(1000), date(2022, 7, 1), date(2022, 7, 1), date(2022, 12, 31)) == 500
    # alta a mitad de semestre: 3 de 6 meses
    assert r.sac(Decimal(1000), date(2022, 10, 1), date(2022, 7, 1), date(2022, 12, 31)) == 250
    # alta anterior al semestre: semestre completo
    assert r.sac(Decimal(1000), date(2020, 1, 1), date(2022, 7, 1), date(2022, 12, 31)) == 500
