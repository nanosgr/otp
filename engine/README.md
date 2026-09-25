# engine — motor de fórmulas (Rust)

Motor **puro** de liquidación: recibe reglas (conceptos con fórmulas, auxiliares, grupos) y un contexto ya cargado
(variables, tablas, historial, beneficiarios) y devuelve conceptos calculados y totales. No accede a la base de datos.

```
engine/
├── otp-formula/      núcleo (lexer, parser, macros, análisis, DAG, evaluador) + tests
└── otp-formula-py/   binding PyO3 → módulo Python `otp_engine`
```

```bash
cd engine && cargo test                                  # 34 tests (unitarios + propiedades)
cd engine/otp-formula-py && maturin develop --release    # instala otp_engine en el venv activo
```
Uso desde el backend: `app/services/motor.py` (`calcular`, `compilar`, `validar_reglas`, `validar_formula`).

**Compilar una vez:** `compilar(reglas)` / `otp_engine.ReglasCompiladas(reglas_json)` parsea las fórmulas, expande auxiliares y arma
el orden de evaluación una sola vez; `.calcular(contexto_json)` da lo mismo que `calcular(reglas, contexto)`. `motor.calcular`
cachea las reglas compiladas por su JSON (LRU de 128), así que el liquidador compila una vez por vigencia/etapa.

## Cálculo de un concepto
Cada concepto tiene 4 fórmulas opcionales. Orden de evaluación: **condición** → unidad → unitario → importe.
- Condición vacía = verdadera. Si es falsa, el concepto queda oculto: no se evalúan las demás fórmulas, no suma en
  totales, `EXISTE(#c)` es falso y sus referencias valen 0.
- Sin fórmula de importe: `importe = unidad × unitario` (si están ambas), si no 0.
- Dentro de las fórmulas del concepto: `UNIDAD`, `UNITARIO` (ya calculados), `CAMPO_UNIDAD`, `CAMPO_IMPORTE` (valores manuales, `contexto.campos`).
- Redondeo mitad hacia arriba (lejos de cero): unidad a `decimales_unidad` (4), unitario a 4, importe a `decimales_importe` (2).
- Totales: `bruto = rem + no_rem`, `neto = bruto − descuento`, `costo_laboral = bruto + contribución`. `AUXILIAR` no suma.

## Dependencias
Se extraen estáticamente (`#c`, `EXISTE/UNIDAD_CONCEPTO/...(#c)`, `TOTAL(sel)`, `CONCEPTOS(sel,…)`) y se evalúan en orden
topológico (desempate por `orden`, luego código). Un ciclo marca error en los conceptos involucrados y en los que dependen de ellos; el resto se calcula.
Un error en un concepto se propaga a quienes lo referencian. Referirse a un concepto que no está asignado da 0.
**Ojo con `TOTAL('COLUMNA')`:** depende de todos los conceptos de esa columna; si algún concepto de la columna depende del resultado, hay ciclo.
Excluir con `TOTAL('REMUNERATIVO', #90, #91)` o poner los conceptos derivados (p. ej. pensión) en otra columna.

## Lenguaje
- Números `12.5`, porcentaje `10%` (= /100), textos `'x'` o `"x"` (la comilla se escapa duplicándola: `'D''Angelo'`), `TRUE/FALSE`,
  referencias `#10` (importe del concepto, 0 si no aplica).
- Operadores: `+ - * /`, potencia `^`, `= <> != < <= > >=`, `AND OR NOT`. Identificadores en mayúsculas (`FECHA`, `CLASE`, `COL.HABER`).
- Precedencia (de menor a mayor): `OR`, `AND`, `NOT`, comparaciones, `+ -`, `* /`, `^`, menos unario, `%` (porcentaje).
  `^` es asociativo por la derecha (`2^3^2` = 512) y, como en Excel, el menos unario liga más fuerte: `-2^2` = 4, `10%^2` = 0,01.
  Con exponente entero la potencia es exacta; con exponente decimal es una aproximación decimal (sin punto flotante).
- Fechas: `FECHA('2025-03-01')`, `ANIOS(d1,d2)` (años cumplidos), `MESES`, `DIAS`, `ANIO`, `MES`, `DIA`.
- Funciones (alias separados por `/`): `IF/SI(c,a,b)`, `ROUND/REDONDEAR(x[,n])` (mitad hacia arriba), `TRUNC(x[,n])`,
  `CEIL/REDONDEAR_ARRIBA(x[,n])`, `FLOOR/REDONDEAR_ABAJO(x[,n])`, `MIN(…)`, `MAX(…)`, `SUMA/SUM(…)`, `PROMEDIO/AVERAGE(…)`, `ABS`,
  `SIGNO/SIGN`, `MOD/RESTO(a,b)`, `POTENCIA/POW(x,y)`, `RAIZ/SQRT`, `EXP`, `LN`, `LOG10`.
- **Nueva función:** una entrada en `otp-formula/src/functions.rs::FUNCIONES` (nombre, alias, aridad, implementación) y un test.
  Las `Impl::Pura` reciben los argumentos evaluados; las `Impl::Especial` (lazy o con contexto) se resuelven en `eval.rs`.
- `TABLA('COD', condición, resultado[, default])`: primera fila que cumple; en la condición/resultado están `COL1..COLn` y `COL.NOMBRE`.
- `HISTORIAL('CAMPO'[, fecha[, default]])`, `EXISTE_HISTORIAL('CAMPO'[, fecha])`: valor vigente a la fecha (default: `FECHA`).
- `EXISTE(#c)`, `UNIDAD_CONCEPTO(#c)`, `UNITARIO_CONCEPTO(#c)`, `IMPORTE_CONCEPTO(#c)`.
- `TOTAL(sel[, #excluidos…])` y `CONCEPTOS(sel, op, expr)`; `sel` = columna (`REMUNERATIVO`, `NO_REMUNERATIVO`, `DESCUENTO`, `CONTRIBUCION`, `AUXILIAR`) o grupo. En `expr`: `UNIDAD`, `UNITARIO`, `IMPORTE`, `CODIGO`.
- `BENEFICIARIOS(filtro, op, expr)`: `filtro` = `'TODOS'` o parentesco; en `expr` están las variables de cada beneficiario (`PORCENTAJE`, …).
- `op`: `'+' '*' 'MAX' 'MIN' 'AVG' 'AND' 'OR' 'COUNT'`.
- **Auxiliares (macros):** `codigo`, `formato` (`(a,b)` o vacío) y `formula` con `?0`, `?1` (o `?` si hay uno). Expansión por tokens, máx. 50 pasadas.
- Límites (protección de entradas hostiles): 5000 símbolos, profundidad 200, expansión de macros 50 000 símbolos.

## Contrato JSON
Entrada (`calcular(reglas_json, contexto_json)`):
```jsonc
// reglas
{"conceptos": [{"codigo": "10", "descripcion": "Clase", "columna": "REMUNERATIVO", "orden": 10,
                "formula_unidad": null, "formula_unitario": null, "formula_importe": "…", "formula_condicion": null,
                "decimales_unidad": 4, "decimales_importe": 2}],
 "auxiliares": [{"codigo": "IVA", "formato": "(x)", "formula": "? * 21%"}],
 "grupos": {"BONIF": ["10", "80"]}}
// contexto
{"fecha": "2025-03-01",
 "variables": {"CLASE": 3, "TIPO": "superior", "HABER": {"decimal": "1000.10"}, "INGRESO": {"date": "2005-03-01"}},
 "tablas": {"ESCALA": {"columnas": [{"nombre": "CLASE", "tipo": "int"}, {"nombre": "HABER", "tipo": "decimal"}], "filas": [[2, "1000.10"]]}},
 "historial": {"PORC_PENSION": [{"desde": "2025-01-01", "hasta": null, "valor": {"decimal": "0.75"}}]},
 "beneficiarios": [{"parentesco": "conyuge", "porcentaje": {"decimal": "50"}}],
 "campos": {"99": {"unidad": null, "importe": "10.5"}}}
```
Valores: número, booleano y string (texto) directos; `{"decimal": ".."}` y `{"date": "AAAA-MM-DD"}` para tipar. `app/services/motor.py` los genera desde `Decimal`/`date`.
Salida: `{"conceptos": [{codigo, descripcion, columna, orden, unidad, unitario, importe, condicion, error, message, error_detalle}], "orden_evaluacion": […], "totales": {…}}` con importes como strings.

**Errores:** `error_detalle` es `null` o `{campo, tipo, pos}`: `campo` = fórmula que falló (`formula_importe`, …), `pos` = carácter
en esa fórmula y `tipo` ∈ `sintaxis`, `division_por_cero`, `tipo`, `variable_no_definida`, `funcion_desconocida`, `desbordamiento`,
`sin_datos` (tabla/historial sin valor), `dependencia`, `selector`, `ciclo`, `otro`. El `message` de un error de evaluación señala
el lugar: `formula_importe, posición 9 («100 + 10 ▶/ (5 - 5)»): División por cero`.
