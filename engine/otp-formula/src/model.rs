use rust_decimal::Decimal;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Columna {
    Remunerativo,
    NoRemunerativo,
    Descuento,
    Contribucion,
    Auxiliar,
}

impl Columna {
    pub fn parse(s: &str) -> Option<Columna> {
        match s.to_uppercase().as_str() {
            "REMUNERATIVO" => Some(Columna::Remunerativo),
            "NO_REMUNERATIVO" => Some(Columna::NoRemunerativo),
            "DESCUENTO" => Some(Columna::Descuento),
            "CONTRIBUCION" => Some(Columna::Contribucion),
            "AUXILIAR" => Some(Columna::Auxiliar),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Columna::Remunerativo => "REMUNERATIVO",
            Columna::NoRemunerativo => "NO_REMUNERATIVO",
            Columna::Descuento => "DESCUENTO",
            Columna::Contribucion => "CONTRIBUCION",
            Columna::Auxiliar => "AUXILIAR",
        }
    }
}

#[derive(Debug, Clone)]
pub struct ConceptoDef {
    pub codigo: String,
    pub descripcion: String,
    pub columna: Columna,
    pub formula_unidad: Option<String>,
    pub formula_importe: Option<String>,
    pub formula_unitario: Option<String>,
    pub formula_condicion: Option<String>,
    pub decimales_unidad: u32,
    pub decimales_importe: u32,
    pub orden: i32,
}

#[derive(Debug, Clone)]
pub struct ConceptoRes {
    pub codigo: String,
    pub descripcion: String,
    pub columna: Columna,
    pub orden: i32,
    pub unidad: Option<Decimal>,
    pub unitario: Option<Decimal>,
    pub importe: Decimal,
    pub decimales_importe: u32,
    pub condicion: bool,
    pub error: Option<String>,
    pub error_detalle: Option<ErrorDetalle>,
}

/// Dónde y de qué clase fue el error de un concepto (`campo` = fórmula que falló; `pos` = carácter en esa fórmula).
#[derive(Debug, Clone, PartialEq)]
pub struct ErrorDetalle {
    pub campo: Option<&'static str>,
    pub tipo: &'static str,
    pub pos: Option<usize>,
}

impl ConceptoRes {
    /// Cuenta en totales y en referencias: condición verdadera y sin error.
    pub fn visible(&self) -> bool {
        self.condicion && self.error.is_none()
    }
}
