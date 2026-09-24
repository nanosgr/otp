use crate::error::{FormulaError, Result};
use crate::lexer::{lex, Tok, Token};
use std::collections::HashMap;

const MAX_PASSES: usize = 50;
const MAX_TOKENS: usize = 50_000;

#[derive(Debug, Clone)]
pub struct FormulaAuxiliar {
    pub codigo: String,
    /// Ej.: `(a,b)`; vacío = constante sin parámetros
    pub formato: Option<String>,
    pub formula: String,
}

struct Macro {
    params: usize,
    body: Vec<Tok>,
}

#[derive(Default)]
pub struct MacroTable {
    macros: HashMap<String, Macro>,
}

impl MacroTable {
    pub fn new(defs: &[FormulaAuxiliar]) -> Result<Self> {
        let mut macros = HashMap::new();
        for d in defs {
            let params = match d.formato.as_deref().map(str::trim) {
                None | Some("") | Some("()") => 0,
                Some(f) => f.trim_matches(|c| c == '(' || c == ')').split(',').count(),
            };
            let body = lex(&d.formula)
                .map_err(|e| FormulaError::eval(format!("Fórmula auxiliar {}: {e}", d.codigo)))?;
            macros.insert(d.codigo.to_uppercase(), Macro { params, body });
        }
        Ok(MacroTable { macros })
    }

    pub fn is_empty(&self) -> bool {
        self.macros.is_empty()
    }

    pub fn expand(&self, mut toks: Vec<Tok>) -> Result<Vec<Tok>> {
        if self.macros.is_empty() {
            return Ok(toks);
        }
        for _ in 0..MAX_PASSES {
            let (next, changed) = self.pass(&toks)?;
            if next.len() > MAX_TOKENS {
                return Err(FormulaError::eval("La expansión de fórmulas auxiliares es demasiado grande"));
            }
            toks = next;
            if !changed {
                return Ok(toks);
            }
        }
        Err(FormulaError::eval("Error de recursividad en fórmulas auxiliares"))
    }

    fn pass(&self, toks: &[Tok]) -> Result<(Vec<Tok>, bool)> {
        let mut out = Vec::with_capacity(toks.len());
        let mut changed = false;
        let mut i = 0;
        while i < toks.len() {
            let t = &toks[i];
            let m = match &t.tok {
                Token::Ident(name) => self.macros.get(name).map(|m| (name, m)),
                _ => None,
            };
            let Some((name, m)) = m else {
                out.push(t.clone());
                i += 1;
                continue;
            };
            changed = true;
            let mut args: Vec<Vec<Tok>> = Vec::new();
            i += 1;
            if m.params > 0 {
                if toks.get(i).map(|x| &x.tok) != Some(&Token::LParen) {
                    return Err(FormulaError::syntax(t.pos, format!("La fórmula auxiliar {name} requiere {} parámetro(s)", m.params)));
                }
                i += 1;
                let mut depth = 1;
                let mut cur = Vec::new();
                loop {
                    let Some(x) = toks.get(i) else {
                        return Err(FormulaError::syntax(t.pos, format!("Paréntesis sin cerrar en {name}")));
                    };
                    i += 1;
                    match x.tok {
                        Token::LParen => { depth += 1; cur.push(x.clone()); }
                        Token::RParen => {
                            depth -= 1;
                            if depth == 0 { args.push(std::mem::take(&mut cur)); break; }
                            cur.push(x.clone());
                        }
                        Token::Comma if depth == 1 => args.push(std::mem::take(&mut cur)),
                        _ => cur.push(x.clone()),
                    }
                }
                if args.len() != m.params {
                    return Err(FormulaError::syntax(t.pos, format!("{name} espera {} parámetro(s) y recibió {}", m.params, args.len())));
                }
            }
            out.push(Tok { tok: Token::LParen, pos: t.pos });
            for b in &m.body {
                match &b.tok {
                    Token::Param(n) => {
                        let arg = args.get(*n).ok_or_else(|| {
                            FormulaError::syntax(t.pos, format!("{name}: referencia al parámetro ?{n} inexistente"))
                        })?;
                        out.push(Tok { tok: Token::LParen, pos: t.pos });
                        out.extend(arg.iter().cloned());
                        out.push(Tok { tok: Token::RParen, pos: t.pos });
                    }
                    _ => out.push(Tok { tok: b.tok.clone(), pos: t.pos }),
                }
            }
            out.push(Tok { tok: Token::RParen, pos: t.pos });
        }
        Ok((out, changed))
    }
}
