use crate::error::{FormulaError, Result};
use crate::value::parse_decimal;
use rust_decimal::Decimal;

#[derive(Debug, Clone, PartialEq)]
pub enum Token {
    Num(Decimal),
    Str(String),
    Ident(String),
    ConceptRef(String),
    Param(usize),
    Plus,
    Minus,
    Star,
    Slash,
    Percent,
    LParen,
    RParen,
    Comma,
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Tok {
    pub tok: Token,
    pub pos: usize,
}

fn is_ident_start(c: char) -> bool {
    c.is_alphabetic() || c == '_'
}

fn is_ident_char(c: char) -> bool {
    c.is_alphanumeric() || c == '_' || c == '.'
}

pub fn lex(src: &str) -> Result<Vec<Tok>> {
    let chars: Vec<char> = src.chars().collect();
    let mut i = 0;
    let mut out = Vec::new();
    while i < chars.len() {
        let c = chars[i];
        let pos = i;
        if c.is_whitespace() {
            i += 1;
            continue;
        }
        let tok = match c {
            '+' => { i += 1; Token::Plus }
            '-' => { i += 1; Token::Minus }
            '*' => { i += 1; Token::Star }
            '/' => { i += 1; Token::Slash }
            '%' => { i += 1; Token::Percent }
            '(' => { i += 1; Token::LParen }
            ')' => { i += 1; Token::RParen }
            ',' => { i += 1; Token::Comma }
            '=' => { i += 1; if chars.get(i) == Some(&'=') { i += 1; } Token::Eq }
            '!' if chars.get(i + 1) == Some(&'=') => { i += 2; Token::Ne }
            '<' => {
                i += 1;
                match chars.get(i) {
                    Some('=') => { i += 1; Token::Le }
                    Some('>') => { i += 1; Token::Ne }
                    _ => Token::Lt,
                }
            }
            '>' => {
                i += 1;
                if chars.get(i) == Some(&'=') { i += 1; Token::Ge } else { Token::Gt }
            }
            '\'' | '"' => {
                let q = c;
                i += 1;
                let mut s = String::new();
                loop {
                    match chars.get(i) {
                        None => return Err(FormulaError::syntax(pos, "Texto sin cerrar")),
                        Some(&ch) if ch == q => { i += 1; break; }
                        Some(&ch) => { s.push(ch); i += 1; }
                    }
                }
                Token::Str(s)
            }
            '#' => {
                i += 1;
                let start = i;
                while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') { i += 1; }
                if start == i {
                    return Err(FormulaError::syntax(pos, "Se esperaba un código de concepto después de '#'"));
                }
                Token::ConceptRef(chars[start..i].iter().collect::<String>().to_uppercase())
            }
            '?' => {
                i += 1;
                let start = i;
                while i < chars.len() && chars[i].is_ascii_digit() { i += 1; }
                let n = if start == i { 0 } else { chars[start..i].iter().collect::<String>().parse().unwrap_or(0) };
                Token::Param(n)
            }
            d if d.is_ascii_digit() => {
                let start = i;
                while i < chars.len() && chars[i].is_ascii_digit() { i += 1; }
                if chars.get(i) == Some(&'.') && chars.get(i + 1).map_or(false, |x| x.is_ascii_digit()) {
                    i += 1;
                    while i < chars.len() && chars[i].is_ascii_digit() { i += 1; }
                }
                let text: String = chars[start..i].iter().collect();
                Token::Num(parse_decimal(&text).map_err(|_| FormulaError::syntax(pos, format!("Número inválido '{text}'")))?)
            }
            a if is_ident_start(a) => {
                let start = i;
                while i < chars.len() && is_ident_char(chars[i]) { i += 1; }
                Token::Ident(chars[start..i].iter().collect::<String>().to_uppercase())
            }
            other => return Err(FormulaError::syntax(pos, format!("Carácter inesperado '{other}'"))),
        };
        out.push(Tok { tok, pos });
    }
    Ok(out)
}
