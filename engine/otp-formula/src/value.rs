use crate::error::{FormulaError, Result};
use chrono::NaiveDate;
use rust_decimal::Decimal;
use std::str::FromStr;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Num(Decimal),
    Bool(bool),
    Text(String),
    Date(NaiveDate),
}

pub fn parse_decimal(s: &str) -> Result<Decimal> {
    let t = s.trim();
    Decimal::from_str(t)
        .or_else(|_| Decimal::from_scientific(t))
        .map_err(|_| FormulaError::eval(format!("Número inválido: '{s}'")))
}

pub fn parse_date(s: &str) -> Result<NaiveDate> {
    NaiveDate::parse_from_str(s.trim(), "%Y-%m-%d")
        .map_err(|_| FormulaError::eval(format!("Fecha inválida (se espera AAAA-MM-DD): '{s}'")))
}

impl Value {
    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Num(_) => "número",
            Value::Bool(_) => "booleano",
            Value::Text(_) => "texto",
            Value::Date(_) => "fecha",
        }
    }

    pub fn num(&self) -> Result<Decimal> {
        match self {
            Value::Num(n) => Ok(*n),
            o => Err(FormulaError::eval(format!("Se esperaba un número y se obtuvo {}", o.type_name()))),
        }
    }

    pub fn boolean(&self) -> Result<bool> {
        match self {
            Value::Bool(b) => Ok(*b),
            o => Err(FormulaError::eval(format!("Se esperaba un booleano y se obtuvo {}", o.type_name()))),
        }
    }

    pub fn text(&self) -> Result<&str> {
        match self {
            Value::Text(s) => Ok(s),
            o => Err(FormulaError::eval(format!("Se esperaba un texto y se obtuvo {}", o.type_name()))),
        }
    }

    pub fn date(&self) -> Result<NaiveDate> {
        match self {
            Value::Date(d) => Ok(*d),
            o => Err(FormulaError::eval(format!("Se esperaba una fecha y se obtuvo {}", o.type_name()))),
        }
    }

    /// JSON -> Value. Número, booleano y string (texto) directos; `{"decimal": "1.5"}` y `{"date": "2025-01-31"}` para tipar explícitamente.
    pub fn from_json(v: &serde_json::Value) -> Result<Value> {
        use serde_json::Value as J;
        match v {
            J::Number(n) => Ok(Value::Num(parse_decimal(&n.to_string())?)),
            J::Bool(b) => Ok(Value::Bool(*b)),
            J::String(s) => Ok(Value::Text(s.clone())),
            J::Object(o) => {
                if let Some(J::String(s)) = o.get("decimal") {
                    Ok(Value::Num(parse_decimal(s)?))
                } else if let Some(J::String(s)) = o.get("date") {
                    Ok(Value::Date(parse_date(s)?))
                } else if let Some(J::Number(n)) = o.get("decimal") {
                    Ok(Value::Num(parse_decimal(&n.to_string())?))
                } else {
                    Err(FormulaError::eval("Valor JSON inválido: se esperaba {\"decimal\": ..} o {\"date\": ..}"))
                }
            }
            other => Err(FormulaError::eval(format!("Valor JSON no soportado: {other}"))),
        }
    }

    /// Conversión según el tipo declarado de una columna de tabla.
    pub fn from_json_typed(v: &serde_json::Value, tipo: &str) -> Result<Value> {
        use serde_json::Value as J;
        match (tipo, v) {
            ("int" | "decimal", J::String(s)) => Ok(Value::Num(parse_decimal(s)?)),
            ("date", J::String(s)) => Ok(Value::Date(parse_date(s)?)),
            ("bool", J::String(s)) => Ok(Value::Bool(matches!(s.to_lowercase().as_str(), "true" | "1" | "si" | "sí"))),
            ("text", J::Number(n)) => Ok(Value::Text(n.to_string())),
            _ => Value::from_json(v),
        }
    }
}
