use otp_formula::{calcular_json, validar_formula_json, validar_reglas_json};
use serde_json::{json, Value};

fn run(reglas: Value, ctx: Value) -> Value {
    let out = calcular_json(&reglas.to_string(), &ctx.to_string()).expect("calcular");
    serde_json::from_str(&out).unwrap()
}

fn concepto<'a>(res: &'a Value, code: &str) -> &'a Value {
    res["conceptos"].as_array().unwrap().iter().find(|c| c["codigo"] == code).unwrap_or_else(|| panic!("falta {code}"))
}

fn ctx(vars: Value) -> Value {
    json!({"fecha": "2025-03-01", "variables": vars})
}

fn one(formula: &str) -> Value {
    let r = run(
        json!({"conceptos": [{"codigo": "1", "descripcion": "x", "columna": "REMUNERATIVO", "formula_importe": formula}]}),
        ctx(json!({})),
    );
    concepto(&r, "1").clone()
}

#[test]
fn aritmetica_y_porcentajes() {
    assert_eq!(one("100 + 20 * 2")["importe"], "140.00");
    assert_eq!(one("(100 + 20) * 2")["importe"], "240.00");
    assert_eq!(one("200 * 2%")["importe"], "4.00");
    assert_eq!(one("-5 + 10")["importe"], "5.00");
    assert_eq!(one("10 / 4")["importe"], "2.50");
}

#[test]
fn redondeo_mitad_hacia_arriba_y_funciones() {
    assert_eq!(one("2.345")["importe"], "2.35");
    assert_eq!(one("ROUND(2.5)")["importe"], "3.00");
    assert_eq!(one("ROUND(-2.5)")["importe"], "-3.00");
    assert_eq!(one("TRUNC(2.999, 1)")["importe"], "2.90");
    assert_eq!(one("MAX(1, 7, 3) + MIN(4, 2)")["importe"], "9.00");
    assert_eq!(one("IF(3 > 2 AND NOT (1 = 2), 10, 20)")["importe"], "10.00");
    assert_eq!(one("SI(1 > 2, 10, 20)")["importe"], "20.00");
}

#[test]
fn division_por_cero_es_error_del_concepto() {
    let c = one("1 / 0");
    assert_eq!(c["error"], true);
    assert!(c["message"].as_str().unwrap().contains("cero"));
}

#[test]
fn variables_fechas_y_tipos() {
    let r = run(
        json!({"conceptos": [
            {"codigo": "1", "formula_unidad": "ANIOS(FECHA_INGRESO, FECHA)", "formula_importe": "UNIDAD * 10"},
            {"codigo": "2", "formula_importe": "IF(TIPO = 'superior', 1, 2)"},
            {"codigo": "3", "formula_importe": "MESES(FECHA_INGRESO, FECHA) + DIAS(FECHA_INGRESO, FECHA) * 0"},
        ]}),
        ctx(json!({"FECHA_INGRESO": {"date": "2000-06-15"}, "TIPO": "superior"})),
    );
    assert_eq!(concepto(&r, "1")["unidad"], "24");
    assert_eq!(concepto(&r, "1")["importe"], "240.00");
    assert_eq!(concepto(&r, "2")["importe"], "1.00");
    assert_eq!(concepto(&r, "3")["importe"], "296.00");
}

#[test]
fn variable_no_definida() {
    let c = one("FOO + 1");
    assert_eq!(c["error"], true);
    assert!(c["message"].as_str().unwrap().contains("FOO"));
}

#[test]
fn unidad_por_unitario_y_condicion() {
    let r = run(
        json!({"conceptos": [
            {"codigo": "1", "formula_unidad": "3", "formula_unitario": "12.5"},
            {"codigo": "2", "formula_importe": "1 / 0", "formula_condicion": "FALSE"},
            {"codigo": "3", "formula_importe": "IF(EXISTE(#2), 1, 2) + #2"},
        ]}),
        ctx(json!({})),
    );
    assert_eq!(concepto(&r, "1")["importe"], "37.50");
    // condición falsa: no se evalúa el importe (no hay error), no suma y EXISTE es falso
    assert_eq!(concepto(&r, "2")["error"], false);
    assert_eq!(concepto(&r, "2")["condicion"], false);
    assert_eq!(concepto(&r, "3")["importe"], "2.00");
    assert_eq!(r["totales"]["remunerativo"], "39.50");
}

#[test]
fn orden_topologico_independiente_del_orden_de_carga() {
    let r = run(
        json!({"conceptos": [
            {"codigo": "C", "orden": 1, "formula_importe": "#B * 2"},
            {"codigo": "B", "orden": 2, "formula_importe": "#A + 1"},
            {"codigo": "A", "orden": 3, "formula_importe": "10"},
        ]}),
        ctx(json!({})),
    );
    assert_eq!(r["orden_evaluacion"], json!(["A", "B", "C"]));
    assert_eq!(concepto(&r, "C")["importe"], "22.00");
}

#[test]
fn dependencia_circular_se_reporta_por_concepto() {
    let reglas = json!({"conceptos": [
        {"codigo": "A", "formula_importe": "#B + 1"},
        {"codigo": "B", "formula_importe": "#A + 1"},
        {"codigo": "C", "formula_importe": "#A"},
        {"codigo": "D", "formula_importe": "5"},
    ]});
    let r = run(reglas.clone(), ctx(json!({})));
    assert_eq!(concepto(&r, "A")["error"], true);
    assert!(concepto(&r, "A")["message"].as_str().unwrap().contains("circular"));
    assert_eq!(concepto(&r, "C")["error"], true);
    assert_eq!(concepto(&r, "D")["importe"], "5.00");

    let v: Value = serde_json::from_str(&validar_reglas_json(&reglas.to_string(), None).unwrap()).unwrap();
    let errs: Vec<_> = v.as_array().unwrap().iter().filter(|p| p["nivel"] == "error").collect();
    assert_eq!(errs.len(), 2);
    assert!(errs[0]["mensaje"].as_str().unwrap().contains("#A -> #B -> #A") || errs[0]["mensaje"].as_str().unwrap().contains("#B -> #A -> #B"));
}

#[test]
fn error_de_dependencia_se_propaga() {
    let r = run(
        json!({"conceptos": [
            {"codigo": "A", "formula_importe": "1 / 0"},
            {"codigo": "B", "formula_importe": "#A + 1"},
            {"codigo": "C", "formula_importe": "2"},
        ]}),
        ctx(json!({})),
    );
    assert_eq!(concepto(&r, "B")["error"], true);
    assert!(concepto(&r, "B")["message"].as_str().unwrap().contains("A"));
    assert_eq!(r["totales"]["remunerativo"], "2.00");
}

#[test]
fn macros_con_y_sin_parametros() {
    let r = run(
        json!({
            "auxiliares": [
                {"codigo": "IVA", "formula": "21%"},
                {"codigo": "CON_IVA", "formato": "(x)", "formula": "? * (1 + IVA)"},
                {"codigo": "PROM", "formato": "(a,b)", "formula": "(?0 + ?1) / 2"},
            ],
            "conceptos": [
                {"codigo": "1", "formula_importe": "CON_IVA(100)"},
                {"codigo": "2", "formula_importe": "PROM(CON_IVA(10), 2 * 3)"},
            ]
        }),
        ctx(json!({})),
    );
    assert_eq!(concepto(&r, "1")["importe"], "121.00");
    assert_eq!(concepto(&r, "2")["importe"], "9.05");
}

#[test]
fn macro_recursiva_falla() {
    let r = run(
        json!({"auxiliares": [{"codigo": "LOOP", "formula": "LOOP + 1"}], "conceptos": [{"codigo": "1", "formula_importe": "LOOP"}]}),
        ctx(json!({})),
    );
    assert_eq!(concepto(&r, "1")["error"], true);
    assert!(concepto(&r, "1")["message"].as_str().unwrap().contains("recursividad"));
}

fn ctx_completo() -> Value {
    json!({
        "fecha": "2025-03-01",
        "variables": {"CLASE": 3, "ANIOS_SERVICIO": 27, "ANIOS_ANTIGUEDAD": 20, "TIPO": "superior"},
        "tablas": {
            "ESCALA_CLASE": {
                "columnas": [{"nombre": "CLASE", "tipo": "int"}, {"nombre": "HABER", "tipo": "decimal"}],
                "filas": [[2, "1000.10"], [3, "2000.25"], [4, "3000.00"]]
            },
            "PORC_RETIRO": {
                "columnas": [{"nombre": "ANIOS", "tipo": "int"}, {"nombre": "PORC", "tipo": "decimal"}],
                "filas": [[10, "30"], [20, "70"], [25, "100"]]
            }
        },
        "historial": {
            "PORC_PENSION": [
                {"desde": "2000-01-01", "hasta": "2024-12-31", "valor": {"decimal": "0.70"}},
                {"desde": "2025-01-01", "hasta": null, "valor": {"decimal": "0.75"}}
            ]
        },
        "beneficiarios": [
            {"parentesco": "conyuge", "porcentaje": {"decimal": "50"}, "art37": false},
            {"parentesco": "hijo", "porcentaje": {"decimal": "25"}, "art37": true},
            {"parentesco": "hijo", "porcentaje": {"decimal": "25"}, "art37": false}
        ],
        "campos": {"99": {"importe": "10.5"}}
    })
}

#[test]
fn tabla_historial_y_beneficiarios() {
    let r = run(
        json!({"conceptos": [
            {"codigo": "10", "formula_importe": "TABLA('ESCALA_CLASE', COL.CLASE = CLASE, COL.HABER)"},
            {"codigo": "11", "formula_importe": "TABLA('PORC_RETIRO', COL1 = 99, COL2, -1)"},
            {"codigo": "12", "formula_importe": "HISTORIAL('PORC_PENSION') * 100"},
            {"codigo": "13", "formula_importe": "HISTORIAL('PORC_PENSION', FECHA('2020-06-01')) * 100"},
            {"codigo": "14", "formula_importe": "HISTORIAL('NO_EXISTE', FECHA, 7)"},
            {"codigo": "15", "formula_importe": "BENEFICIARIOS('TODOS', '+', PORCENTAJE)"},
            {"codigo": "16", "formula_importe": "BENEFICIARIOS('hijo', '+', IF(ART37, 1, 0))"},
            {"codigo": "17", "formula_importe": "BENEFICIARIOS('hijo', 'COUNT', TRUE)"},
            {"codigo": "18", "formula_importe": "TABLA('ESCALA_CLASE', COL1 = 99, COL2)"},
            {"codigo": "99", "formula_importe": "CAMPO_IMPORTE"},
        ]}),
        ctx_completo(),
    );
    assert_eq!(concepto(&r, "10")["importe"], "2000.25");
    assert_eq!(concepto(&r, "11")["importe"], "-1.00");
    assert_eq!(concepto(&r, "12")["importe"], "75.00");
    assert_eq!(concepto(&r, "13")["importe"], "70.00");
    assert_eq!(concepto(&r, "14")["importe"], "7.00");
    assert_eq!(concepto(&r, "15")["importe"], "100.00");
    assert_eq!(concepto(&r, "16")["importe"], "1.00");
    assert_eq!(concepto(&r, "17")["importe"], "2.00");
    assert_eq!(concepto(&r, "18")["error"], true);
    assert!(concepto(&r, "18")["message"].as_str().unwrap().contains("no encontrado"));
    assert_eq!(concepto(&r, "99")["importe"], "10.50");
}

#[test]
fn total_conceptos_y_grupos() {
    let r = run(
        json!({
            "grupos": {"BONIF": ["10", "20", "30"]},
            "conceptos": [
                {"codigo": "10", "columna": "REMUNERATIVO", "formula_importe": "1000"},
                {"codigo": "20", "columna": "REMUNERATIVO", "formula_importe": "#10 * 10%"},
                {"codigo": "30", "columna": "NO_REMUNERATIVO", "formula_importe": "50"},
                {"codigo": "40", "columna": "REMUNERATIVO", "formula_importe": "TOTAL('BONIF')"},
                {"codigo": "41", "columna": "AUXILIAR", "formula_importe": "TOTAL('REMUNERATIVO', #40, #41)"},
                {"codigo": "42", "columna": "AUXILIAR", "formula_importe": "CONCEPTOS('BONIF', 'MAX', IMPORTE)"},
                {"codigo": "43", "columna": "AUXILIAR", "formula_importe": "CONCEPTOS('REMUNERATIVO', '+', UNIDAD)"},
                {"codigo": "50", "columna": "DESCUENTO", "formula_importe": "TOTAL('REMUNERATIVO') * 8%"},
                {"codigo": "60", "columna": "CONTRIBUCION", "formula_importe": "100"},
            ]
        }),
        ctx(json!({})),
    );
    assert_eq!(concepto(&r, "40")["importe"], "1150.00");
    assert_eq!(concepto(&r, "41")["importe"], "1100.00");
    assert_eq!(concepto(&r, "42")["importe"], "1000.00");
    // rem = 1000 + 100 + 1150 = 2250 ; desc = 180 ; neto = 2250 + 50 - 180
    assert_eq!(r["totales"]["remunerativo"], "2250.00");
    assert_eq!(r["totales"]["no_remunerativo"], "50.00");
    assert_eq!(r["totales"]["descuento"], "180.00");
    assert_eq!(r["totales"]["bruto"], "2300.00");
    assert_eq!(r["totales"]["neto"], "2120.00");
    assert_eq!(r["totales"]["costo_laboral"], "2400.00");
}

#[test]
fn selector_desconocido_es_error() {
    let c = one("TOTAL('NOEXISTE')");
    assert_eq!(c["error"], true);
    assert!(c["message"].as_str().unwrap().contains("NOEXISTE"));
}

/// Cadena de las planillas: clase -> adicionales en cascada -> haber -> retiro -> pensión -> beneficiarios -> descuentos.
#[test]
fn escenario_retiro_y_pension() {
    let conceptos = json!([
        {"codigo": "10",  "orden": 10, "columna": "REMUNERATIVO", "descripcion": "Clase",
         "formula_importe": "TABLA('ESCALA_CLASE', COL.CLASE = CLASE, COL.HABER)"},
        {"codigo": "80",  "orden": 20, "columna": "REMUNERATIVO", "descripcion": "Antigüedad",
         "formula_importe": "#10 * 2% * ANIOS_ANTIGUEDAD"},
        {"codigo": "90",  "orden": 30, "columna": "REMUNERATIVO", "descripcion": "Adic. Fuerzas de Seguridad",
         "formula_importe": "TOTAL('REMUNERATIVO', #90, #91) * 37%"},
        {"codigo": "91",  "orden": 40, "columna": "REMUNERATIVO", "descripcion": "07/05",
         "formula_importe": "TOTAL('REMUNERATIVO', #91) * 10%"},
        {"codigo": "500", "orden": 50, "columna": "AUXILIAR", "descripcion": "Haber de retiro",
         "formula_importe": "TOTAL('REMUNERATIVO') * TABLA('PORC_RETIRO', COL.ANIOS <= ANIOS_SERVICIO AND COL.ANIOS >= 20, COL.PORC, 0) / 100"},
        {"codigo": "600", "orden": 60, "columna": "AUXILIAR", "descripcion": "Pensión",
         "formula_importe": "#500 * HISTORIAL('PORC_PENSION')"},
        {"codigo": "610", "orden": 70, "columna": "NO_REMUNERATIVO", "descripcion": "Pensión conyuge",
         "formula_importe": "#600 * PORCENTAJE / 100"},
        {"codigo": "611", "orden": 80, "columna": "NO_REMUNERATIVO", "descripcion": "Art. 37",
         "formula_importe": "#500 * 5%", "formula_condicion": "ART37"},
    ]);
    let r_ret = run(json!({"conceptos": conceptos.as_array().unwrap()[..6].to_vec()}), ctx_completo());
    // Sin filtrar beneficiarios; TOTAL('REMUNERATIVO') de 500 incluye 10, 80, 90, 91
    // 10 = 2000.25 ; 80 = 2000.25*0.02*20 = 800.10 ; 90 = (2000.25+800.10)*0.37 = 1036.1295 -> 1036.13
    // 91 = (2000.25+800.10+1036.13)*0.10 = 383.648 -> 383.65  (90 ya redondeado)
    assert_eq!(concepto(&r_ret, "10")["importe"], "2000.25");
    assert_eq!(concepto(&r_ret, "80")["importe"], "800.10");
    assert_eq!(concepto(&r_ret, "90")["importe"], "1036.13");
    assert_eq!(concepto(&r_ret, "91")["importe"], "383.65");
    // haber = 4220.13 -> %retiro 70 (fila 20; fila 25 no aplica: 25 <= 27 sí aplica) -> ver abajo
    let haber = 2000.25 + 800.10 + 1036.13 + 383.65;
    assert!((haber - 4220.13_f64).abs() < 1e-9);
    // Filas con ANIOS <= 27 y >= 20: (20,70) y (25,100); TABLA toma la primera coincidencia => 70
    assert_eq!(concepto(&r_ret, "500")["importe"], "2954.09");
    assert_eq!(concepto(&r_ret, "600")["importe"], "2215.57");

    // pensión por beneficiario: un recibo por beneficiario con PORCENTAJE y ART37 propios
    let mut c = ctx_completo();
    c["variables"]["PORCENTAJE"] = json!({"decimal": "50"});
    c["variables"]["ART37"] = json!(true);
    let r = run(json!({"conceptos": conceptos}), c);
    assert_eq!(concepto(&r, "610")["importe"], "1107.79");
    assert_eq!(concepto(&r, "611")["importe"], "147.70");
    // los conceptos de pensión van en otra columna: si estuvieran en REMUNERATIVO, el TOTAL('REMUNERATIVO')
    // del haber dependería de ellos y habría un ciclo
    assert_eq!(r["totales"]["remunerativo"], "4220.13");
    assert_eq!(r["totales"]["no_remunerativo"], "1255.49");
}

#[test]
fn validar_formula_devuelve_referencias() {
    let out = validar_formula_json("TOTAL('BONIF', #10) + #20 * CLASE + TABLA('T', COL1 = 1, COL2) + HISTORIAL('H')", "[]").unwrap();
    let v: Value = serde_json::from_str(&out).unwrap();
    assert_eq!(v["conceptos"], json!(["20"]));
    assert_eq!(v["selectores"], json!(["BONIF"]));
    assert!(v["variables"].as_array().unwrap().contains(&json!("CLASE")));
    assert_eq!(v["tablas"], json!(["T"]));
    assert_eq!(v["historial"], json!(["H"]));
}

#[test]
fn validar_formula_errores_de_sintaxis_y_aridad() {
    for bad in ["1 +", "(1 + 2", "FOO(1)", "IF(1, 2)", "TOTAL(CLASE)", "CONCEPTOS('X', '??', 1)", "1 $ 2", "'sin cerrar", "TABLA(X, 1, 2)", "EXISTE(3)"] {
        assert!(validar_formula_json(bad, "[]").is_err(), "debería fallar: {bad}");
    }
}

#[test]
fn validar_reglas_advierte_referencias_y_variables_desconocidas() {
    let reglas = json!({"conceptos": [{"codigo": "1", "formula_importe": "#99 + FOO + CLASE"}]});
    let out = validar_reglas_json(&reglas.to_string(), Some(vec!["clase".into()])).unwrap();
    let v: Value = serde_json::from_str(&out).unwrap();
    let msgs: Vec<String> = v.as_array().unwrap().iter().map(|p| p["mensaje"].as_str().unwrap().to_string()).collect();
    assert!(msgs.iter().any(|m| m.contains("#99")));
    assert!(msgs.iter().any(|m| m.contains("FOO")));
    assert!(!msgs.iter().any(|m| m.contains("CLASE")));
    assert!(v.as_array().unwrap().iter().all(|p| p["nivel"] == "warning"));
}

#[test]
fn codigo_numerico_en_json_y_duplicados() {
    let r = run(json!({"conceptos": [{"codigo": 7, "formula_importe": "1"}]}), ctx(json!({})));
    assert_eq!(concepto(&r, "7")["importe"], "1.00");
    let dup = json!({"conceptos": [{"codigo": "1"}, {"codigo": "1"}]});
    assert!(calcular_json(&dup.to_string(), &ctx(json!({})).to_string()).is_err());
}

#[test]
fn contexto_invalido() {
    assert!(calcular_json("{}", "{}").is_err());
    assert!(calcular_json("no-json", "{}").is_err());
}

#[test]
fn entradas_hostiles_no_tumban_el_motor() {
    let profunda = format!("{}1{}", "(".repeat(50_000), ")".repeat(50_000));
    assert!(validar_formula_json(&profunda, "[]").is_err());
    assert!(validar_formula_json(&"-".repeat(50_000), "[]").is_err());
    assert!(validar_formula_json(&format!("{}TRUE", "NOT ".repeat(50_000)), "[]").is_err());

    // A = B B ; B = C C ; ... crece exponencialmente
    let mut aux = Vec::new();
    for i in 0..40 {
        aux.push(json!({"codigo": format!("M{i}"), "formula": format!("M{} + M{}", i + 1, i + 1)}));
    }
    aux.push(json!({"codigo": "M40", "formula": "1"}));
    let r = run(json!({"auxiliares": aux, "conceptos": [{"codigo": "1", "formula_importe": "M0"}]}), ctx(json!({})));
    assert_eq!(concepto(&r, "1")["error"], true);
}

#[test]
fn formula_larga_es_rechazada() {
    let larga = vec!["1"; 100_000].join("+");
    assert!(validar_formula_json(&larga, "[]").is_err());
    assert!(validar_formula_json(&vec!["1"; 1_000].join("+"), "[]").is_err());
    let razonable = vec!["1"; 150].join("+");
    assert!(validar_formula_json(&razonable, "[]").is_ok());
    let r = run(json!({"conceptos": [{"codigo": "1", "formula_importe": razonable}]}), ctx(json!({})));
    assert_eq!(concepto(&r, "1")["importe"], "150.00");
}

// ------------------------------------------------------------ lenguaje: potencia, funciones, textos

#[test]
fn potencia_precedencia_y_asociatividad() {
    assert_eq!(one("2^10")["importe"], "1024.00");
    assert_eq!(one("2^3^2")["importe"], "512.00"); // por la derecha: 2^(3^2)
    assert_eq!(one("2 * 3^2")["importe"], "18.00");
    assert_eq!(one("-2^2")["importe"], "4.00"); // el menos unario liga más fuerte, como Excel
    assert_eq!(one("-(2^2)")["importe"], "-4.00");
    assert_eq!(one("2^-2")["importe"], "0.25");
    assert_eq!(one("10%^2 * 100")["importe"], "1.00"); // (10%)^2 = 0,01
    assert_eq!(one("1.05^2")["importe"], "1.10"); // 1,1025 exacto, redondeado a 2
    assert_eq!(one("ROUND(1.05^2, 4) * 10000")["importe"], "11025.00");
    assert_eq!(one("POTENCIA(9, 0.5)")["importe"], "3.00");
    assert_eq!(one("POW(2, 3)")["importe"], "8.00");
    assert_eq!(one("0^-1")["error"], true);
    assert_eq!(one("(-8)^0.5")["error"], true);
}

#[test]
fn funciones_matematicas_y_alias() {
    assert_eq!(one("RAIZ(16) + SQRT(9)")["importe"], "7.00");
    assert_eq!(one("RAIZ(-1)")["error"], true);
    assert_eq!(one("REDONDEAR_ARRIBA(2.001)")["importe"], "3.00");
    assert_eq!(one("CEIL(-2.9)")["importe"], "-2.00");
    assert_eq!(one("REDONDEAR_ABAJO(2.999, 2)")["importe"], "2.99");
    assert_eq!(one("FLOOR(-2.1)")["importe"], "-3.00");
    assert_eq!(one("SUMA(1, 2, 3.5)")["importe"], "6.50");
    assert_eq!(one("SUM(4)")["importe"], "4.00");
    assert_eq!(one("PROMEDIO(1, 2, 3, 4)")["importe"], "2.50");
    assert_eq!(one("AVERAGE(10, 20)")["importe"], "15.00");
    assert_eq!(one("SIGNO(-7) + SIGN(0) * 10 + SIGNO(3) * 100")["importe"], "99.00");
    assert_eq!(one("MOD(17, 5) + RESTO(-7, 3) * 10")["importe"], "-8.00"); // 2 + (-1)*10
    assert_eq!(one("EXP(0) + LN(1) + LOG10(1000)")["importe"], "4.00");
    assert_eq!(one("ROUND(LN(EXP(2)), 6)")["importe"], "2.00");
    assert_eq!(one("REDONDEAR(2.345, 2)")["importe"], "2.35");
}

#[test]
fn aridad_de_funciones_nuevas_se_valida() {
    assert!(validar_formula_json("SUMA()", "[]").is_err());
    assert!(validar_formula_json("MOD(1)", "[]").is_err());
    assert!(validar_formula_json("RAIZ(1, 2)", "[]").is_err());
    assert!(validar_formula_json("2^3 + RAIZ(16)", "[]").is_ok());
}

#[test]
fn textos_con_comillas_escapadas() {
    let r = run(
        json!({"conceptos": [
            {"codigo": "1", "formula_importe": "IF(NOMBRE = 'D''Angelo', 1, 2)"},
            {"codigo": "2", "formula_importe": "IF(\"di \"\"x\"\"\" = 'di \"x\"', 1, 2)"},
            {"codigo": "3", "formula_importe": "IF('' = '', 1, 2)"},
        ]}),
        ctx(json!({"NOMBRE": "D'Angelo"})),
    );
    assert_eq!(concepto(&r, "1")["importe"], "1.00");
    assert_eq!(concepto(&r, "2")["importe"], "1.00");
    assert_eq!(concepto(&r, "3")["importe"], "1.00");
}

// ------------------------------------------------------------ errores con tipo, posición y fragmento

#[test]
fn errores_de_evaluacion_con_detalle() {
    let c = one("100 + 10 / (5 - 5)");
    assert_eq!(c["error_detalle"], json!({"campo": "formula_importe", "tipo": "division_por_cero", "pos": 9}));
    let msg = c["message"].as_str().unwrap();
    assert!(msg.starts_with("formula_importe, posición 9 («100 + 10 ▶/ (5 - 5)»): División por cero"), "{msg}");

    let c = one("HABER * RESP_X%");
    assert_eq!(c["error_detalle"]["tipo"], "variable_no_definida");
    assert_eq!(c["error_detalle"]["pos"], 0);

    let c = one("1 + 'a'");
    assert_eq!(c["error_detalle"]["tipo"], "tipo");
    assert_eq!(c["error_detalle"]["pos"], 2);

    let c = one("TABLA('NO_EXISTE', COL1 = 1, COL2)");
    assert_eq!(c["error_detalle"]["tipo"], "sin_datos");

    // error en la condición: se informa ese campo
    let r = run(json!({"conceptos": [{"codigo": "1", "formula_condicion": "X > 1", "formula_importe": "1"}]}), ctx(json!({})));
    assert_eq!(concepto(&r, "1")["error_detalle"]["campo"], "formula_condicion");

    // sin error: detalle nulo; error de sintaxis: tipo sintaxis
    assert_eq!(one("1")["error_detalle"], Value::Null);
    assert_eq!(one("1 +")["error_detalle"]["tipo"], "sintaxis");
}

#[test]
fn fragmento_de_formula_larga_se_recorta() {
    let c = one("1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + NO_DEFINIDA + 9 + 10 + 11 + 12 + 13");
    let msg = c["message"].as_str().unwrap();
    assert!(msg.contains("(«… + 6 + 7 + 8 + ▶NO_DEFINIDA + 9…»)"), "{msg}");
}

// ------------------------------------------------------------ compilar una vez

#[test]
fn compilado_se_reutiliza_con_distintos_contextos() {
    let reglas = json!({"conceptos": [
        {"codigo": "10", "formula_importe": "TABLA('ESCALA', COL.CLASE = CLASE, COL.HABER)"},
        {"codigo": "80", "formula_importe": "#10 * 2% * ANIOS_ANTIGUEDAD"},
    ]}).to_string();
    let comp = otp_formula::compilar_json(&reglas).unwrap();
    let tabla = json!({"ESCALA": {"columnas": [{"nombre": "CLASE", "tipo": "int"}, {"nombre": "HABER", "tipo": "decimal"}],
                                  "filas": [[1, "1000"], [2, "2000"]]}});
    for (clase, anios) in [(1, 10), (2, 5), (1, 0)] {
        let c = json!({"fecha": "2025-01-01", "variables": {"CLASE": clase, "ANIOS_ANTIGUEDAD": anios}, "tablas": tabla}).to_string();
        let a = comp.calcular_json(&c).unwrap();
        let b = calcular_json(&reglas, &c).unwrap();
        assert_eq!(a, b);
    }
}
