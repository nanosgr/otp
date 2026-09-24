use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Error)]
pub enum FormulaError {
    #[error("Error de sintaxis (posición {pos}): {msg}")]
    Syntax { pos: usize, msg: String },
    #[error("{0}")]
    Eval(String),
    #[error("Depende del concepto {0}, que tiene error")]
    Dependency(String),
}

impl FormulaError {
    pub fn syntax(pos: usize, msg: impl Into<String>) -> Self {
        FormulaError::Syntax { pos, msg: msg.into() }
    }
    pub fn eval(msg: impl Into<String>) -> Self {
        FormulaError::Eval(msg.into())
    }
}

pub type Result<T> = std::result::Result<T, FormulaError>;
