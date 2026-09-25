//! Registro de funciones del lenguaje: nombre, alias, aridad e implementación.
//!
//! Para agregar una función pura basta una entrada en `FUNCIONES` (y un test). Las funciones `Especial` evalúan
//! solo algunos argumentos o necesitan el contexto (conceptos, tablas, historial); las resuelve `eval.rs`.
use crate::error::{FormulaError, Result, TipoError};
use crate::value::{parse_date, Value};
use chrono::{Datelike, NaiveDate};
use rust_decimal::{Decimal, MathematicalOps, RoundingStrategy};

pub enum Impl {
    /// Recibe los argumentos ya evaluados.
    Pura(fn(&[Value]) -> Result<Value>),
    Especial,
}

pub struct FuncDef {
    pub nombre: &'static str,
    pub alias: &'static [&'static str],
    pub min: usize,
    pub max: usize,
    pub imp: Impl,
}

const N: usize = usize::MAX;

macro_rules! f {
    ($nombre:literal, [$($alias:literal),*], $min:expr, $max:expr, $imp:expr) => {
        FuncDef { nombre: $nombre, alias: &[$($alias),*], min: $min, max: $max, imp: $imp }
    };
}

pub static FUNCIONES: &[FuncDef] = &[
    // formas especiales (eval.rs)
    f!("IF", ["SI"], 3, 3, Impl::Especial),
    f!("TABLA", [], 3, 4, Impl::Especial),
    f!("HISTORIAL", [], 1, 3, Impl::Especial),
    f!("EXISTE_HISTORIAL", [], 1, 2, Impl::Especial),
    f!("EXISTE", [], 1, 1, Impl::Especial),
    f!("UNIDAD_CONCEPTO", [], 1, 1, Impl::Especial),
    f!("UNITARIO_CONCEPTO", [], 1, 1, Impl::Especial),
    f!("IMPORTE_CONCEPTO", [], 1, 1, Impl::Especial),
    f!("TOTAL", [], 1, N, Impl::Especial),
    f!("CONCEPTOS", [], 3, 3, Impl::Especial),
    f!("BENEFICIARIOS", [], 3, 3, Impl::Especial),
    // numéricas
    f!("ROUND", ["REDONDEAR"], 1, 2, Impl::Pura(round)),
    f!("TRUNC", [], 1, 2, Impl::Pura(trunc)),
    f!("CEIL", ["REDONDEAR_ARRIBA"], 1, 2, Impl::Pura(ceil)),
    f!("FLOOR", ["REDONDEAR_ABAJO"], 1, 2, Impl::Pura(floor)),
    f!("MIN", [], 1, N, Impl::Pura(min)),
    f!("MAX", [], 1, N, Impl::Pura(max)),
    f!("SUMA", ["SUM"], 1, N, Impl::Pura(suma)),
    f!("PROMEDIO", ["AVERAGE"], 1, N, Impl::Pura(promedio)),
    f!("ABS", [], 1, 1, Impl::Pura(abs)),
    f!("SIGNO", ["SIGN"], 1, 1, Impl::Pura(signo)),
    f!("MOD", ["RESTO"], 2, 2, Impl::Pura(modulo)),
    f!("POTENCIA", ["POW"], 2, 2, Impl::Pura(potencia_fn)),
    f!("RAIZ", ["SQRT"], 1, 1, Impl::Pura(raiz)),
    f!("EXP", [], 1, 1, Impl::Pura(exp)),
    f!("LN", [], 1, 1, Impl::Pura(ln)),
    f!("LOG10", [], 1, 1, Impl::Pura(log10)),
    // fechas
    f!("FECHA", [], 1, 1, Impl::Pura(fecha)),
    f!("ANIOS", [], 2, 2, Impl::Pura(anios)),
    f!("MESES", [], 2, 2, Impl::Pura(meses)),
    f!("DIAS", [], 2, 2, Impl::Pura(dias)),
    f!("ANIO", [], 1, 1, Impl::Pura(anio)),
    f!("MES", [], 1, 1, Impl::Pura(mes)),
    f!("DIA", [], 1, 1, Impl::Pura(dia)),
];

/// Busca una función por nombre o alias (los nombres ya vienen en mayúsculas del lexer).
pub fn buscar(nombre: &str) -> Option<&'static FuncDef> {
    FUNCIONES.iter().find(|f| f.nombre == nombre || f.alias.contains(&nombre))
}

// ---------------------------------------------------------------- helpers

pub fn overflow() -> FormulaError {
    FormulaError::of(TipoError::Desbordamiento, "Desbordamiento numérico")
}

pub fn division_por_cero() -> FormulaError {
    FormulaError::of(TipoError::DivisionPorCero, "División por cero")
}

fn nums(args: &[Value]) -> Result<Vec<Decimal>> {
    args.iter().map(Value::num).collect()
}

fn num(v: Decimal) -> Result<Value> {
    Ok(Value::Num(v))
}

/// Cantidad de decimales del segundo argumento opcional (0 si no está).
fn decimales(args: &[Value]) -> Result<u32> {
    let dp = match args.get(1) {
        Some(v) => v.num()?.trunc().to_string().parse::<i64>().unwrap_or(-1),
        None => 0,
    };
    if !(0..=28).contains(&dp) {
        return Err(FormulaError::eval("La cantidad de decimales debe estar entre 0 y 28"));
    }
    Ok(dp as u32)
}

fn redondeo(args: &[Value], estrategia: RoundingStrategy) -> Result<Value> {
    let dp = decimales(args)?;
    num(args[0].num()?.round_dp_with_strategy(dp, estrategia))
}

/// Resultado de una función matemática que puede no estar definida o desbordar.
fn definido(r: Option<Decimal>, que: &str) -> Result<Value> {
    r.map(Value::Num).ok_or_else(|| FormulaError::eval(format!("{que}: resultado no definido o fuera de rango")))
}

// ---------------------------------------------------------------- numéricas

fn round(a: &[Value]) -> Result<Value> {
    redondeo(a, RoundingStrategy::MidpointAwayFromZero)
}

fn trunc(a: &[Value]) -> Result<Value> {
    redondeo(a, RoundingStrategy::ToZero)
}

fn ceil(a: &[Value]) -> Result<Value> {
    redondeo(a, RoundingStrategy::ToPositiveInfinity)
}

fn floor(a: &[Value]) -> Result<Value> {
    redondeo(a, RoundingStrategy::ToNegativeInfinity)
}

fn min(a: &[Value]) -> Result<Value> {
    num(nums(a)?.into_iter().min().expect("aridad validada"))
}

fn max(a: &[Value]) -> Result<Value> {
    num(nums(a)?.into_iter().max().expect("aridad validada"))
}

fn sumar(v: &[Decimal]) -> Result<Decimal> {
    v.iter().try_fold(Decimal::ZERO, |acc, x| acc.checked_add(*x)).ok_or_else(overflow)
}

fn suma(a: &[Value]) -> Result<Value> {
    num(sumar(&nums(a)?)?)
}

fn promedio(a: &[Value]) -> Result<Value> {
    let v = nums(a)?;
    num(sumar(&v)?.checked_div(Decimal::from(v.len())).ok_or_else(overflow)?)
}

fn abs(a: &[Value]) -> Result<Value> {
    num(a[0].num()?.abs())
}

fn signo(a: &[Value]) -> Result<Value> {
    let x = a[0].num()?;
    num(if x.is_zero() { Decimal::ZERO } else if x.is_sign_negative() { Decimal::NEGATIVE_ONE } else { Decimal::ONE })
}

fn modulo(a: &[Value]) -> Result<Value> {
    let (x, y) = (a[0].num()?, a[1].num()?);
    if y.is_zero() {
        return Err(division_por_cero());
    }
    num(x.checked_rem(y).ok_or_else(overflow)?)
}

/// `base ^ exp`: exacto con exponente entero; con exponente decimal, aproximación de `rust_decimal` (sin f64).
pub fn potencia(base: Decimal, exp: Decimal) -> Result<Decimal> {
    let e = exp.normalize();
    if e.scale() == 0 {
        let n = e.to_string().parse::<i64>().map_err(|_| overflow())?;
        if base.is_zero() && n < 0 {
            return Err(division_por_cero());
        }
        return base.checked_powi(n).ok_or_else(overflow);
    }
    if base.is_sign_negative() && !base.is_zero() {
        return Err(FormulaError::eval("Potencia de base negativa con exponente decimal: resultado no real"));
    }
    if base.is_zero() {
        return if exp.is_sign_positive() { Ok(Decimal::ZERO) } else { Err(division_por_cero()) };
    }
    base.checked_powd(exp).ok_or_else(overflow)
}

fn potencia_fn(a: &[Value]) -> Result<Value> {
    num(potencia(a[0].num()?, a[1].num()?)?)
}

fn raiz(a: &[Value]) -> Result<Value> {
    let x = a[0].num()?;
    if x.is_sign_negative() && !x.is_zero() {
        return Err(FormulaError::eval("RAIZ de un número negativo"));
    }
    definido(x.sqrt(), "RAIZ")
}

fn exp(a: &[Value]) -> Result<Value> {
    definido(a[0].num()?.checked_exp(), "EXP")
}

fn ln(a: &[Value]) -> Result<Value> {
    definido(a[0].num()?.checked_ln(), "LN")
}

fn log10(a: &[Value]) -> Result<Value> {
    definido(a[0].num()?.checked_log10(), "LOG10")
}

// ---------------------------------------------------------------- fechas

fn fecha(a: &[Value]) -> Result<Value> {
    match &a[0] {
        Value::Date(d) => Ok(Value::Date(*d)),
        Value::Text(s) => Ok(Value::Date(parse_date(s)?)),
        o => Err(FormulaError::of(TipoError::Tipo, format!("FECHA no acepta {}", o.type_name()))),
    }
}

fn fechas(a: &[Value]) -> Result<(NaiveDate, NaiveDate)> {
    Ok((a[0].date()?, a[1].date()?))
}

/// Años cumplidos entre dos fechas.
fn anios(a: &[Value]) -> Result<Value> {
    let (d1, d2) = fechas(a)?;
    let mut y = d2.year() - d1.year();
    if (d2.month(), d2.day()) < (d1.month(), d1.day()) {
        y -= 1;
    }
    num(Decimal::from(y))
}

fn meses(a: &[Value]) -> Result<Value> {
    let (d1, d2) = fechas(a)?;
    let mut m = (d2.year() - d1.year()) * 12 + d2.month() as i32 - d1.month() as i32;
    if d2.day() < d1.day() {
        m -= 1;
    }
    num(Decimal::from(m))
}

fn dias(a: &[Value]) -> Result<Value> {
    let (d1, d2) = fechas(a)?;
    num(Decimal::from((d2 - d1).num_days()))
}

fn anio(a: &[Value]) -> Result<Value> {
    num(Decimal::from(a[0].date()?.year()))
}

fn mes(a: &[Value]) -> Result<Value> {
    num(Decimal::from(a[0].date()?.month()))
}

fn dia(a: &[Value]) -> Result<Value> {
    num(Decimal::from(a[0].date()?.day()))
}
