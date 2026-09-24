use crate::error::{FormulaError, Result};
use crate::value::{parse_date, parse_decimal, Value};
use chrono::NaiveDate;
use rust_decimal::Decimal;
use serde_json::Value as J;
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct Tabla {
    pub columnas: Vec<String>,
    pub filas: Vec<Vec<Value>>,
}

#[derive(Debug, Clone)]
pub struct HistItem {
    pub desde: Option<NaiveDate>,
    pub hasta: Option<NaiveDate>,
    pub valor: Value,
}

#[derive(Debug, Clone, Default)]
pub struct Campos {
    pub unidad: Option<Decimal>,
    pub importe: Option<Decimal>,
}

#[derive(Debug, Clone)]
pub struct Contexto {
    pub fecha: NaiveDate,
    pub variables: HashMap<String, Value>,
    pub tablas: HashMap<String, Tabla>,
    pub historial: HashMap<String, Vec<HistItem>>,
    pub beneficiarios: Vec<HashMap<String, Value>>,
    pub campos: HashMap<String, Campos>,
}

fn obj<'a>(v: &'a J, what: &str) -> Result<&'a serde_json::Map<String, J>> {
    v.as_object().ok_or_else(|| FormulaError::eval(format!("'{what}' debe ser un objeto JSON")))
}

fn opt_date(v: Option<&J>) -> Result<Option<NaiveDate>> {
    match v {
        None | Some(J::Null) => Ok(None),
        Some(J::String(s)) if s.is_empty() => Ok(None),
        Some(J::String(s)) => Ok(Some(parse_date(s)?)),
        Some(o @ J::Object(_)) => Ok(Some(Value::from_json(o)?.date()?)),
        Some(_) => Err(FormulaError::eval("Fecha inválida en el contexto")),
    }
}

fn opt_dec(v: Option<&J>) -> Result<Option<Decimal>> {
    match v {
        None | Some(J::Null) => Ok(None),
        Some(J::String(s)) => Ok(Some(parse_decimal(s)?)),
        Some(J::Number(n)) => Ok(Some(parse_decimal(&n.to_string())?)),
        Some(o @ J::Object(_)) => Ok(Some(Value::from_json(o)?.num()?)),
        Some(_) => Err(FormulaError::eval("Número inválido en el contexto")),
    }
}

fn value_map(v: &J, what: &str) -> Result<HashMap<String, Value>> {
    let mut out = HashMap::new();
    for (k, x) in obj(v, what)? {
        out.insert(k.to_uppercase(), Value::from_json(x).map_err(|e| FormulaError::eval(format!("{what}.{k}: {e}")))?);
    }
    Ok(out)
}

impl Contexto {
    pub fn from_json(v: &J) -> Result<Contexto> {
        let o = obj(v, "contexto")?;
        let fecha = opt_date(o.get("fecha"))?.ok_or_else(|| FormulaError::eval("El contexto requiere 'fecha' (AAAA-MM-DD)"))?;
        let variables = match o.get("variables") {
            Some(x) => value_map(x, "variables")?,
            None => HashMap::new(),
        };

        let mut tablas = HashMap::new();
        if let Some(t) = o.get("tablas") {
            for (code, def) in obj(t, "tablas")? {
                let d = obj(def, "tabla")?;
                let cols = d.get("columnas").and_then(J::as_array).ok_or_else(|| FormulaError::eval(format!("Tabla {code}: falta 'columnas'")))?;
                let mut nombres = Vec::new();
                let mut tipos = Vec::new();
                for c in cols {
                    let co = obj(c, "columna")?;
                    nombres.push(co.get("nombre").and_then(J::as_str).unwrap_or("").to_uppercase());
                    tipos.push(co.get("tipo").and_then(J::as_str).unwrap_or("text").to_lowercase());
                }
                let mut filas = Vec::new();
                for f in d.get("filas").and_then(J::as_array).map(Vec::as_slice).unwrap_or(&[]) {
                    let cells = f.as_array().ok_or_else(|| FormulaError::eval(format!("Tabla {code}: cada fila debe ser una lista")))?;
                    if cells.len() != nombres.len() {
                        return Err(FormulaError::eval(format!("Tabla {code}: una fila tiene {} valores y hay {} columnas", cells.len(), nombres.len())));
                    }
                    let mut row = Vec::new();
                    for (c, t) in cells.iter().zip(&tipos) {
                        row.push(Value::from_json_typed(c, t).map_err(|e| FormulaError::eval(format!("Tabla {code}: {e}")))?);
                    }
                    filas.push(row);
                }
                tablas.insert(code.to_uppercase(), Tabla { columnas: nombres, filas });
            }
        }

        let mut historial = HashMap::new();
        if let Some(h) = o.get("historial") {
            for (campo, items) in obj(h, "historial")? {
                let mut list = Vec::new();
                for it in items.as_array().map(Vec::as_slice).unwrap_or(&[]) {
                    let io = obj(it, "historial item")?;
                    list.push(HistItem {
                        desde: opt_date(io.get("desde"))?,
                        hasta: opt_date(io.get("hasta"))?,
                        valor: Value::from_json(io.get("valor").ok_or_else(|| FormulaError::eval(format!("historial.{campo}: falta 'valor'")))?)?,
                    });
                }
                historial.insert(campo.to_uppercase(), list);
            }
        }

        let mut beneficiarios = Vec::new();
        if let Some(b) = o.get("beneficiarios") {
            for x in b.as_array().map(Vec::as_slice).unwrap_or(&[]) {
                beneficiarios.push(value_map(x, "beneficiario")?);
            }
        }

        let mut campos = HashMap::new();
        if let Some(c) = o.get("campos") {
            for (code, x) in obj(c, "campos")? {
                let co = obj(x, "campo")?;
                campos.insert(code.to_uppercase(), Campos { unidad: opt_dec(co.get("unidad"))?, importe: opt_dec(co.get("importe"))? });
            }
        }

        Ok(Contexto { fecha, variables, tablas, historial, beneficiarios, campos })
    }
}
