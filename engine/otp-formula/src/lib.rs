//! Motor de fórmulas de online-otp: liquidación de haberes previsionales con reglas configurables.
//!
//! El motor es puro: recibe reglas (conceptos con fórmulas, auxiliares, grupos) y un contexto ya
//! cargado (variables, tablas, historial, beneficiarios) y devuelve conceptos calculados y totales.

pub mod analysis;
pub mod ast;
pub mod context;
pub mod engine;
pub mod error;
pub mod eval;
pub mod lexer;
pub mod macros;
pub mod model;
pub mod parser;
pub mod value;

pub use engine::{calcular, validar_formula, validar_reglas, Reglas, Resultado};
pub use error::FormulaError;

use serde_json::Value as J;

fn parse_json(s: &str, what: &str) -> Result<J, FormulaError> {
    serde_json::from_str(s).map_err(|e| FormulaError::eval(format!("JSON inválido en {what}: {e}")))
}

/// Calcula un recibo. Entrada y salida en JSON (ver `docs/engine.md`).
pub fn calcular_json(reglas: &str, contexto: &str) -> Result<String, FormulaError> {
    let reglas = Reglas::from_json(&parse_json(reglas, "reglas")?)?;
    let ctx = context::Contexto::from_json(&parse_json(contexto, "contexto")?)?;
    Ok(calcular(&reglas, &ctx)?.to_json().to_string())
}

/// Valida todas las reglas (sintaxis, aridad, selectores, ciclos). Devuelve una lista JSON de problemas.
pub fn validar_reglas_json(reglas: &str, variables_conocidas: Option<Vec<String>>) -> Result<String, FormulaError> {
    let reglas = Reglas::from_json(&parse_json(reglas, "reglas")?)?;
    let known = variables_conocidas.map(|v| v.into_iter().map(|s| s.to_uppercase()).collect());
    let problemas = validar_reglas(&reglas, known.as_ref())?;
    Ok(J::Array(problemas.iter().map(|p| p.to_json()).collect()).to_string())
}

/// Valida una fórmula suelta. `auxiliares` es una lista JSON `[{"codigo","formato","formula"}]` (puede ser vacía).
pub fn validar_formula_json(formula: &str, auxiliares: &str) -> Result<String, FormulaError> {
    let aux = Reglas::from_json(&serde_json::json!({"auxiliares": parse_json(auxiliares, "auxiliares")?}))?.auxiliares;
    Ok(validar_formula(formula, &aux)?.to_string())
}
