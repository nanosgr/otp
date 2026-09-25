use crate::analysis::{collect, Refs, BUILTIN_VARS};
use crate::ast::Expr;
use crate::context::Contexto;
use crate::error::{FormulaError, Result};
use crate::eval::{round_half_up, Env};
use crate::functions::overflow;
use crate::lexer::lex;
use crate::macros::{FormulaAuxiliar, MacroTable};
use crate::model::{Columna, ConceptoDef, ConceptoRes, ErrorDetalle};
use crate::parser::parse_tokens;
use crate::value::Value;
use rust_decimal::Decimal;
use serde_json::{json, Value as J};
use std::collections::{BTreeMap, BTreeSet, HashMap};

// ---------------------------------------------------------------- reglas

#[derive(Debug, Clone, Default)]
pub struct Reglas {
    pub conceptos: Vec<ConceptoDef>,
    pub auxiliares: Vec<FormulaAuxiliar>,
    pub grupos: HashMap<String, Vec<String>>,
}

fn opt_str(o: &serde_json::Map<String, J>, k: &str) -> Option<String> {
    o.get(k).and_then(J::as_str).map(str::to_string).filter(|s| !s.trim().is_empty())
}

impl Reglas {
    pub fn from_json(v: &J) -> Result<Reglas> {
        let o = v.as_object().ok_or_else(|| FormulaError::eval("Las reglas deben ser un objeto JSON"))?;
        let mut conceptos = Vec::new();
        let mut seen = BTreeSet::new();
        for c in o.get("conceptos").and_then(J::as_array).map(Vec::as_slice).unwrap_or(&[]) {
            let co = c.as_object().ok_or_else(|| FormulaError::eval("Cada concepto debe ser un objeto"))?;
            let codigo = co.get("codigo").and_then(|x| x.as_str().map(str::to_string).or_else(|| x.as_i64().map(|n| n.to_string())))
                .ok_or_else(|| FormulaError::eval("Concepto sin 'codigo'"))?
                .to_uppercase();
            if !seen.insert(codigo.clone()) {
                return Err(FormulaError::eval(format!("Código de concepto duplicado: {codigo}")));
            }
            let columna = opt_str(co, "columna").as_deref().map(|s| Columna::parse(s).ok_or_else(|| FormulaError::eval(format!("Concepto {codigo}: columna inválida '{s}'")))).transpose()?.unwrap_or(Columna::Remunerativo);
            conceptos.push(ConceptoDef {
                descripcion: opt_str(co, "descripcion").unwrap_or_default(),
                columna,
                formula_unidad: opt_str(co, "formula_unidad"),
                formula_importe: opt_str(co, "formula_importe"),
                formula_unitario: opt_str(co, "formula_unitario"),
                formula_condicion: opt_str(co, "formula_condicion"),
                decimales_unidad: co.get("decimales_unidad").and_then(J::as_u64).unwrap_or(4) as u32,
                decimales_importe: co.get("decimales_importe").and_then(J::as_u64).unwrap_or(2) as u32,
                orden: co.get("orden").and_then(J::as_i64).unwrap_or(0) as i32,
                codigo,
            });
        }
        let mut auxiliares = Vec::new();
        for a in o.get("auxiliares").and_then(J::as_array).map(Vec::as_slice).unwrap_or(&[]) {
            let ao = a.as_object().ok_or_else(|| FormulaError::eval("Cada auxiliar debe ser un objeto"))?;
            auxiliares.push(FormulaAuxiliar {
                codigo: opt_str(ao, "codigo").ok_or_else(|| FormulaError::eval("Fórmula auxiliar sin 'codigo'"))?,
                formato: opt_str(ao, "formato"),
                formula: opt_str(ao, "formula").ok_or_else(|| FormulaError::eval("Fórmula auxiliar sin 'formula'"))?,
            });
        }
        let mut grupos = HashMap::new();
        if let Some(g) = o.get("grupos").and_then(J::as_object) {
            for (name, members) in g {
                let list = members.as_array().map(Vec::as_slice).unwrap_or(&[]).iter()
                    .filter_map(|m| m.as_str().map(str::to_string).or_else(|| m.as_i64().map(|n| n.to_string())))
                    .map(|s| s.to_uppercase()).collect();
                grupos.insert(name.to_uppercase(), list);
            }
        }
        Ok(Reglas { conceptos, auxiliares, grupos })
    }
}

// ------------------------------------------------------------ compilación

const FIELDS: [&str; 4] = ["formula_unidad", "formula_unitario", "formula_importe", "formula_condicion"];

#[derive(Default)]
struct Compiled {
    unidad: Option<Expr>,
    unitario: Option<Expr>,
    importe: Option<Expr>,
    condicion: Option<Expr>,
    refs: Refs,
    errors: Vec<(&'static str, FormulaError)>,
}

fn compile_field(src: &Option<String>, field: &'static str, macros: &MacroTable, refs: &mut Refs, errors: &mut Vec<(&'static str, FormulaError)>) -> Option<Expr> {
    let src = src.as_deref()?;
    let mut errs = Vec::new();
    let expr = lex(src).and_then(|t| macros.expand(t)).and_then(parse_tokens);
    match expr {
        Ok(e) => {
            collect(&e, refs, &mut errs);
            errors.extend(errs.into_iter().map(|x| (field, x)));
            Some(e)
        }
        Err(e) => {
            errors.push((field, e));
            None
        }
    }
}

fn compile(def: &ConceptoDef, macros: &MacroTable) -> Compiled {
    let mut c = Compiled::default();
    let mut refs = Refs::default();
    let mut errors = Vec::new();
    c.unidad = compile_field(&def.formula_unidad, FIELDS[0], macros, &mut refs, &mut errors);
    c.unitario = compile_field(&def.formula_unitario, FIELDS[1], macros, &mut refs, &mut errors);
    c.importe = compile_field(&def.formula_importe, FIELDS[2], macros, &mut refs, &mut errors);
    c.condicion = compile_field(&def.formula_condicion, FIELDS[3], macros, &mut refs, &mut errors);
    c.refs = refs;
    c.errors = errors;
    c
}

fn selector_members(name: &str, reglas_defs: &BTreeMap<String, &ConceptoDef>, grupos: &HashMap<String, Vec<String>>) -> Option<Vec<String>> {
    if let Some(col) = Columna::parse(name) {
        Some(reglas_defs.values().filter(|d| d.columna == col).map(|d| d.codigo.clone()).collect())
    } else {
        grupos.get(&name.to_uppercase()).map(|m| m.iter().filter(|c| reglas_defs.contains_key(*c)).cloned().collect())
    }
}

type Deps = BTreeMap<String, BTreeSet<String>>;

/// Dependencias de cada concepto (a qué conceptos necesita), más errores de selectores desconocidos.
fn build_deps(defs: &BTreeMap<String, &ConceptoDef>, compiled: &BTreeMap<String, Compiled>, grupos: &HashMap<String, Vec<String>>) -> (Deps, BTreeMap<String, Vec<String>>) {
    let mut deps = Deps::new();
    let mut sel_errors: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (code, c) in compiled {
        let mut d = BTreeSet::new();
        for r in &c.refs.concepts {
            if defs.contains_key(r) {
                d.insert(r.clone());
            }
        }
        for s in &c.refs.selectors {
            match selector_members(&s.name, defs, grupos) {
                Some(members) => {
                    for m in members {
                        if m != *code && !s.excluded.contains(&m) {
                            d.insert(m);
                        }
                    }
                }
                None => sel_errors.entry(code.clone()).or_default().push(format!("Selector desconocido (columna o grupo): {}", s.name)),
            }
        }
        deps.insert(code.clone(), d);
    }
    (deps, sel_errors)
}

/// Orden topológico determinista (por `orden`, luego código). Devuelve (orden, restantes en ciclo o dependientes de uno).
fn toposort(defs: &BTreeMap<String, &ConceptoDef>, deps: &Deps) -> (Vec<String>, BTreeSet<String>) {
    let mut indeg: BTreeMap<&String, usize> = deps.iter().map(|(k, v)| (k, v.len())).collect();
    let mut users: BTreeMap<&String, Vec<&String>> = BTreeMap::new();
    for (k, v) in deps {
        for d in v {
            users.entry(d).or_default().push(k);
        }
    }
    let key = |c: &String| (defs[c].orden, c.clone());
    let mut ready: BTreeSet<(i32, String)> = indeg.iter().filter(|(_, n)| **n == 0).map(|(k, _)| key(k)).collect();
    let mut order = Vec::new();
    while let Some(first) = ready.iter().next().cloned() {
        ready.remove(&first);
        let code = first.1;
        for u in users.get(&code).map(Vec::as_slice).unwrap_or(&[]) {
            let n = indeg.get_mut(u).unwrap();
            *n -= 1;
            if *n == 0 {
                ready.insert(key(u));
            }
        }
        order.push(code);
    }
    let done: BTreeSet<&String> = order.iter().collect();
    let remaining = deps.keys().filter(|k| !done.contains(k)).cloned().collect();
    (order, remaining)
}

fn find_cycle(remaining: &BTreeSet<String>, deps: &Deps) -> Vec<String> {
    fn dfs(n: &String, remaining: &BTreeSet<String>, deps: &Deps, stack: &mut Vec<String>, seen: &mut BTreeSet<String>) -> Option<Vec<String>> {
        if let Some(i) = stack.iter().position(|x| x == n) {
            let mut cyc: Vec<String> = stack[i..].to_vec();
            cyc.push(n.clone());
            return Some(cyc);
        }
        if !seen.insert(n.clone()) {
            return None;
        }
        stack.push(n.clone());
        for d in &deps[n] {
            if remaining.contains(d) {
                if let Some(c) = dfs(d, remaining, deps, stack, seen) {
                    return Some(c);
                }
            }
        }
        stack.pop();
        None
    }
    let mut seen = BTreeSet::new();
    for n in remaining {
        if let Some(c) = dfs(n, remaining, deps, &mut Vec::new(), &mut seen) {
            return c;
        }
    }
    Vec::new()
}

// ---------------------------------------------------------------- cálculo

#[derive(Debug, Clone)]
pub struct Totales {
    pub remunerativo: Decimal,
    pub no_remunerativo: Decimal,
    pub descuento: Decimal,
    pub contribucion: Decimal,
    pub bruto: Decimal,
    pub neto: Decimal,
    pub costo_laboral: Decimal,
}

#[derive(Debug, Clone)]
pub struct Resultado {
    pub conceptos: Vec<ConceptoRes>,
    pub orden_evaluacion: Vec<String>,
    pub totales: Totales,
}

fn failed(def: &ConceptoDef, msg: String, detalle: Option<ErrorDetalle>) -> ConceptoRes {
    ConceptoRes {
        codigo: def.codigo.clone(), descripcion: def.descripcion.clone(), columna: def.columna, orden: def.orden,
        unidad: None, unitario: None, importe: Decimal::ZERO, decimales_importe: def.decimales_importe, condicion: true,
        error: Some(msg), error_detalle: detalle,
    }
}

/// Fragmento de la fórmula alrededor de `pos` (en caracteres), con `▶` marcando el punto del error.
fn fragmento(src: &str, pos: usize) -> String {
    const ANCHO: usize = 15;
    let chars: Vec<char> = src.chars().collect();
    let pos = pos.min(chars.len());
    let desde = pos.saturating_sub(ANCHO);
    let hasta = (pos + ANCHO).min(chars.len());
    format!(
        "{}{}▶{}{}",
        if desde > 0 { "…" } else { "" },
        chars[desde..pos].iter().collect::<String>(),
        chars[pos..hasta].iter().collect::<String>(),
        if hasta < chars.len() { "…" } else { "" },
    )
}

fn formula_de<'d>(def: &'d ConceptoDef, campo: &str) -> Option<&'d str> {
    match campo {
        "formula_unidad" => def.formula_unidad.as_deref(),
        "formula_unitario" => def.formula_unitario.as_deref(),
        "formula_importe" => def.formula_importe.as_deref(),
        "formula_condicion" => def.formula_condicion.as_deref(),
        _ => None,
    }
}

/// Error de evaluación de un campo del concepto → mensaje (con ubicación si la hay) y detalle.
fn fallo_eval(def: &ConceptoDef, campo: &'static str, e: FormulaError) -> ConceptoRes {
    let msg = match (e.pos(), formula_de(def, campo)) {
        (Some(p), Some(src)) => format!("{campo}, posición {p} («{}»): {e}", fragmento(src, p)),
        _ => e.to_string(),
    };
    failed(def, msg, Some(ErrorDetalle { campo: Some(campo), tipo: e.tipo(), pos: e.pos() }))
}

fn eval_concept(def: &ConceptoDef, c: &Compiled, env: &mut Env) -> std::result::Result<ConceptoRes, (&'static str, FormulaError)> {
    let campos = env.ctx.campos.get(&def.codigo).cloned().unwrap_or_default();
    let mut base = HashMap::new();
    base.insert("CAMPO_UNIDAD".to_string(), Value::Num(campos.unidad.unwrap_or_default()));
    base.insert("CAMPO_IMPORTE".to_string(), Value::Num(campos.importe.unwrap_or_default()));
    env.scopes = vec![base];
    let en = |campo: &'static str| move |e: FormulaError| (campo, e);

    let condicion = match &c.condicion {
        Some(e) => env.eval(e).and_then(|v| v.boolean()).map_err(en(FIELDS[3]))?,
        None => true,
    };
    let mut res = ConceptoRes {
        codigo: def.codigo.clone(), descripcion: def.descripcion.clone(), columna: def.columna, orden: def.orden,
        unidad: None, unitario: None, importe: Decimal::ZERO, decimales_importe: def.decimales_importe, condicion,
        error: None, error_detalle: None,
    };
    if !condicion {
        return Ok(res);
    }
    if let Some(e) = &c.unidad {
        let u = round_half_up(env.eval(e).and_then(|v| v.num()).map_err(en(FIELDS[0]))?, def.decimales_unidad);
        env.scopes[0].insert("UNIDAD".to_string(), Value::Num(u));
        res.unidad = Some(u);
    }
    if let Some(e) = &c.unitario {
        let u = round_half_up(env.eval(e).and_then(|v| v.num()).map_err(en(FIELDS[1]))?, 4);
        env.scopes[0].insert("UNITARIO".to_string(), Value::Num(u));
        res.unitario = Some(u);
    }
    let importe = match (&c.importe, res.unidad, res.unitario) {
        (Some(e), _, _) => env.eval(e).and_then(|v| v.num()).map_err(en(FIELDS[2]))?,
        (None, Some(u), Some(p)) => u.checked_mul(p).ok_or_else(overflow).map_err(en(FIELDS[2]))?,
        _ => Decimal::ZERO,
    };
    let mut imp = round_half_up(importe, def.decimales_importe);
    imp.rescale(def.decimales_importe);
    res.importe = imp;
    Ok(res)
}

/// Reglas compiladas una vez (fórmulas parseadas, dependencias y orden de evaluación) para calcular muchas veces.
pub struct Compilado {
    defs: HashMap<String, ConceptoDef>,
    grupos: HashMap<String, Vec<String>>,
    compiled: BTreeMap<String, Compiled>,
    sel_errors: BTreeMap<String, Vec<String>>,
    orden: Vec<String>,
    /// Conceptos en un ciclo o que dependen de uno
    remaining: BTreeSet<String>,
    cycle: Vec<String>,
}

pub fn compilar(reglas: &Reglas) -> Result<Compilado> {
    let macros = MacroTable::new(&reglas.auxiliares)?;
    let defs: BTreeMap<String, &ConceptoDef> = reglas.conceptos.iter().map(|d| (d.codigo.clone(), d)).collect();
    let compiled: BTreeMap<String, Compiled> = reglas.conceptos.iter().map(|d| (d.codigo.clone(), compile(d, &macros))).collect();
    let (deps, sel_errors) = build_deps(&defs, &compiled, &reglas.grupos);
    let (orden, remaining) = toposort(&defs, &deps);
    let cycle = find_cycle(&remaining, &deps);
    Ok(Compilado {
        defs: reglas.conceptos.iter().map(|d| (d.codigo.clone(), d.clone())).collect(),
        grupos: reglas.grupos.clone(),
        compiled, sel_errors, orden, remaining, cycle,
    })
}

pub fn calcular(reglas: &Reglas, ctx: &Contexto) -> Result<Resultado> {
    compilar(reglas)?.calcular(ctx)
}

impl Compilado {
    fn ciclo_texto(&self) -> String {
        self.cycle.iter().map(|c| format!("#{c}")).collect::<Vec<_>>().join(" -> ")
    }

    pub fn calcular(&self, ctx: &Contexto) -> Result<Resultado> {
        let mut results: HashMap<String, ConceptoRes> = HashMap::new();

        for code in &self.orden {
            let def = &self.defs[code];
            let c = &self.compiled[code];
            let res = if let Some((f, e)) = c.errors.first() {
                let msg = c.errors.iter().map(|(f, e)| format!("{f}: {e}")).collect::<Vec<_>>().join("; ");
                failed(def, msg, Some(ErrorDetalle { campo: Some(f), tipo: e.tipo(), pos: e.pos() }))
            } else if let Some(m) = self.sel_errors.get(code) {
                failed(def, m.join("; "), Some(ErrorDetalle { campo: None, tipo: "selector", pos: None }))
            } else {
                let mut env = Env { ctx, defs: &self.defs, grupos: &self.grupos, results: &results, current: code, scopes: Vec::new() };
                match eval_concept(def, c, &mut env) {
                    Ok(r) => r,
                    Err((campo, e)) => fallo_eval(def, campo, e),
                }
            };
            results.insert(code.clone(), res);
        }
        for code in &self.remaining {
            let msg = if self.cycle.contains(code) {
                format!("Dependencia circular: {}", self.ciclo_texto())
            } else {
                "Depende de conceptos con dependencia circular".to_string()
            };
            results.insert(code.clone(), failed(&self.defs[code], msg, Some(ErrorDetalle { campo: None, tipo: "ciclo", pos: None })));
        }

        let mut t = Totales {
            remunerativo: Decimal::ZERO, no_remunerativo: Decimal::ZERO, descuento: Decimal::ZERO,
            contribucion: Decimal::ZERO, bruto: Decimal::ZERO, neto: Decimal::ZERO, costo_laboral: Decimal::ZERO,
        };
        for r in results.values().filter(|r| r.visible()) {
            match r.columna {
                Columna::Remunerativo => t.remunerativo += r.importe,
                Columna::NoRemunerativo => t.no_remunerativo += r.importe,
                Columna::Descuento => t.descuento += r.importe,
                Columna::Contribucion => t.contribucion += r.importe,
                Columna::Auxiliar => {}
            }
        }
        t.bruto = t.remunerativo + t.no_remunerativo;
        t.neto = t.bruto - t.descuento;
        t.costo_laboral = t.bruto + t.contribucion;

        let mut conceptos: Vec<ConceptoRes> = results.into_values().collect();
        conceptos.sort_by(|a, b| (a.orden, &a.codigo).cmp(&(b.orden, &b.codigo)));
        Ok(Resultado { conceptos, orden_evaluacion: self.orden.clone(), totales: t })
    }
}

fn fixed(d: Decimal, dp: u32) -> String {
    let mut x = round_half_up(d, dp);
    x.rescale(dp);
    x.to_string()
}

impl Resultado {
    pub fn to_json(&self) -> J {
        let conceptos: Vec<J> = self.conceptos.iter().map(|c| json!({
            "codigo": c.codigo,
            "descripcion": c.descripcion,
            "columna": c.columna.name(),
            "orden": c.orden,
            "unidad": c.unidad.map(|u| u.normalize().to_string()),
            "unitario": c.unitario.map(|u| u.normalize().to_string()),
            "importe": fixed(c.importe, c.decimales_importe),
            "condicion": c.condicion,
            "error": c.error.is_some(),
            "message": c.error,
            "error_detalle": c.error_detalle.as_ref().map(|d| json!({"campo": d.campo, "tipo": d.tipo, "pos": d.pos})),
        })).collect();
        let t = &self.totales;
        json!({
            "conceptos": conceptos,
            "orden_evaluacion": self.orden_evaluacion,
            "totales": {
                "remunerativo": t.remunerativo.to_string(),
                "no_remunerativo": t.no_remunerativo.to_string(),
                "descuento": t.descuento.to_string(),
                "contribucion": t.contribucion.to_string(),
                "bruto": t.bruto.to_string(),
                "neto": t.neto.to_string(),
                "costo_laboral": t.costo_laboral.to_string(),
            }
        })
    }
}

// ------------------------------------------------------------- validación

#[derive(Debug, Clone)]
pub struct Problema {
    pub codigo: String,
    pub campo: String,
    pub nivel: &'static str,
    pub mensaje: String,
}

/// Validación estática de todas las reglas: sintaxis, aridad, selectores, ciclos y referencias.
pub fn validar_reglas(reglas: &Reglas, variables_conocidas: Option<&BTreeSet<String>>) -> Result<Vec<Problema>> {
    let comp = compilar(reglas)?;
    let mut out = Vec::new();
    for (code, c) in &comp.compiled {
        for (f, e) in &c.errors {
            out.push(Problema { codigo: code.clone(), campo: f.to_string(), nivel: "error", mensaje: e.to_string() });
        }
        for r in &c.refs.concepts {
            if !comp.defs.contains_key(r) {
                out.push(Problema { codigo: code.clone(), campo: String::new(), nivel: "warning", mensaje: format!("Referencia al concepto #{r}, que no existe en las reglas (se tratará como 0 si no está asignado)") });
            }
        }
        if let Some(known) = variables_conocidas {
            for v in &c.refs.vars {
                if !BUILTIN_VARS.contains(&v.as_str()) && !v.starts_with("COL") && !known.contains(v) {
                    out.push(Problema { codigo: code.clone(), campo: String::new(), nivel: "warning", mensaje: format!("Variable desconocida: {v}") });
                }
            }
        }
    }
    for (code, msgs) in &comp.sel_errors {
        for m in msgs {
            out.push(Problema { codigo: code.clone(), campo: String::new(), nivel: "error", mensaje: m.clone() });
        }
    }
    for code in comp.cycle.iter().collect::<BTreeSet<_>>() {
        out.push(Problema {
            codigo: code.clone(), campo: String::new(), nivel: "error",
            mensaje: format!("Dependencia circular: {}", comp.ciclo_texto()),
        });
    }
    Ok(out)
}

impl Problema {
    pub fn to_json(&self) -> J {
        json!({"codigo": self.codigo, "campo": self.campo, "nivel": self.nivel, "mensaje": self.mensaje})
    }
}

/// Valida una fórmula suelta (p. ej. al editar un concepto) y devuelve lo que referencia.
pub fn validar_formula(src: &str, auxiliares: &[FormulaAuxiliar]) -> Result<J> {
    let macros = MacroTable::new(auxiliares)?;
    let toks = macros.expand(lex(src)?)?;
    let expr = parse_tokens(toks)?;
    let mut refs = Refs::default();
    let mut errors = Vec::new();
    collect(&expr, &mut refs, &mut errors);
    if let Some(e) = errors.into_iter().next() {
        return Err(e);
    }
    Ok(json!({
        "conceptos": refs.concepts,
        "selectores": refs.selectors.iter().map(|s| s.name.clone()).collect::<Vec<_>>(),
        "variables": refs.vars,
        "tablas": refs.tablas,
        "historial": refs.historial,
    }))
}
