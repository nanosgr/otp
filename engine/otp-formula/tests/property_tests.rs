use otp_formula::{calcular_json, validar_formula_json};
use proptest::prelude::*;
use serde_json::{json, Value};

fn importe(formula: &str) -> Option<String> {
    let reglas = json!({"conceptos": [{"codigo": "1", "formula_importe": formula}]});
    let ctx = json!({"fecha": "2025-01-01"});
    let out: Value = serde_json::from_str(&calcular_json(&reglas.to_string(), &ctx.to_string()).unwrap()).unwrap();
    let c = &out["conceptos"][0];
    if c["error"] == true { None } else { c["importe"].as_str().map(str::to_string) }
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    #[test]
    fn el_analisis_nunca_entra_en_panico(s in "\\PC{0,60}") {
        let _ = validar_formula_json(&s, "[]");
    }

    #[test]
    fn la_evaluacion_nunca_entra_en_panico(s in "[0-9a-zA-Z_+*/()%^,'#<>= .-]{0,40}") {
        let reglas = json!({"conceptos": [{"codigo": "1", "formula_importe": s, "formula_condicion": s}]});
        let ctx = json!({"fecha": "2025-01-01"});
        let _ = calcular_json(&reglas.to_string(), &ctx.to_string());
    }

    #[test]
    fn aritmetica_entera_coincide_con_referencia(a in -1000i64..1000, b in -1000i64..1000, c in 1i64..1000) {
        let expected = a * b + c - a;
        let got = importe(&format!("({a}) * ({b}) + {c} - ({a})")).unwrap();
        prop_assert_eq!(got, format!("{expected}.00"));
    }

    #[test]
    fn compilar_y_calcular_equivale_a_calcular(a in -1000i64..1000, b in 0i64..6, c in 1i64..50) {
        let reglas = json!({"conceptos": [
            {"codigo": "1", "formula_importe": format!("({a}) ^ {b} / {c} + X")},
            {"codigo": "2", "formula_importe": "#1 * 2 + MOD(X, 7)"},
        ]}).to_string();
        let comp = otp_formula::compilar_json(&reglas).unwrap();
        for x in [0, 5, 13] {
            let ctx = json!({"fecha": "2025-01-01", "variables": {"X": x}}).to_string();
            prop_assert_eq!(comp.calcular_json(&ctx).unwrap(), calcular_json(&reglas, &ctx).unwrap());
        }
    }

    #[test]
    fn el_redondeo_es_idempotente(x in -100000i64..100000, dp in 0u32..4) {
        let f = format!("ROUND({x} / 1000, {dp})");
        let once = importe(&f).unwrap();
        let twice = importe(&format!("ROUND({once}, {dp})")).unwrap();
        prop_assert_eq!(once, twice);
    }
}
