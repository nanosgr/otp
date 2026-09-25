use crate::ast::{BinOp, Expr};
use crate::error::{FormulaError, Result};
use crate::lexer::{lex, Tok, Token};
use rust_decimal::Decimal;

pub fn parse(src: &str) -> Result<Expr> {
    parse_tokens(lex(src)?)
}

pub fn parse_tokens(toks: Vec<Tok>) -> Result<Expr> {
    if toks.is_empty() {
        return Err(FormulaError::syntax(0, "Fórmula vacía"));
    }
    if toks.len() > MAX_TOKENS {
        return Err(FormulaError::syntax(0, format!("Fórmula demasiado larga (máximo {MAX_TOKENS} símbolos)")));
    }
    let mut p = Parser { toks, i: 0, depth: 0 };
    let e = p.or()?;
    if let Some(t) = p.toks.get(p.i) {
        return Err(FormulaError::syntax(t.pos, format!("Token inesperado {:?}", t.tok)));
    }
    if ast_depth(&e) > MAX_AST_DEPTH {
        return Err(FormulaError::syntax(0, "Fórmula demasiado compleja (demasiados operadores encadenados)"));
    }
    Ok(e)
}

/// Profundidad del árbol, calculada sin recursión.
fn ast_depth(root: &Expr) -> usize {
    let mut max = 0;
    let mut stack = vec![(root, 1usize)];
    while let Some((e, d)) = stack.pop() {
        max = max.max(d);
        match e {
            Expr::Neg(x) | Expr::Not(x) => stack.push((x, d + 1)),
            Expr::Bin { l, r, .. } => {
                stack.push((l, d + 1));
                stack.push((r, d + 1));
            }
            Expr::Call { args, .. } => stack.extend(args.iter().map(|a| (a, d + 1))),
            _ => {}
        }
    }
    max
}

const MAX_DEPTH: usize = 128;
const MAX_TOKENS: usize = 5_000;
const MAX_AST_DEPTH: usize = 200;

fn bin(op: BinOp, l: Expr, r: Expr, pos: usize) -> Expr {
    Expr::Bin { op, l: Box::new(l), r: Box::new(r), pos }
}

struct Parser {
    toks: Vec<Tok>,
    i: usize,
    depth: usize,
}

impl Parser {
    fn peek(&self) -> Option<&Token> {
        self.toks.get(self.i).map(|t| &t.tok)
    }
    fn pos(&self) -> usize {
        self.toks.get(self.i).or_else(|| self.toks.last()).map_or(0, |t| t.pos)
    }
    fn is_kw(&self, kw: &str) -> bool {
        matches!(self.peek(), Some(Token::Ident(s)) if s == kw)
    }
    fn eat(&mut self, t: &Token) -> bool {
        if self.peek() == Some(t) {
            self.i += 1;
            true
        } else {
            false
        }
    }

    fn or(&mut self) -> Result<Expr> {
        self.depth += 1;
        if self.depth > MAX_DEPTH {
            return Err(FormulaError::syntax(self.pos(), "Fórmula demasiado anidada"));
        }
        let r = self.or_inner();
        self.depth -= 1;
        r
    }

    fn or_inner(&mut self) -> Result<Expr> {
        let mut l = self.and()?;
        while self.is_kw("OR") {
            let pos = self.pos();
            self.i += 1;
            let r = self.and()?;
            l = bin(BinOp::Or, l, r, pos);
        }
        Ok(l)
    }

    fn and(&mut self) -> Result<Expr> {
        let mut l = self.not()?;
        while self.is_kw("AND") {
            let pos = self.pos();
            self.i += 1;
            let r = self.not()?;
            l = bin(BinOp::And, l, r, pos);
        }
        Ok(l)
    }

    fn not(&mut self) -> Result<Expr> {
        if self.is_kw("NOT") {
            self.i += 1;
            self.depth += 1;
            if self.depth > MAX_DEPTH {
                return Err(FormulaError::syntax(self.pos(), "Fórmula demasiado anidada"));
            }
            let inner = self.not();
            self.depth -= 1;
            return Ok(Expr::Not(Box::new(inner?)));
        }
        self.cmp()
    }

    fn cmp(&mut self) -> Result<Expr> {
        let mut l = self.add()?;
        loop {
            let op = match self.peek() {
                Some(Token::Eq) => BinOp::Eq,
                Some(Token::Ne) => BinOp::Ne,
                Some(Token::Lt) => BinOp::Lt,
                Some(Token::Le) => BinOp::Le,
                Some(Token::Gt) => BinOp::Gt,
                Some(Token::Ge) => BinOp::Ge,
                _ => break,
            };
            let pos = self.pos();
            self.i += 1;
            let r = self.add()?;
            l = bin(op, l, r, pos);
        }
        Ok(l)
    }

    fn add(&mut self) -> Result<Expr> {
        let mut l = self.mul()?;
        loop {
            let op = match self.peek() {
                Some(Token::Plus) => BinOp::Add,
                Some(Token::Minus) => BinOp::Sub,
                _ => break,
            };
            let pos = self.pos();
            self.i += 1;
            let r = self.mul()?;
            l = bin(op, l, r, pos);
        }
        Ok(l)
    }

    fn mul(&mut self) -> Result<Expr> {
        let mut l = self.pow()?;
        loop {
            let op = match self.peek() {
                Some(Token::Star) => BinOp::Mul,
                Some(Token::Slash) => BinOp::Div,
                _ => break,
            };
            let pos = self.pos();
            self.i += 1;
            let r = self.pow()?;
            l = bin(op, l, r, pos);
        }
        Ok(l)
    }

    /// `a ^ b`, asociativo por la derecha. El menos unario liga más fuerte (como Excel): `-2^2` = 4.
    fn pow(&mut self) -> Result<Expr> {
        let base = self.unary()?;
        if !matches!(self.peek(), Some(Token::Caret)) {
            return Ok(base);
        }
        let pos = self.pos();
        self.i += 1;
        self.depth += 1;
        if self.depth > MAX_DEPTH {
            return Err(FormulaError::syntax(pos, "Fórmula demasiado anidada"));
        }
        let exp = self.pow();
        self.depth -= 1;
        Ok(bin(BinOp::Pow, base, exp?, pos))
    }

    fn unary(&mut self) -> Result<Expr> {
        if self.eat(&Token::Minus) {
            self.depth += 1;
            if self.depth > MAX_DEPTH {
                return Err(FormulaError::syntax(self.pos(), "Fórmula demasiado anidada"));
            }
            let inner = self.unary();
            self.depth -= 1;
            return Ok(Expr::Neg(Box::new(inner?)));
        }
        if self.eat(&Token::Plus) {
            return self.unary();
        }
        self.postfix()
    }

    fn postfix(&mut self) -> Result<Expr> {
        let mut e = self.primary()?;
        loop {
            let pos = self.pos();
            if !self.eat(&Token::Percent) {
                break;
            }
            e = bin(BinOp::Div, e, Expr::Num(Decimal::from(100)), pos);
        }
        Ok(e)
    }

    fn primary(&mut self) -> Result<Expr> {
        let pos = self.pos();
        let tok = match self.toks.get(self.i) {
            Some(t) => t.tok.clone(),
            None => return Err(FormulaError::syntax(pos, "La fórmula termina inesperadamente")),
        };
        self.i += 1;
        match tok {
            Token::Num(n) => Ok(Expr::Num(n)),
            Token::Str(s) => Ok(Expr::Str(s)),
            Token::ConceptRef(c) => Ok(Expr::Concept(c)),
            Token::Param(_) => Err(FormulaError::syntax(pos, "Parámetro '?' fuera de una fórmula auxiliar")),
            Token::LParen => {
                let e = self.or()?;
                if !self.eat(&Token::RParen) {
                    return Err(FormulaError::syntax(self.pos(), "Se esperaba ')'"));
                }
                Ok(e)
            }
            Token::Ident(name) => {
                if name == "TRUE" || name == "VERDADERO" {
                    return Ok(Expr::Bool(true));
                }
                if name == "FALSE" || name == "FALSO" {
                    return Ok(Expr::Bool(false));
                }
                if self.eat(&Token::LParen) {
                    let mut args = Vec::new();
                    if !self.eat(&Token::RParen) {
                        loop {
                            args.push(self.or()?);
                            if self.eat(&Token::Comma) {
                                continue;
                            }
                            if self.eat(&Token::RParen) {
                                break;
                            }
                            return Err(FormulaError::syntax(self.pos(), "Se esperaba ',' o ')'"));
                        }
                    }
                    Ok(Expr::Call { name, args, pos })
                } else {
                    Ok(Expr::Var { name, pos })
                }
            }
            other => Err(FormulaError::syntax(pos, format!("Token inesperado {other:?}"))),
        }
    }
}
