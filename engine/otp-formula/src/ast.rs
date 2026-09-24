use rust_decimal::Decimal;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum BinOp {
    Add, Sub, Mul, Div,
    Eq, Ne, Lt, Le, Gt, Ge,
    And, Or,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Num(Decimal),
    Str(String),
    Bool(bool),
    Var(String),
    /// `#codigo`: importe del concepto (0 si no está asignado u oculto)
    Concept(String),
    Neg(Box<Expr>),
    Not(Box<Expr>),
    Bin(BinOp, Box<Expr>, Box<Expr>),
    Call { name: String, args: Vec<Expr>, pos: usize },
}
