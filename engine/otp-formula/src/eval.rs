use crate::analysis::canonical;
use crate::ast::{BinOp, Expr};
use crate::context::Contexto;
use crate::error::{FormulaError, Result};
use crate::model::{Columna, ConceptoDef, ConceptoRes};
use crate::value::{parse_date, Value};
use chrono::Datelike;
use rust_decimal::{Decimal, RoundingStrategy};
use std::cmp::Ordering;
use std::collections::HashMap;

pub struct Env<'a> {
    pub ctx: &'a Contexto,
    pub defs: &'a HashMap<String, ConceptoDef>,
    pub grupos: &'a HashMap<String, Vec<String>>,
    pub results: &'a HashMap<String, ConceptoRes>,
    pub current: &'a str,
    pub scopes: Vec<HashMap<String, Value>>,
}

fn overflow() -> FormulaError {
    FormulaError::eval("Desbordamiento numérico")
}

fn cmp_values(a: &Value, b: &Value) -> Result<Ordering> {
    match (a, b) {
        (Value::Num(x), Value::Num(y)) => Ok(x.cmp(y)),
        (Value::Text(x), Value::Text(y)) => Ok(x.cmp(y)),
        (Value::Date(x), Value::Date(y)) => Ok(x.cmp(y)),
        (Value::Bool(x), Value::Bool(y)) => Ok(x.cmp(y)),
        _ => Err(FormulaError::eval(format!("No se puede comparar {} con {}", a.type_name(), b.type_name()))),
    }
}

fn round_to(n: Decimal, dp: i64) -> Result<Decimal> {
    if !(0..=28).contains(&dp) {
        return Err(FormulaError::eval("La cantidad de decimales debe estar entre 0 y 28"));
    }
    Ok(n.round_dp_with_strategy(dp as u32, RoundingStrategy::MidpointAwayFromZero))
}

pub fn round_half_up(n: Decimal, dp: u32) -> Decimal {
    n.round_dp_with_strategy(dp, RoundingStrategy::MidpointAwayFromZero)
}

fn aggregate(op: &str, vals: Vec<Value>) -> Result<Value> {
    let nums = |vals: &[Value]| -> Result<Vec<Decimal>> { vals.iter().map(Value::num).collect() };
    Ok(match op.to_uppercase().as_str() {
        "+" => {
            let mut acc = Decimal::ZERO;
            for n in nums(&vals)? { acc = acc.checked_add(n).ok_or_else(overflow)?; }
            Value::Num(acc)
        }
        "*" => {
            let mut acc = Decimal::ONE;
            for n in nums(&vals)? { acc = acc.checked_mul(n).ok_or_else(overflow)?; }
            Value::Num(acc)
        }
        "MAX" => Value::Num(nums(&vals)?.into_iter().max().unwrap_or(Decimal::ZERO)),
        "MIN" => Value::Num(nums(&vals)?.into_iter().min().unwrap_or(Decimal::ZERO)),
        "AVG" => {
            let n = nums(&vals)?;
            if n.is_empty() {
                Value::Num(Decimal::ZERO)
            } else {
                let sum = n.iter().try_fold(Decimal::ZERO, |a, x| a.checked_add(*x)).ok_or_else(overflow)?;
                Value::Num(sum / Decimal::from(n.len()))
            }
        }
        "AND" => {
            let mut r = true;
            for v in &vals { r &= v.boolean()?; }
            Value::Bool(r)
        }
        "OR" => {
            let mut r = false;
            for v in &vals { r |= v.boolean()?; }
            Value::Bool(r)
        }
        "COUNT" => Value::Num(Decimal::from(vals.iter().filter(|v| !matches!(v, Value::Bool(false))).count())),
        other => return Err(FormulaError::eval(format!("Operador de agregación desconocido: {other}"))),
    })
}

impl<'a> Env<'a> {
    fn lookup(&self, name: &str) -> Result<Value> {
        for s in self.scopes.iter().rev() {
            if let Some(v) = s.get(name) {
                return Ok(v.clone());
            }
        }
        if name == "FECHA" {
            return Ok(Value::Date(self.ctx.fecha));
        }
        if let Some(v) = self.ctx.variables.get(name) {
            return Ok(v.clone());
        }
        Err(FormulaError::eval(format!("Variable no definida: {name}")))
    }

    /// Resultado de un concepto referenciado. `None` = no está asignado en esta liquidación.
    fn result_of(&self, code: &str) -> Result<Option<&'a ConceptoRes>> {
        match self.results.get(code) {
            Some(r) if r.error.is_some() => Err(FormulaError::Dependency(code.to_string())),
            Some(r) => Ok(Some(r)),
            None if self.defs.contains_key(code) => Err(FormulaError::eval(format!("El concepto {code} aún no fue calculado"))),
            None => Ok(None),
        }
    }

    fn select(&self, name: &str) -> Result<Vec<&'a ConceptoDef>> {
        let up = name.to_uppercase();
        let mut list: Vec<&ConceptoDef> = if let Some(col) = Columna::parse(&up) {
            self.defs.values().filter(|d| d.columna == col).collect()
        } else if let Some(members) = self.grupos.get(&up) {
            members.iter().filter_map(|c| self.defs.get(c)).collect()
        } else {
            return Err(FormulaError::eval(format!("Selector desconocido (columna o grupo): {name}")));
        };
        list.retain(|d| d.codigo != self.current);
        list.sort_by(|a, b| (a.orden, &a.codigo).cmp(&(b.orden, &b.codigo)));
        Ok(list)
    }

    fn with_scope<T>(&mut self, scope: HashMap<String, Value>, f: impl FnOnce(&mut Self) -> Result<T>) -> Result<T> {
        self.scopes.push(scope);
        let r = f(self);
        self.scopes.pop();
        r
    }

    pub fn eval(&mut self, e: &Expr) -> Result<Value> {
        match e {
            Expr::Num(n) => Ok(Value::Num(*n)),
            Expr::Str(s) => Ok(Value::Text(s.clone())),
            Expr::Bool(b) => Ok(Value::Bool(*b)),
            Expr::Var(v) => self.lookup(v),
            Expr::Concept(c) => Ok(Value::Num(match self.result_of(c)? {
                Some(r) if r.visible() => r.importe,
                _ => Decimal::ZERO,
            })),
            Expr::Neg(x) => Ok(Value::Num(-self.eval(x)?.num()?)),
            Expr::Not(x) => Ok(Value::Bool(!self.eval(x)?.boolean()?)),
            Expr::Bin(op, a, b) => self.binary(*op, a, b),
            Expr::Call { name, args, .. } => self.call(name, args),
        }
    }

    fn binary(&mut self, op: BinOp, a: &Expr, b: &Expr) -> Result<Value> {
        match op {
            BinOp::And => {
                return Ok(Value::Bool(self.eval(a)?.boolean()? && self.eval(b)?.boolean()?));
            }
            BinOp::Or => {
                return Ok(Value::Bool(self.eval(a)?.boolean()? || self.eval(b)?.boolean()?));
            }
            _ => {}
        }
        let l = self.eval(a)?;
        let r = self.eval(b)?;
        match op {
            BinOp::Add => match (&l, &r) {
                (Value::Text(x), Value::Text(y)) => Ok(Value::Text(format!("{x}{y}"))),
                _ => Ok(Value::Num(l.num()?.checked_add(r.num()?).ok_or_else(overflow)?)),
            },
            BinOp::Sub => Ok(Value::Num(l.num()?.checked_sub(r.num()?).ok_or_else(overflow)?)),
            BinOp::Mul => Ok(Value::Num(l.num()?.checked_mul(r.num()?).ok_or_else(overflow)?)),
            BinOp::Div => {
                let d = r.num()?;
                if d.is_zero() {
                    return Err(FormulaError::eval("División por cero"));
                }
                Ok(Value::Num(l.num()?.checked_div(d).ok_or_else(overflow)?))
            }
            BinOp::Eq => Ok(Value::Bool(cmp_values(&l, &r)? == Ordering::Equal)),
            BinOp::Ne => Ok(Value::Bool(cmp_values(&l, &r)? != Ordering::Equal)),
            BinOp::Lt => Ok(Value::Bool(cmp_values(&l, &r)? == Ordering::Less)),
            BinOp::Le => Ok(Value::Bool(cmp_values(&l, &r)? != Ordering::Greater)),
            BinOp::Gt => Ok(Value::Bool(cmp_values(&l, &r)? == Ordering::Greater)),
            BinOp::Ge => Ok(Value::Bool(cmp_values(&l, &r)? != Ordering::Less)),
            BinOp::And | BinOp::Or => unreachable!(),
        }
    }

    fn eager(&mut self, args: &[Expr]) -> Result<Vec<Value>> {
        args.iter().map(|a| self.eval(a)).collect()
    }

    fn concept_arg(args: &[Expr]) -> Result<&str> {
        match args.first() {
            Some(Expr::Concept(c)) => Ok(c),
            _ => Err(FormulaError::eval("Se esperaba una referencia #concepto")),
        }
    }

    fn call(&mut self, name: &str, args: &[Expr]) -> Result<Value> {
        match canonical(name) {
            "IF" => {
                if self.eval(&args[0])?.boolean()? { self.eval(&args[1]) } else { self.eval(&args[2]) }
            }
            "ROUND" | "TRUNC" => {
                let v = self.eager(args)?;
                let n = v[0].num()?;
                let dp = if v.len() > 1 { v[1].num()?.trunc().to_string().parse::<i64>().unwrap_or(-1) } else { 0 };
                if canonical(name) == "ROUND" {
                    Ok(Value::Num(round_to(n, dp)?))
                } else {
                    if !(0..=28).contains(&dp) {
                        return Err(FormulaError::eval("La cantidad de decimales debe estar entre 0 y 28"));
                    }
                    Ok(Value::Num(n.trunc_with_scale(dp as u32)))
                }
            }
            "MIN" | "MAX" => {
                let nums: Result<Vec<Decimal>> = self.eager(args)?.iter().map(Value::num).collect();
                let nums = nums?;
                let r = if name == "MIN" { nums.into_iter().min() } else { nums.into_iter().max() };
                Ok(Value::Num(r.expect("aridad validada")))
            }
            "ABS" => Ok(Value::Num(self.eager(args)?[0].num()?.abs())),
            "FECHA" => match self.eval(&args[0])? {
                Value::Date(d) => Ok(Value::Date(d)),
                Value::Text(s) => Ok(Value::Date(parse_date(&s)?)),
                o => Err(FormulaError::eval(format!("FECHA no acepta {}", o.type_name()))),
            },
            "ANIOS" | "MESES" | "DIAS" => {
                let v = self.eager(args)?;
                let (d1, d2) = (v[0].date()?, v[1].date()?);
                let n = match name {
                    "ANIOS" => {
                        let mut y = d2.year() - d1.year();
                        if (d2.month(), d2.day()) < (d1.month(), d1.day()) { y -= 1; }
                        i64::from(y)
                    }
                    "MESES" => {
                        let mut m = (d2.year() - d1.year()) * 12 + d2.month() as i32 - d1.month() as i32;
                        if d2.day() < d1.day() { m -= 1; }
                        i64::from(m)
                    }
                    _ => (d2 - d1).num_days(),
                };
                Ok(Value::Num(Decimal::from(n)))
            }
            "ANIO" => Ok(Value::Num(Decimal::from(self.eager(args)?[0].date()?.year()))),
            "MES" => Ok(Value::Num(Decimal::from(self.eager(args)?[0].date()?.month()))),
            "DIA" => Ok(Value::Num(Decimal::from(self.eager(args)?[0].date()?.day()))),
            "TABLA" => self.tabla(args),
            "HISTORIAL" | "EXISTE_HISTORIAL" => self.historial(name == "EXISTE_HISTORIAL", args),
            "EXISTE" => {
                let c = Self::concept_arg(args)?;
                Ok(Value::Bool(self.result_of(c)?.map_or(false, |r| r.visible())))
            }
            "UNIDAD_CONCEPTO" | "UNITARIO_CONCEPTO" | "IMPORTE_CONCEPTO" => {
                let c = Self::concept_arg(args)?;
                let r = self.result_of(c)?.filter(|r| r.visible());
                Ok(Value::Num(match (name, r) {
                    (_, None) => Decimal::ZERO,
                    ("UNIDAD_CONCEPTO", Some(r)) => r.unidad.unwrap_or_default(),
                    ("UNITARIO_CONCEPTO", Some(r)) => r.unitario.unwrap_or_default(),
                    (_, Some(r)) => r.importe,
                }))
            }
            "TOTAL" => {
                let sel = self.eval(&args[0])?;
                let excluded: Vec<&str> = args[1..].iter().filter_map(|a| if let Expr::Concept(c) = a { Some(c.as_str()) } else { None }).collect();
                let mut acc = Decimal::ZERO;
                for d in self.select(sel.text()?)? {
                    if excluded.contains(&d.codigo.as_str()) { continue; }
                    if let Some(r) = self.result_of(&d.codigo)?.filter(|r| r.visible()) {
                        acc = acc.checked_add(r.importe).ok_or_else(overflow)?;
                    }
                }
                Ok(Value::Num(acc))
            }
            "CONCEPTOS" => {
                let sel = self.eval(&args[0])?;
                let op = self.eval(&args[1])?;
                let mut vals = Vec::new();
                for d in self.select(sel.text()?)? {
                    let Some(r) = self.result_of(&d.codigo)?.filter(|r| r.visible()) else { continue };
                    let mut scope = HashMap::new();
                    scope.insert("UNIDAD".to_string(), Value::Num(r.unidad.unwrap_or_default()));
                    scope.insert("UNITARIO".to_string(), Value::Num(r.unitario.unwrap_or_default()));
                    scope.insert("IMPORTE".to_string(), Value::Num(r.importe));
                    scope.insert("CODIGO".to_string(), Value::Text(r.codigo.clone()));
                    vals.push(self.with_scope(scope, |env| env.eval(&args[2]))?);
                }
                aggregate(op.text()?, vals)
            }
            "BENEFICIARIOS" => {
                let filtro = self.eval(&args[0])?;
                let filtro = filtro.text()?.to_uppercase();
                let op = self.eval(&args[1])?;
                let ctx = self.ctx;
                let mut vals = Vec::new();
                for b in &ctx.beneficiarios {
                    if filtro != "TODOS" {
                        match b.get("PARENTESCO") {
                            Some(Value::Text(p)) if p.to_uppercase() == filtro => {}
                            _ => continue,
                        }
                    }
                    vals.push(self.with_scope(b.clone(), |env| env.eval(&args[2]))?);
                }
                aggregate(op.text()?, vals)
            }
            other => Err(FormulaError::eval(format!("Función desconocida: {other}"))),
        }
    }

    fn tabla(&mut self, args: &[Expr]) -> Result<Value> {
        let code = self.eval(&args[0])?;
        let code = code.text()?.to_uppercase();
        let ctx = self.ctx;
        let tabla = ctx.tablas.get(&code).ok_or_else(|| FormulaError::eval(format!("Tabla no definida: {code}")))?;
        for fila in &tabla.filas {
            let mut scope = HashMap::new();
            for (i, (nombre, v)) in tabla.columnas.iter().zip(fila).enumerate() {
                scope.insert(format!("COL{}", i + 1), v.clone());
                if !nombre.is_empty() {
                    scope.insert(format!("COL.{nombre}"), v.clone());
                }
            }
            let hit = self.with_scope(scope, |env| {
                if env.eval(&args[1])?.boolean()? { env.eval(&args[2]).map(Some) } else { Ok(None) }
            })?;
            if let Some(v) = hit {
                return Ok(v);
            }
        }
        match args.get(3) {
            Some(d) => self.eval(d),
            None => Err(FormulaError::eval(format!("Valor no encontrado en la tabla {code}"))),
        }
    }

    fn historial(&mut self, exists: bool, args: &[Expr]) -> Result<Value> {
        let campo = self.eval(&args[0])?;
        let campo = campo.text()?.to_uppercase();
        let fecha = match args.get(1) {
            Some(a) => self.eval(a)?.date()?,
            None => self.ctx.fecha,
        };
        let found = self.ctx.historial.get(&campo).and_then(|items| {
            items
                .iter()
                .filter(|i| i.desde.map_or(true, |d| d <= fecha) && i.hasta.map_or(true, |h| h >= fecha))
                .max_by_key(|i| i.desde)
        });
        if exists {
            return Ok(Value::Bool(found.is_some()));
        }
        match (found, args.get(2)) {
            (Some(i), _) => Ok(i.valor.clone()),
            (None, Some(d)) => self.eval(d),
            (None, None) => Err(FormulaError::eval(format!("Sin valor vigente de {campo} al {fecha}"))),
        }
    }
}
