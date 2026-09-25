use crate::ast::{BinOp, Expr};
use crate::context::Contexto;
use crate::error::{FormulaError, Result, TipoError};
use crate::functions::{buscar, division_por_cero, overflow, potencia, Impl};
use crate::model::{Columna, ConceptoDef, ConceptoRes};
use crate::value::Value;
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

fn cmp_values(a: &Value, b: &Value) -> Result<Ordering> {
    match (a, b) {
        (Value::Num(x), Value::Num(y)) => Ok(x.cmp(y)),
        (Value::Text(x), Value::Text(y)) => Ok(x.cmp(y)),
        (Value::Date(x), Value::Date(y)) => Ok(x.cmp(y)),
        (Value::Bool(x), Value::Bool(y)) => Ok(x.cmp(y)),
        _ => Err(FormulaError::of(TipoError::Tipo, format!("No se puede comparar {} con {}", a.type_name(), b.type_name()))),
    }
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

/// Operador binario sobre valores ya evaluados. Aparte de `Env::binary` para que el frame recursivo sea chico
/// (la evaluación del árbol es recursiva y en debug cada frame grande limita la profundidad).
#[inline(never)]
fn aplicar(op: BinOp, l: Value, r: Value) -> Result<Value> {
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
                return Err(division_por_cero());
            }
            Ok(Value::Num(l.num()?.checked_div(d).ok_or_else(overflow)?))
        }
        BinOp::Pow => Ok(Value::Num(potencia(l.num()?, r.num()?)?)),
        BinOp::Eq => Ok(Value::Bool(cmp_values(&l, &r)? == Ordering::Equal)),
        BinOp::Ne => Ok(Value::Bool(cmp_values(&l, &r)? != Ordering::Equal)),
        BinOp::Lt => Ok(Value::Bool(cmp_values(&l, &r)? == Ordering::Less)),
        BinOp::Le => Ok(Value::Bool(cmp_values(&l, &r)? != Ordering::Greater)),
        BinOp::Gt => Ok(Value::Bool(cmp_values(&l, &r)? == Ordering::Greater)),
        BinOp::Ge => Ok(Value::Bool(cmp_values(&l, &r)? != Ordering::Less)),
        BinOp::And | BinOp::Or => unreachable!(),
    }
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
        Err(FormulaError::of(TipoError::VariableNoDefinida, format!("Variable no definida: {name}")))
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
            Expr::Var { name, pos } => self.lookup(name).map_err(|e| e.con_pos(*pos)),
            Expr::Concept(c) => Ok(Value::Num(match self.result_of(c)? {
                Some(r) if r.visible() => r.importe,
                _ => Decimal::ZERO,
            })),
            Expr::Neg(x) => Ok(Value::Num(-self.eval(x)?.num()?)),
            Expr::Not(x) => Ok(Value::Bool(!self.eval(x)?.boolean()?)),
            Expr::Bin { op, l, r, pos } => self.binary(*op, l, r).map_err(|e| e.con_pos(*pos)),
            Expr::Call { name, args, pos } => self.call(name, args).map_err(|e| e.con_pos(*pos)),
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
        aplicar(op, l, r)
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
        let Some(f) = buscar(name) else {
            return Err(FormulaError::of(TipoError::FuncionDesconocida, format!("Función desconocida: {name}")));
        };
        if args.len() < f.min || args.len() > f.max {
            return Err(FormulaError::eval(format!("{name}: cantidad de argumentos inválida ({})", args.len())));
        }
        if let Impl::Pura(fun) = f.imp {
            let vals = self.eager(args)?;
            return fun(&vals);
        }
        let name = f.nombre;
        match name {
            "IF" => {
                if self.eval(&args[0])?.boolean()? { self.eval(&args[1]) } else { self.eval(&args[2]) }
            }
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
            other => unreachable!("función especial sin implementar: {other}"),
        }
    }

    fn tabla(&mut self, args: &[Expr]) -> Result<Value> {
        let code = self.eval(&args[0])?;
        let code = code.text()?.to_uppercase();
        let ctx = self.ctx;
        let tabla = ctx.tablas.get(&code).ok_or_else(|| FormulaError::of(TipoError::SinDatos, format!("Tabla no definida: {code}")))?;
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
            None => Err(FormulaError::of(TipoError::SinDatos, format!("Valor no encontrado en la tabla {code}"))),
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
            (None, None) => Err(FormulaError::of(TipoError::SinDatos, format!("Sin valor vigente de {campo} al {fecha}"))),
        }
    }
}
