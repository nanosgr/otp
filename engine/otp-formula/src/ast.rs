use rust_decimal::Decimal;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum BinOp {
    Add, Sub, Mul, Div, Pow,
    Eq, Ne, Lt, Le, Gt, Ge,
    And, Or,
}

/// Los `pos` son la posición (en caracteres) del token en la fórmula original, para ubicar los errores.
#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Num(Decimal),
    Str(String),
    Bool(bool),
    Var { name: String, pos: usize },
    /// `#codigo`: importe del concepto (0 si no está asignado u oculto)
    Concept(String),
    Neg(Box<Expr>),
    Not(Box<Expr>),
    Bin { op: BinOp, l: Box<Expr>, r: Box<Expr>, pos: usize },
    Call { name: String, args: Vec<Expr>, pos: usize },
}
