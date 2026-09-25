//! Análisis estático de expresiones: aridad de funciones, selectores y referencias.
use crate::ast::Expr;
use crate::error::FormulaError;
use crate::functions::buscar;
use std::collections::BTreeSet;

pub const AGG_OPS: &[&str] = &["+", "*", "MAX", "MIN", "AVG", "AND", "OR", "COUNT"];

/// Nombres de variables definidas por el propio motor (no vienen del contexto).
pub const BUILTIN_VARS: &[&str] = &[
    "FECHA", "UNIDAD", "UNITARIO", "IMPORTE", "CODIGO", "CAMPO_UNIDAD", "CAMPO_IMPORTE",
];

#[derive(Debug, Default, Clone)]
pub struct Selector {
    pub name: String,
    pub excluded: BTreeSet<String>,
}

#[derive(Debug, Default, Clone)]
pub struct Refs {
    pub concepts: BTreeSet<String>,
    pub selectors: Vec<Selector>,
    pub vars: BTreeSet<String>,
    pub tablas: BTreeSet<String>,
    pub historial: BTreeSet<String>,
}

pub fn collect(e: &Expr, r: &mut Refs, errors: &mut Vec<FormulaError>) {
    match e {
        Expr::Num(_) | Expr::Str(_) | Expr::Bool(_) => {}
        Expr::Var { name, .. } => {
            r.vars.insert(name.clone());
        }
        Expr::Concept(c) => {
            r.concepts.insert(c.clone());
        }
        Expr::Neg(x) | Expr::Not(x) => collect(x, r, errors),
        Expr::Bin { l, r: rhs, .. } => {
            collect(l, r, errors);
            collect(rhs, r, errors);
        }
        Expr::Call { name, args, pos } => {
            let Some(f) = buscar(name) else {
                errors.push(FormulaError::syntax(*pos, format!("Función desconocida: {name}")));
                args.iter().for_each(|a| collect(a, r, errors));
                return;
            };
            let (min, max) = (f.min, f.max);
            if args.len() < min || args.len() > max {
                errors.push(FormulaError::syntax(*pos, format!("{name} espera entre {min} y {} argumentos y recibió {}", if max == usize::MAX { "N".to_string() } else { max.to_string() }, args.len())));
            }
            match f.nombre {
                "TOTAL" => {
                    if let Some(Expr::Str(sel)) = args.first() {
                        let mut s = Selector { name: sel.to_uppercase(), excluded: BTreeSet::new() };
                        for a in &args[1..] {
                            match a {
                                Expr::Concept(c) => { s.excluded.insert(c.clone()); }
                                _ => errors.push(FormulaError::syntax(*pos, "TOTAL: los argumentos de exclusión deben ser referencias #concepto")),
                            }
                        }
                        r.selectors.push(s);
                    } else if !args.is_empty() {
                        errors.push(FormulaError::syntax(*pos, "TOTAL: el selector debe ser un texto literal (columna o grupo)"));
                    }
                }
                "CONCEPTOS" => {
                    if let Some(Expr::Str(sel)) = args.first() {
                        r.selectors.push(Selector { name: sel.to_uppercase(), excluded: BTreeSet::new() });
                    } else if !args.is_empty() {
                        errors.push(FormulaError::syntax(*pos, "CONCEPTOS: el selector debe ser un texto literal (columna o grupo)"));
                    }
                    check_op(args.get(1), *pos, errors);
                    if let Some(b) = args.get(2) {
                        collect(b, r, errors);
                    }
                }
                "BENEFICIARIOS" => {
                    check_op(args.get(1), *pos, errors);
                    if let Some(f) = args.first() {
                        collect(f, r, errors);
                    }
                    if let Some(b) = args.get(2) {
                        collect(b, r, errors);
                    }
                }
                "TABLA" => {
                    if let Some(Expr::Str(t)) = args.first() {
                        r.tablas.insert(t.to_uppercase());
                    } else if !args.is_empty() {
                        errors.push(FormulaError::syntax(*pos, "TABLA: el código de tabla debe ser un texto literal"));
                    }
                    args.iter().skip(1).for_each(|a| collect(a, r, errors));
                }
                "HISTORIAL" | "EXISTE_HISTORIAL" => {
                    if let Some(Expr::Str(t)) = args.first() {
                        r.historial.insert(t.to_uppercase());
                    } else if !args.is_empty() {
                        errors.push(FormulaError::syntax(*pos, format!("{name}: el campo debe ser un texto literal")));
                    }
                    args.iter().skip(1).for_each(|a| collect(a, r, errors));
                }
                "EXISTE" | "UNIDAD_CONCEPTO" | "IMPORTE_CONCEPTO" | "UNITARIO_CONCEPTO" => {
                    match args.first() {
                        Some(Expr::Concept(c)) => { r.concepts.insert(c.clone()); }
                        Some(_) => errors.push(FormulaError::syntax(*pos, format!("{name}: el argumento debe ser una referencia #concepto"))),
                        None => {}
                    }
                }
                _ => args.iter().for_each(|a| collect(a, r, errors)),
            }
        }
    }
}

fn check_op(op: Option<&Expr>, pos: usize, errors: &mut Vec<FormulaError>) {
    match op {
        Some(Expr::Str(s)) if AGG_OPS.contains(&s.to_uppercase().as_str()) => {}
        Some(_) => errors.push(FormulaError::syntax(pos, format!("El operador de agregación debe ser un texto literal entre: {}", AGG_OPS.join(", ")))),
        None => {}
    }
}
