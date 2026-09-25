//! Binding Python (PyO3) del motor de fórmulas. Todas las funciones intercambian JSON (str).
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

create_exception!(otp_engine, FormulaError, PyValueError, "Error de sintaxis o de evaluación del motor de fórmulas.");

fn map_err(e: otp_formula::FormulaError) -> PyErr {
    FormulaError::new_err(e.to_string())
}

/// calcular(reglas_json, contexto_json) -> str (JSON con conceptos y totales)
#[pyfunction]
fn calcular(py: Python<'_>, reglas_json: String, contexto_json: String) -> PyResult<String> {
    py.allow_threads(move || otp_formula::calcular_json(&reglas_json, &contexto_json)).map_err(map_err)
}

/// Reglas compiladas una vez: `ReglasCompiladas(reglas_json).calcular(contexto_json)` da lo mismo que
/// `calcular(reglas_json, contexto_json)` sin volver a parsear las fórmulas ni rearmar el orden de evaluación.
#[pyclass(frozen, module = "otp_engine")]
struct ReglasCompiladas {
    inner: otp_formula::Compilado,
}

#[pymethods]
impl ReglasCompiladas {
    #[new]
    fn new(py: Python<'_>, reglas_json: String) -> PyResult<Self> {
        let inner = py.allow_threads(move || otp_formula::compilar_json(&reglas_json)).map_err(map_err)?;
        Ok(ReglasCompiladas { inner })
    }

    /// calcular(contexto_json) -> str (JSON con conceptos y totales)
    fn calcular(&self, py: Python<'_>, contexto_json: String) -> PyResult<String> {
        py.allow_threads(|| self.inner.calcular_json(&contexto_json)).map_err(map_err)
    }
}

/// validar_reglas(reglas_json, variables_conocidas=None) -> str (JSON: lista de problemas)
#[pyfunction]
#[pyo3(signature = (reglas_json, variables_conocidas=None))]
fn validar_reglas(py: Python<'_>, reglas_json: String, variables_conocidas: Option<Vec<String>>) -> PyResult<String> {
    py.allow_threads(move || otp_formula::validar_reglas_json(&reglas_json, variables_conocidas)).map_err(map_err)
}

/// validar_formula(formula, auxiliares_json="[]") -> str (JSON con lo que referencia); lanza FormulaError si es inválida
#[pyfunction]
#[pyo3(signature = (formula, auxiliares_json="[]".to_string()))]
fn validar_formula(py: Python<'_>, formula: String, auxiliares_json: String) -> PyResult<String> {
    py.allow_threads(move || otp_formula::validar_formula_json(&formula, &auxiliares_json)).map_err(map_err)
}

#[pymodule]
fn otp_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("FormulaError", m.py().get_type::<FormulaError>())?;
    m.add_class::<ReglasCompiladas>()?;
    m.add_function(wrap_pyfunction!(calcular, m)?)?;
    m.add_function(wrap_pyfunction!(validar_reglas, m)?)?;
    m.add_function(wrap_pyfunction!(validar_formula, m)?)?;
    Ok(())
}
