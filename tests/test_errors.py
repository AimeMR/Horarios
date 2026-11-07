from extractor.errors import CargaError, ExtractorError


def test_carga_error_inclou_ubicacio_sense_valor() -> None:
    valor_cella = "S912345"
    error = CargaError("sessions.csv", 42, "id_grup", "valor fuera del dominio permitido")
    missatge = str(error)
    assert "sessions.csv" in missatge
    assert "42" in missatge
    assert "id_grup" in missatge
    assert "valor fuera del dominio permitido" in missatge
    assert valor_cella not in missatge
    assert isinstance(error, ExtractorError)


def test_carga_error_sense_linia_ni_columna() -> None:
    error = CargaError("plans.csv", None, None, "falta el fichero")
    assert str(error) == "fichero plans.csv: falta el fichero"
    assert error.linia is None
    assert error.columna is None
