import {
  Users, UserRound, Briefcase, CalendarRange, MapPin, FunctionSquare, Layers, Braces, CalendarClock,
  Table2, Rows3, SlidersHorizontal, FileSpreadsheet, Receipt, ListChecks, Route, type LucideIcon,
} from 'lucide-react';

export type FieldType = 'text' | 'textarea' | 'number' | 'decimal' | 'date' | 'checkbox' | 'select' | 'json';

export interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: { value: string; label: string }[];
  defaultValue?: unknown;
  hint?: string;
  hideInTable?: boolean;
  /** Se muestra en la tabla pero no se edita (lo calcula el sistema) */
  readOnly?: boolean;
}

export interface RelatedLink {
  label: string;
  resource: string;
  param: string;
}

export interface ResourceDef {
  key: string;
  path: string;
  permission: string;
  title: string;
  singular: string;
  icon: LucideIcon;
  group: 'Personas' | 'Reglas' | 'Liquidación';
  fields: FieldDef[];
  related?: RelatedLink[];
  /** Filtros que se toman de la query string (?campo=valor) y se envían a la API */
  filters?: string[];
  searchable?: boolean;
  /** Campos que impide editar/eliminar cuando estado === 'CERRADA' (informativo) */
  readOnlyWhenClosed?: boolean;
  /** Enlace a una página de detalle propia (p. ej. la planilla de una liquidación) */
  detail?: { label: string; path: (id: number) => string };
}

const opt = (...values: string[]) => values.map((v) => ({ value: v, label: v }));
const fk = (name: string, label: string, required = true): FieldDef => ({
  name, label, type: 'number', required, hint: 'ID del registro relacionado',
});

export const RESOURCES: ResourceDef[] = [
  {
    key: 'causantes', path: 'causantes', permission: 'causantes', title: 'Causantes', singular: 'Causante',
    icon: Users, group: 'Personas', searchable: true,
    related: [
      { label: 'Beneficiarios', resource: 'beneficiarios', param: 'causante_id' },
      { label: 'Cargos', resource: 'cargos', param: 'causante_id' },
      { label: 'Servicios', resource: 'servicios', param: 'causante_id' },
      { label: 'Zonas', resource: 'zonas', param: 'causante_id' },
      { label: 'Liquidaciones', resource: 'liquidaciones', param: 'causante_id' },
    ],
    fields: [
      { name: 'dni', label: 'DNI', type: 'text', required: true },
      { name: 'apellido', label: 'Apellido', type: 'text', required: true },
      { name: 'nombre', label: 'Nombre', type: 'text', required: true },
      { name: 'expediente', label: 'Expediente', type: 'text' },
      { name: 'tipo_personal', label: 'Tipo de personal', type: 'select', defaultValue: 'subalterno', options: opt('subalterno', 'superior') },
      { name: 'escalafon', label: 'Escalafón', type: 'text', hideInTable: true },
      { name: 'fecha_nacimiento', label: 'Nacimiento', type: 'date', hideInTable: true },
      { name: 'fecha_ingreso', label: 'Ingreso', type: 'date', hideInTable: true },
      { name: 'fecha_egreso', label: 'Egreso', type: 'date', hideInTable: true },
      { name: 'fecha_fallecimiento', label: 'Fallecimiento', type: 'date' },
      { name: 'is_active', label: 'Activo', type: 'checkbox', defaultValue: true },
    ],
  },
  {
    key: 'beneficiarios', path: 'beneficiarios', permission: 'beneficiarios', title: 'Beneficiarios', singular: 'Beneficiario',
    icon: UserRound, group: 'Personas', searchable: true, filters: ['causante_id'],
    fields: [
      fk('causante_id', 'Causante'),
      { name: 'apellido', label: 'Apellido', type: 'text', required: true },
      { name: 'nombre', label: 'Nombre', type: 'text', required: true },
      { name: 'dni', label: 'DNI', type: 'text' },
      { name: 'parentesco', label: 'Parentesco', type: 'select', defaultValue: 'conyuge', options: opt('conyuge', 'hijo', 'padre', 'madre', 'conviviente', 'otro') },
      { name: 'porcentaje', label: '% beneficiario', type: 'decimal', defaultValue: '0', hint: 'Porcentaje 0-100 de la pensión (la suma no puede pasar de 100)' },
      { name: 'fecha_nacimiento', label: 'Nacimiento', type: 'date', hideInTable: true },
      { name: 'fecha_alta', label: 'Alta', type: 'date' },
      { name: 'fecha_baja', label: 'Baja', type: 'date', hideInTable: true },
      { name: 'discapacidad', label: 'Discapacidad', type: 'checkbox', hideInTable: true },
      { name: 'art37', label: 'Art. 37 (5%)', type: 'checkbox' },
      { name: 'is_active', label: 'Activo', type: 'checkbox', defaultValue: true, hideInTable: true },
    ],
  },
  {
    key: 'cargos', path: 'cargos', permission: 'cargos', title: 'Cargos / secuencias', singular: 'Cargo',
    icon: Briefcase, group: 'Personas', filters: ['causante_id'],
    fields: [
      fk('causante_id', 'Causante'),
      { name: 'secuencia', label: 'Secuencia', type: 'number', defaultValue: 1, hint: 'El cargo de menor secuencia es el principal: de él salen el % de retiro y sus años' },
      { name: 'porcentaje_secuencia', label: '% de la secuencia', type: 'decimal', defaultValue: '100', hint: 'Peso en el haber ponderado; los cargos del causante deben sumar 100' },
      { name: 'clase', label: 'Clase (2-27)', type: 'number', required: true, defaultValue: 2 },
      { name: 'fecha_desde', label: 'Desde', type: 'date', hideInTable: true },
      { name: 'fecha_hasta', label: 'Hasta', type: 'date', hideInTable: true },
      { name: 'responsabilidad_jerarquica_porcentaje', label: '% resp. jerárquica', type: 'decimal', defaultValue: '0', hideInTable: true, hint: 'Porcentaje 0-100 sobre la base del Jefe de Policía' },
      { name: 'recargo_servicio_porcentaje', label: '% recargo de servicio', type: 'decimal', defaultValue: '0', hideInTable: true, hint: 'Porcentaje 0-100 sobre la base del Jefe de Policía' },
      { name: 'titulo', label: 'Título', type: 'select', defaultValue: 'ninguno', options: opt('ninguno', 'pregrado', 'grado', 'posgrado') },
      { name: 'titulo_pregrado_nivel', label: 'Nivel pregrado (0-3)', type: 'number', defaultValue: 0, hideInTable: true },
      { name: 'riesgo_especial', label: 'Riesgo especial', type: 'checkbox', hideInTable: true },
      { name: 'zona_porcentaje', label: '% zona', type: 'decimal', defaultValue: '0', hideInTable: true, hint: 'Porcentaje 0-100 (hoja CALCULO ZONA)' },
      { name: 'zona_clase', label: 'Clase base de zona (0 = sin zona)', type: 'number', defaultValue: 0, hideInTable: true },
      { name: 'anios_antiguedad', label: 'Años de antigüedad', type: 'decimal', defaultValue: '0', hint: 'Antigüedad final: define el 2% por año y el % de retiro' },
      { name: 'presentismo', label: 'Presentismo', type: 'checkbox', hideInTable: true },
      { name: 'cuerpo_apoyo_porcentaje', label: '% cuerpo de apoyo', type: 'decimal', defaultValue: '0', hideInTable: true },
      { name: 'adicional_seguridad', label: 'Adic. seguridad', type: 'checkbox', hideInTable: true },
      { name: 'eventos_especiales', label: 'Eventos especiales', type: 'checkbox', hideInTable: true },
      { name: 'porcentaje_retiro', label: '% retiro (manual)', type: 'decimal', defaultValue: '0', hint: '0 = se toma de la tabla según años de antigüedad y tipo de personal' },
      { name: 'caracter', label: 'Carácter', type: 'text', hideInTable: true },
      { name: 'jurisdiccion', label: 'Jurisdicción', type: 'text', hideInTable: true },
      { name: 'finalidad', label: 'Finalidad', type: 'text', hideInTable: true },
      { name: 'funcion', label: 'Función', type: 'text', hideInTable: true },
    ],
  },
  {
    key: 'servicios', path: 'servicios', permission: 'servicios', title: 'Períodos de servicio', singular: 'Período',
    icon: CalendarRange, group: 'Personas', searchable: true, filters: ['causante_id'],
    fields: [
      fk('causante_id', 'Causante'),
      { name: 'tipo', label: 'Tipo', type: 'select', defaultValue: 'servicio', options: opt('servicio', 'suspension', 'licencia', 'otro') },
      { name: 'fecha_desde', label: 'Desde', type: 'date', required: true },
      { name: 'fecha_hasta', label: 'Hasta', type: 'date' },
      { name: 'descripcion', label: 'Descripción', type: 'text' },
      { name: 'computable', label: 'Computable', type: 'checkbox', defaultValue: true },
    ],
  },
  {
    key: 'zonas', path: 'zonas', permission: 'zonas', title: 'Zonas y destinos', singular: 'Zona',
    icon: MapPin, group: 'Personas', searchable: true, filters: ['causante_id'],
    fields: [
      fk('causante_id', 'Causante'),
      { name: 'dependencia', label: 'Dependencia', type: 'text', required: true },
      { name: 'porcentaje_zona', label: '% zona', type: 'decimal', defaultValue: '0' },
      { name: 'fecha_desde', label: 'Desde', type: 'date', required: true },
      { name: 'fecha_hasta', label: 'Hasta', type: 'date' },
    ],
  },
  {
    key: 'conceptos', path: 'conceptos', permission: 'conceptos', title: 'Conceptos', singular: 'Concepto',
    icon: FunctionSquare, group: 'Reglas', searchable: true, filters: ['columna'],
    related: [{ label: 'Vigencias', resource: 'concepto-vigencias', param: 'concepto_id' }],
    fields: [
      { name: 'codigo', label: 'Código', type: 'text', required: true },
      { name: 'descripcion', label: 'Descripción', type: 'text', required: true },
      { name: 'columna', label: 'Columna', type: 'select', defaultValue: 'REMUNERATIVO', options: opt('REMUNERATIVO', 'NO_REMUNERATIVO', 'DESCUENTO', 'CONTRIBUCION', 'AUXILIAR') },
      { name: 'formula_unidad', label: 'Fórmula unidad', type: 'textarea', hideInTable: true },
      { name: 'formula_importe', label: 'Fórmula importe', type: 'textarea', hideInTable: true },
      { name: 'formula_unitario', label: 'Fórmula unitario', type: 'textarea', hideInTable: true },
      { name: 'formula_condicion', label: 'Fórmula condición', type: 'textarea', hideInTable: true, hint: 'Vacía = siempre verdadera' },
      { name: 'simbolo_unidad', label: 'Símbolo unidad', type: 'text', hideInTable: true },
      { name: 'decimales_unidad', label: 'Decimales unidad', type: 'number', defaultValue: 4, hideInTable: true },
      { name: 'decimales_importe', label: 'Decimales importe', type: 'number', defaultValue: 2, hideInTable: true },
      { name: 'unidad_visible', label: 'Unidad visible', type: 'checkbox', defaultValue: true, hideInTable: true },
      { name: 'etapa', label: 'Etapa', type: 'select', defaultValue: 'haber', options: opt('haber', 'liquidacion'), hint: 'haber: se calcula por tramo mensual; liquidacion: una vez sobre el subtotal (descuentos, anticipo)' },
      { name: 'orden', label: 'Orden', type: 'number', defaultValue: 0 },
      { name: 'is_active', label: 'Activo', type: 'checkbox', defaultValue: true },
    ],
  },
  {
    key: 'concepto-vigencias', path: 'concepto-vigencias', permission: 'concepto_vigencias', title: 'Vigencias de conceptos', singular: 'Vigencia',
    icon: CalendarClock, group: 'Reglas', searchable: true, filters: ['concepto_id'],
    fields: [
      fk('concepto_id', 'Concepto'),
      { name: 'alcance', label: 'Alcance', type: 'select', defaultValue: 'general', options: opt('general', 'grupo', 'tipo_beneficio') },
      fk('grupo_id', 'Grupo', false),
      { name: 'tipo_beneficio', label: 'Tipo de beneficio', type: 'select', options: [{ value: '', label: '(todos)' }, ...opt('retiro', 'pension')] },
      { name: 'vigencia_desde', label: 'Desde', type: 'date' },
      { name: 'vigencia_hasta', label: 'Hasta', type: 'date' },
      { name: 'descripcion', label: 'Descripción', type: 'text' },
      { name: 'orden', label: 'Orden', type: 'number', hideInTable: true },
    ],
  },
  {
    key: 'grupos-concepto', path: 'grupos-concepto', permission: 'grupos_concepto', title: 'Grupos de conceptos', singular: 'Grupo',
    icon: Layers, group: 'Reglas', searchable: true,
    fields: [
      { name: 'nombre', label: 'Nombre', type: 'text', required: true },
      { name: 'descripcion', label: 'Descripción', type: 'text' },
      { name: 'is_active', label: 'Activo', type: 'checkbox', defaultValue: true },
    ],
  },
  {
    key: 'formulas-auxiliares', path: 'formulas-auxiliares', permission: 'formulas_auxiliares', title: 'Fórmulas auxiliares', singular: 'Fórmula auxiliar',
    icon: Braces, group: 'Reglas', searchable: true,
    fields: [
      { name: 'codigo', label: 'Código', type: 'text', required: true },
      { name: 'formato', label: 'Formato', type: 'text', hint: 'Ej.: (a,b) — parámetros en la fórmula como ?0, ?1' },
      { name: 'formula', label: 'Fórmula', type: 'textarea', required: true },
      { name: 'descripcion', label: 'Descripción', type: 'text' },
      { name: 'orden', label: 'Orden', type: 'number', defaultValue: 0 },
    ],
  },
  {
    key: 'tablas', path: 'tablas', permission: 'tablas', title: 'Tablas y escalas', singular: 'Tabla',
    icon: Table2, group: 'Reglas', searchable: true,
    related: [{ label: 'Filas', resource: 'filas', param: 'tabla_id' }],
    fields: [
      { name: 'codigo', label: 'Código', type: 'text', required: true },
      { name: 'descripcion', label: 'Descripción', type: 'text' },
      { name: 'columnas', label: 'Columnas (JSON)', type: 'json', defaultValue: [], hint: 'Ej.: [{"nombre":"CLASE","tipo":"int"},{"nombre":"HABER","tipo":"decimal"}]', hideInTable: true },
      { name: 'vigencia_desde', label: 'Desde', type: 'date' },
      { name: 'vigencia_hasta', label: 'Hasta', type: 'date' },
      { name: 'is_active', label: 'Activa', type: 'checkbox', defaultValue: true },
    ],
  },
  {
    key: 'filas', path: 'filas', permission: 'tablas', title: 'Filas de tabla', singular: 'Fila',
    icon: Rows3, group: 'Reglas', filters: ['tabla_id'],
    fields: [
      fk('tabla_id', 'Tabla'),
      { name: 'orden', label: 'Orden', type: 'number', defaultValue: 0 },
      { name: 'valores', label: 'Valores (JSON)', type: 'json', defaultValue: [], hint: 'Lista alineada con las columnas. Ej.: [2, "131921.93"]' },
    ],
  },
  {
    key: 'parametros', path: 'parametros', permission: 'parametros', title: 'Parámetros con vigencia', singular: 'Parámetro',
    icon: SlidersHorizontal, group: 'Reglas', searchable: true, filters: ['campo'],
    fields: [
      { name: 'campo', label: 'Campo', type: 'text', required: true, hint: 'Ej.: PORC_PENSION, PORC_ART37, DESC_LEY_FEDERAL' },
      { name: 'valor', label: 'Valor', type: 'text', required: true },
      { name: 'tipo_dato', label: 'Tipo de dato', type: 'select', defaultValue: 'decimal', options: opt('decimal', 'int', 'text', 'date', 'bool') },
      { name: 'vigencia_desde', label: 'Desde', type: 'date' },
      { name: 'vigencia_hasta', label: 'Hasta', type: 'date' },
      { name: 'descripcion', label: 'Descripción', type: 'text' },
    ],
  },
  {
    key: 'liquidaciones', path: 'liquidaciones', permission: 'liquidaciones', title: 'Liquidaciones', singular: 'Liquidación',
    icon: FileSpreadsheet, group: 'Liquidación', searchable: true, filters: ['causante_id', 'estado', 'tipo'], readOnlyWhenClosed: true,
    detail: { label: 'Planilla', path: (id) => `/liquidaciones/${id}/planilla` },
    related: [
      { label: 'Recibos', resource: 'recibos', param: 'liquidacion_id' },
      { label: 'Tramos', resource: 'tramos-retroactivos', param: 'liquidacion_id' },
    ],
    fields: [
      fk('causante_id', 'Causante'),
      { name: 'periodo', label: 'Período (AAAA-MM)', type: 'text', required: true },
      { name: 'tipo', label: 'Tipo', type: 'select', defaultValue: 'retiro', options: opt('retiro', 'pension', 'reajuste') },
      { name: 'estado', label: 'Estado', type: 'select', defaultValue: 'ABIERTA', options: opt('ABIERTA', 'CERRADA') },
      { name: 'fecha_desde', label: 'Desde', type: 'date', hideInTable: true },
      { name: 'fecha_hasta', label: 'Hasta', type: 'date', hideInTable: true },
      { name: 'fecha_pago', label: 'Fecha de pago', type: 'date', hideInTable: true },
      { name: 'anticipo_importe', label: 'Anticipo percibido', type: 'decimal', defaultValue: '0', hideInTable: true, hint: 'Se descuenta del líquido' },
      { name: 'total_credito', label: 'Crédito', type: 'decimal', readOnly: true },
      { name: 'total_debitos', label: 'Débitos', type: 'decimal', readOnly: true },
      { name: 'total_liquido', label: 'Líquido', type: 'decimal', readOnly: true },
      { name: 'observaciones', label: 'Observaciones', type: 'textarea', hideInTable: true },
    ],
  },
  {
    key: 'recibos', path: 'recibos', permission: 'liquidaciones', title: 'Recibos', singular: 'Recibo',
    icon: Receipt, group: 'Liquidación', filters: ['liquidacion_id', 'beneficiario_id'],
    related: [{ label: 'Conceptos', resource: 'recibo-conceptos', param: 'recibo_id' }],
    fields: [
      fk('liquidacion_id', 'Liquidación'),
      fk('beneficiario_id', 'Beneficiario', false),
      { name: 'numero', label: 'Número', type: 'number', defaultValue: 1 },
      { name: 'total_remunerativo', label: 'Remunerativo', type: 'decimal', defaultValue: '0' },
      { name: 'total_no_remunerativo', label: 'No remunerativo', type: 'decimal', defaultValue: '0', hideInTable: true },
      { name: 'total_descuento', label: 'Descuentos', type: 'decimal', defaultValue: '0' },
      { name: 'total_contribucion', label: 'Contribuciones', type: 'decimal', defaultValue: '0', hideInTable: true },
      { name: 'sueldo_bruto', label: 'Bruto', type: 'decimal', defaultValue: '0', hideInTable: true },
      { name: 'sueldo_neto', label: 'Neto', type: 'decimal', defaultValue: '0' },
    ],
  },
  {
    key: 'recibo-conceptos', path: 'recibo-conceptos', permission: 'liquidaciones', title: 'Conceptos de recibo', singular: 'Concepto de recibo',
    icon: ListChecks, group: 'Liquidación', searchable: true, filters: ['recibo_id'],
    fields: [
      fk('recibo_id', 'Recibo'),
      fk('concepto_id', 'Concepto', false),
      { name: 'secuencia', label: 'Secuencia', type: 'number' },
      { name: 'codigo', label: 'Código', type: 'text', required: true },
      { name: 'descripcion', label: 'Descripción', type: 'text', required: true },
      { name: 'columna', label: 'Columna', type: 'select', defaultValue: 'REMUNERATIVO', options: opt('REMUNERATIVO', 'NO_REMUNERATIVO', 'DESCUENTO', 'CONTRIBUCION', 'AUXILIAR') },
      { name: 'unidad', label: 'Unidad', type: 'decimal' },
      { name: 'importe', label: 'Importe', type: 'decimal' },
      { name: 'condicion', label: 'Condición', type: 'checkbox', hideInTable: true },
      { name: 'warning', label: 'Advertencia', type: 'checkbox', hideInTable: true },
      { name: 'error', label: 'Error', type: 'checkbox', hideInTable: true },
      { name: 'message', label: 'Mensaje', type: 'text', hideInTable: true },
    ],
  },
  {
    key: 'tramos-retroactivos', path: 'tramos-retroactivos', permission: 'liquidaciones', title: 'Tramos retroactivos', singular: 'Tramo',
    icon: Route, group: 'Liquidación', filters: ['liquidacion_id'],
    fields: [
      fk('liquidacion_id', 'Liquidación'),
      fk('beneficiario_id', 'Beneficiario', false),
      { name: 'fecha_desde', label: 'Desde', type: 'date', required: true },
      { name: 'fecha_hasta', label: 'Hasta', type: 'date', required: true },
      { name: 'haber_mensual', label: 'Haber mensual', type: 'decimal', defaultValue: '0' },
      { name: 'meses', label: 'Meses', type: 'decimal', defaultValue: '0' },
      { name: 'importe', label: 'Importe', type: 'decimal', defaultValue: '0' },
      { name: 'sac', label: 'SAC', type: 'decimal', defaultValue: '0' },
      { name: 'descripcion', label: 'Descripción', type: 'text', hideInTable: true },
    ],
  },
];

export const RESOURCE_BY_KEY: Record<string, ResourceDef> =
  Object.fromEntries(RESOURCES.map((r) => [r.key, r]));

/** Recursos con entrada propia en el menú lateral (los dependientes se navegan desde su padre) */
export const NAV_RESOURCE_KEYS = [
  'causantes', 'liquidaciones', 'conceptos', 'tablas', 'parametros', 'formulas-auxiliares', 'grupos-concepto',
];
