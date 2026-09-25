use thiserror::Error;

/// Clase de un error de evaluación (se informa en `error_detalle.tipo`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TipoError {
    DivisionPorCero,
    Tipo,
    VariableNoDefinida,
    FuncionDesconocida,
    Desbordamiento,
    /// Tabla, fila o historial sin valor para lo pedido
    SinDatos,
    Otro,
}

impl TipoError {
    pub fn name(self) -> &'static str {
        match self {
            TipoError::DivisionPorCero => "division_por_cero",
            TipoError::Tipo => "tipo",
            TipoError::VariableNoDefinida => "variable_no_definida",
            TipoError::FuncionDesconocida => "funcion_desconocida",
            TipoError::Desbordamiento => "desbordamiento",
            TipoError::SinDatos => "sin_datos",
            TipoError::Otro => "otro",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Error)]
pub enum FormulaError {
    #[error("Error de sintaxis (posición {pos}): {msg}")]
    Syntax { pos: usize, msg: String },
    #[error("{msg}")]
    Eval { tipo: TipoError, pos: Option<usize>, msg: String },
    #[error("Depende del concepto {0}, que tiene error")]
    Dependency(String),
}

impl FormulaError {
    pub fn syntax(pos: usize, msg: impl Into<String>) -> Self {
        FormulaError::Syntax { pos, msg: msg.into() }
    }
    pub fn eval(msg: impl Into<String>) -> Self {
        FormulaError::of(TipoError::Otro, msg)
    }
    pub fn of(tipo: TipoError, msg: impl Into<String>) -> Self {
        FormulaError::Eval { tipo, pos: None, msg: msg.into() }
    }

    /// Completa la posición de un error de evaluación si todavía no tiene una (la más interna gana).
    pub fn con_pos(self, p: usize) -> Self {
        match self {
            FormulaError::Eval { tipo, pos: None, msg } => FormulaError::Eval { tipo, pos: Some(p), msg },
            other => other,
        }
    }

    pub fn tipo(&self) -> &'static str {
        match self {
            FormulaError::Syntax { .. } => "sintaxis",
            FormulaError::Eval { tipo, .. } => tipo.name(),
            FormulaError::Dependency(_) => "dependencia",
        }
    }

    pub fn pos(&self) -> Option<usize> {
        match self {
            FormulaError::Syntax { pos, .. } => Some(*pos),
            FormulaError::Eval { pos, .. } => *pos,
            FormulaError::Dependency(_) => None,
        }
    }
}

pub type Result<T> = std::result::Result<T, FormulaError>;
