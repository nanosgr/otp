import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Calculator, Plus, Save, Trash2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useToast } from '@/context/ToastContext';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import Button from '@/components/common/Button';
import ErrorAlert from '@/components/common/ErrorAlert';
import {
  ETIQUETAS_COMPUTO, TablaComputo, TablaZona, cod, money, type Computo, type Zona,
} from '@/components/prevision/ProyectadaContent';

type Row = Record<string, unknown> & { id: number };
interface Ficha {
  causante: Row;
  computo: { filas: Row[]; totales: Computo | null };
  cargos: (Row & { encasillamiento: Row[] })[];
  zonas: Row[];
  zona: Zona | null;
  liquidaciones: { id: number; periodo: string; tipo: string; modalidad: string; estado: string; total_liquido: string; calculada_at: string | null }[];
}

type Tipo = 'text' | 'number' | 'decimal' | 'date' | 'select';
interface Campo { name: string; label: string; type?: Tipo; options?: string[]; hint?: string; ancho?: string }

const TABS = [
  ['expediente', '1. Expediente'], ['computo', '2. Cómputo'], ['imputacion', '3. Imputación'],
  ['encasillamiento', '4. Encasillamiento'], ['zonas', 'Zonas'], ['liquidaciones', 'Liquidaciones'],
] as const;
type Tab = (typeof TABS)[number][0];

const EXPEDIENTE: Campo[] = [
  { name: 'expediente', label: 'Expediente' }, { name: 'apellido', label: 'Apellido' }, { name: 'nombre', label: 'Nombre' },
  { name: 'dni', label: 'DNI' }, { name: 'cuil', label: 'CUIL' },
  { name: 'escalafon', label: 'Escalafón', type: 'select', options: ['policia', 'penitenciario'], hint: 'Define el juego de reglas' },
  { name: 'tipo_personal', label: 'Tipo de personal', type: 'select', options: ['subalterno', 'superior'], hint: 'Tabla de % de retiro y divisor de zona (25/30)' },
  { name: 'grado', label: 'Cargo / grado' }, { name: 'cuerpo', label: 'Cuerpo' }, { name: 'condicion', label: 'Condición' },
  { name: 'familia', label: 'Familia' }, { name: 'fecha_ingreso', label: 'Ingreso', type: 'date' },
  { name: 'fecha_renuncia_condicionada', label: 'Renuncia condicionada', type: 'date' },
  { name: 'cuadro_servicio_desde', label: 'Cuadro de servicio desde', type: 'date' },
  { name: 'cuadro_servicio_hasta', label: 'Cuadro de servicio hasta', type: 'date' },
];
const IMPUTACION: Campo[] = [
  { name: 'grado', label: 'Cargo / grado' }, { name: 'clase', label: 'Clase', type: 'number' },
  { name: 'caracter', label: 'Carácter' }, { name: 'jurisdiccion', label: 'Jurisdicción' },
  { name: 'unidad_organizativa', label: 'Unidad organizativa' }, { name: 'finalidad', label: 'Finalidad' }, { name: 'funcion', label: 'Función' },
  { name: 'regimen_salarial', label: 'R.S.', hint: '36 policía · 37 penitenciaría' }, { name: 'agrupamiento', label: 'A.', hint: '1 seguridad · 2 administrativo' },
  { name: 'tramo', label: 'T.', type: 'select', options: ['', '01', '02'], hint: '01 subalterno · 02 superior' }, { name: 'subtramo', label: 'ST.' },
  { name: 'anios_antiguedad', label: 'Años de antigüedad (080)', type: 'decimal', hint: 'Si el encasillamiento trae 080, manda el encasillamiento' },
  { name: 'porcentaje_retiro', label: '% retiro manual', type: 'decimal', hint: '0 = tabla por antigüedad final del cómputo' },
  { name: 'zona_clase', label: 'Clase base de zona', type: 'number', hint: '0 = sin zona' }, { name: 'zona_cargo_base', label: 'Cargo base de zona' },
  { name: 'zona_porcentaje', label: '% zona manual', type: 'decimal', hint: 'Se usa solo si no hay destinos cargados' },
];
const COMPUTO: Campo[] = [
  { name: 'concepto', label: 'Concepto', type: 'select', options: Object.keys(ETIQUETAS_COMPUTO), ancho: 'w-56' },
  { name: 'anios', label: 'Años', type: 'number', ancho: 'w-20' }, { name: 'meses', label: 'Meses', type: 'number', ancho: 'w-20' },
  { name: 'dias', label: 'Días', type: 'number', ancho: 'w-20' }, { name: 'observacion', label: 'Observación' },
];
const ZONAS: Campo[] = [
  { name: 'dependencia', label: 'Dependencia' }, { name: 'porcentaje_zona', label: '% zona', type: 'decimal', ancho: 'w-24' },
  { name: 'fecha_desde', label: 'Desde', type: 'date', ancho: 'w-40' }, { name: 'fecha_hasta', label: 'Hasta', type: 'date', ancho: 'w-40' },
];
const ENCASILLAMIENTO: Campo[] = [
  { name: 'codigo', label: 'Código', ancho: 'w-20' }, { name: 'descripcion', label: 'Concepto' },
  { name: 'modo', label: 'Tipo', type: 'select', options: ['valor', '$', '-'], ancho: 'w-24' },
  { name: 'valor', label: 'Valor (% o cant.)', type: 'decimal', ancho: 'w-32' },
];

const control = `px-2 py-1.5 text-sm rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900
  text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 w-full`;

const aTexto = (v: unknown) => (v === null || v === undefined ? '' : String(v));
/** La API devuelve los Numeric como "55.0500": se muestran sin ceros de más ("55.05"). */
function normal(campos: Campo[], r: Record<string, unknown>) {
  const out = { ...r };
  for (const c of campos) {
    const v = r[c.name];
    if (c.type === 'decimal' && v !== null && v !== undefined && v !== '' && !Number.isNaN(Number(v))) out[c.name] = String(Number(v));
  }
  return out;
}

function Control({ campo, valor, onChange }: { campo: Campo; valor: unknown; onChange: (v: string) => void }) {
  if (campo.type === 'select') {
    return (
      <select className={control} value={aTexto(valor)} onChange={(e) => onChange(e.target.value)} aria-label={campo.label}>
        {campo.options!.map((o) => <option key={o} value={o}>{ETIQUETAS_COMPUTO[o] ?? (o || '—')}</option>)}
      </select>
    );
  }
  const type = campo.type === 'date' ? 'date' : campo.type === 'number' || campo.type === 'decimal' ? 'number' : 'text';
  return (
    <input className={`${control} ${type === 'number' ? 'text-right tabular-nums' : ''}`} type={type} aria-label={campo.label}
      step={campo.type === 'decimal' ? 'any' : undefined} value={aTexto(valor)} onChange={(e) => onChange(e.target.value)} />
  );
}

/** Convierte lo editado al payload de la API: '' → null, números como número o string decimal. */
function payload(campos: Campo[], datos: Record<string, unknown>) {
  const out: Record<string, unknown> = {};
  for (const c of campos) {
    if (!(c.name in datos)) continue;
    const v = datos[c.name];
    if (v === '' || v === undefined) out[c.name] = c.type === 'number' ? 0 : null;
    else if (c.type === 'number') out[c.name] = Number(v);
    else out[c.name] = v;
  }
  return out;
}

function Formulario({ campos, inicial, onGuardar }: { campos: Campo[]; inicial: Row; onGuardar: (d: Record<string, unknown>) => Promise<void> }) {
  const base = useMemo(() => normal(campos, inicial), [campos, inicial]);
  const [datos, setDatos] = useState<Record<string, unknown>>(base);
  const [busy, setBusy] = useState(false);
  useEffect(() => setDatos(base), [base]);
  const cambiado = campos.some((c) => aTexto(datos[c.name]) !== aTexto(base[c.name]));
  return (
    <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setBusy(true); try { await onGuardar(payload(campos, datos)); } finally { setBusy(false); } }}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {campos.map((c) => (
          <label key={c.name} className="block">
            <span className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">{c.label}</span>
            <Control campo={c} valor={datos[c.name]} onChange={(v) => setDatos((d) => ({ ...d, [c.name]: v }))} />
            {c.hint && <span className="mt-1 block text-xs text-stone-500">{c.hint}</span>}
          </label>
        ))}
      </div>
      <Button type="submit" size="sm" disabled={!cambiado || busy}><Save className="w-4 h-4 mr-1" />Guardar</Button>
    </form>
  );
}

/** Tabla editable en línea: cada fila se guarda o elimina por separado; la última fila sirve para agregar. */
function FilasEditables({ campos, filas, nueva, onGuardar, onBorrar, onAgregar }: {
  campos: Campo[]; filas: Row[]; nueva: Record<string, unknown>;
  onGuardar: (id: number, d: Record<string, unknown>) => Promise<void>; onBorrar: (id: number) => Promise<void>;
  onAgregar: (d: Record<string, unknown>) => Promise<void>;
}) {
  const [borradores, setBorradores] = useState<Record<string, Record<string, unknown>>>({});
  useEffect(() => setBorradores({}), [filas]);
  const valor = (key: string, base: Record<string, unknown>, campo: string) => (borradores[key]?.[campo] ?? base[campo]);
  const editar = (key: string, campo: string, v: string) => setBorradores((b) => ({ ...b, [key]: { ...b[key], [campo]: v } }));
  const fila = (key: string, base: Record<string, unknown>, acciones: React.ReactNode) => (
    <tr key={key} className="border-b border-stone-100 dark:border-stone-800 align-top">
      {campos.map((c) => (
        <td key={c.name} className={`py-1.5 pr-2 ${c.ancho ?? ''}`}>
          <Control campo={c} valor={valor(key, base, c.name)} onChange={(v) => editar(key, c.name, v)} />
        </td>
      ))}
      <td className="py-1.5 whitespace-nowrap">{acciones}</td>
    </tr>
  );
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-stone-500 border-b border-stone-200 dark:border-stone-800">
            {campos.map((c) => <th key={c.name} className="py-2 pr-2 font-medium">{c.label}</th>)}<th />
          </tr>
        </thead>
        <tbody>
          {filas.map((r) => fila(String(r.id), normal(campos, r), (
            <>
              <Button size="sm" variant="ghost" aria-label="Guardar fila" disabled={!borradores[String(r.id)]}
                onClick={() => onGuardar(r.id, payload(campos, borradores[String(r.id)] ?? {}))}><Save className="w-4 h-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Eliminar fila" onClick={() => onBorrar(r.id)}><Trash2 className="w-4 h-4 text-red-600" /></Button>
            </>
          )))}
          {fila('nueva', nueva, (
            <Button size="sm" variant="secondary" aria-label="Agregar fila"
              onClick={() => onAgregar(payload(campos, { ...nueva, ...borradores.nueva }))}><Plus className="w-4 h-4 mr-1" />Agregar</Button>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const modoDe = (r: Row) => (!r.aplica ? '-' : r.valor === null || r.valor === undefined || r.valor === '' ? '$' : 'valor');
/** Traduce "valor / $ / -" a los campos `valor` y `aplica` del encasillamiento. */
function encPayload(d: Record<string, unknown>) {
  const { modo, ...resto } = d;
  if (modo === '-') return { ...resto, aplica: false, valor: null };
  if (modo === '$') return { ...resto, aplica: true, valor: null };
  return modo === 'valor' ? { ...resto, aplica: true } : resto;
}

export default function CausanteFicha() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { success, error: showError } = useToast();
  const [ficha, setFicha] = useState<Ficha | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('expediente');
  const [cargoIdx, setCargoIdx] = useState(0);
  const [nuevaLiq, setNuevaLiq] = useState({ periodo: '', asunto: 'RENUNCIA CONDICIONADA' });

  const load = useCallback(async () => {
    try {
      setFicha(await apiClient.get<Ficha>(`/causantes/${id}/ficha`));
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar la ficha');
    }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const hacer = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      success(ok);
      await load();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'No se pudo guardar');
    }
  };

  const cargo = ficha?.cargos[cargoIdx];
  const encFilas = useMemo(() => (cargo?.encasillamiento ?? []).map((r) => ({ ...r, modo: modoDe(r) })), [cargo]);
  const c = ficha?.causante;

  const crearLiquidacion = async () => {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(nuevaLiq.periodo)) {
      showError('Indicá el mes base salarial como AAAA-MM');
      return;
    }
    try {
      const liq = await apiClient.post<{ id: number }>('/liquidaciones/', {
        causante_id: Number(id), periodo: nuevaLiq.periodo, tipo: 'retiro', modalidad: 'proyectada', asunto: nuevaLiq.asunto || null,
      });
      await apiClient.post(`/liquidaciones/${liq.id}/calcular`);
      success('Liquidación proyectada calculada');
      navigate(`/liquidaciones/${liq.id}/planilla`);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'No se pudo crear la liquidación');
      await load();
    }
  };

  return (
    <DashboardLayout title="Ficha del causante">
      <div className="space-y-5">
        <Link to="/causantes" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">← Causantes</Link>
        {error && <ErrorAlert message={error} />}
        {ficha && c && (
          <>
            <Card>
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-stone-800 dark:text-stone-100">{aTexto(c.apellido)}, {aTexto(c.nombre)}</h2>
                  <p className="text-sm text-stone-500">
                    DNI {aTexto(c.dni)} · {aTexto(c.grado) || 'sin cargo'} · {aTexto(c.escalafon)} · {aTexto(c.tipo_personal)}
                    {c.expediente ? ` · ${aTexto(c.expediente)}` : ''}
                  </p>
                </div>
                <dl className="flex gap-6 text-sm">
                  <div><dt className="text-xs text-stone-500">Antigüedad final</dt><dd className="font-semibold tabular-nums">{ficha.computo.totales?.antiguedad_final ?? '—'}</dd></div>
                  <div><dt className="text-xs text-stone-500">Zona aplicada</dt><dd className="font-semibold tabular-nums">{ficha.zona ? `${Number(ficha.zona.porcentaje_aplicado)}%` : '—'}</dd></div>
                </dl>
              </div>
            </Card>

            <div role="tablist" className="flex flex-wrap gap-1 border-b border-stone-200 dark:border-stone-800">
              {TABS.map(([k, label]) => (
                <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                  className={`px-3 py-2 text-sm -mb-px border-b-2 transition-colors ${tab === k
                    ? 'border-blue-600 text-blue-700 dark:text-blue-400 font-medium'
                    : 'border-transparent text-stone-500 hover:text-stone-800 dark:hover:text-stone-200'}`}>
                  {label}
                </button>
              ))}
            </div>

            {tab === 'expediente' && (
              <Card title="1. Datos del expediente">
                <Formulario campos={EXPEDIENTE} inicial={c}
                  onGuardar={(d) => hacer(() => apiClient.put(`/causantes/${id}`, d), 'Datos del expediente guardados')} />
              </Card>
            )}

            {tab === 'computo' && (
              <Card title="2. Cómputo de servicios">
                <FilasEditables campos={COMPUTO} filas={ficha.computo.filas}
                  nueva={{ concepto: 'cuadro_servicio', anios: 0, meses: 0, dias: 0, observacion: '' }}
                  onGuardar={(rid, d) => hacer(() => apiClient.put(`/computo-servicios/${rid}`, d), 'Fila guardada')}
                  onBorrar={(rid) => hacer(() => apiClient.delete(`/computo-servicios/${rid}`), 'Fila eliminada')}
                  onAgregar={(d) => hacer(() => apiClient.post('/computo-servicios/', { ...d, causante_id: Number(id), orden: ficha.computo.filas.length }), 'Fila agregada')} />
                <p className="mt-2 text-xs text-stone-500">Año de 360 días y mes de 30. Las suspensiones se cargan en positivo y se restan. Antigüedad final = años de “Corresponde” + 1 si los meses son 6 o más; define el % de retiro.</p>
                {ficha.computo.totales && <div className="mt-5"><TablaComputo computo={ficha.computo.totales} /></div>}
              </Card>
            )}

            {(tab === 'imputacion' || tab === 'encasillamiento') && ficha.cargos.length > 1 && (
              <div className="flex gap-2 text-sm">
                {ficha.cargos.map((cg, i) => (
                  <Button key={cg.id} size="sm" variant={i === cargoIdx ? 'primary' : 'ghost'} onClick={() => setCargoIdx(i)}>Secuencia {aTexto(cg.secuencia)}</Button>
                ))}
              </div>
            )}

            {(tab === 'imputacion' || tab === 'encasillamiento') && !cargo && (
              <Card>
                <p className="text-sm text-stone-500 mb-3">El causante no tiene un cargo cargado.</p>
                <Button size="sm" onClick={() => hacer(() => apiClient.post('/cargos/', { causante_id: Number(id), clase: 2 }), 'Cargo creado')}>
                  <Plus className="w-4 h-4 mr-1" />Crear cargo
                </Button>
              </Card>
            )}

            {tab === 'imputacion' && cargo && (
              <Card title="3. Imputación / codificación previsional">
                <Formulario campos={IMPUTACION} inicial={cargo}
                  onGuardar={(d) => hacer(() => apiClient.put(`/cargos/${cargo.id}`, d), 'Imputación guardada')} />
              </Card>
            )}

            {tab === 'encasillamiento' && cargo && (
              <Card title="4. Encasillamiento definitivo">
                <FilasEditables campos={ENCASILLAMIENTO} filas={encFilas} nueva={{ codigo: '', descripcion: '', modo: 'valor', valor: '' }}
                  onGuardar={(rid, d) => hacer(() => apiClient.put(`/encasillamiento/${rid}`, encPayload(d)), 'Ítem guardado')}
                  onBorrar={(rid) => hacer(() => apiClient.delete(`/encasillamiento/${rid}`), 'Ítem eliminado')}
                  onAgregar={(d) => hacer(() => apiClient.post('/encasillamiento/', {
                    ...encPayload({ ...d, codigo: String(d.codigo ?? '').replace(/^0+(?=\d)/, '') }), cargo_id: cargo.id, orden: encFilas.length,
                  }), 'Ítem agregado')} />
                <p className="mt-2 text-xs text-stone-500">
                  Código sin ceros a la izquierda ({cod('10')} → 10). Porcentajes de 0 a 100; clase (010) y antigüedad (080) como cantidad.
                  “$” liquida el monto fijo vigente y “-” no liquida el concepto. Con encasillamiento, solo se liquida lo encasillado.
                </p>
              </Card>
            )}

            {tab === 'zonas' && (
              <Card title="Anexo — zona inhóspita / desfavorable">
                <FilasEditables campos={ZONAS} filas={ficha.zonas} nueva={{ dependencia: '', porcentaje_zona: '', fecha_desde: '', fecha_hasta: '' }}
                  onGuardar={(rid, d) => hacer(() => apiClient.put(`/zonas/${rid}`, d), 'Destino guardado')}
                  onBorrar={(rid) => hacer(() => apiClient.delete(`/zonas/${rid}`), 'Destino eliminado')}
                  onAgregar={(d) => hacer(() => apiClient.post('/zonas/', { ...d, causante_id: Number(id) }), 'Destino agregado')} />
                <p className="mt-2 text-xs text-stone-500">% zona de 0 a 100 (p. ej. 20 para Alma Fuerte). Divisor: 25 subalterno, 30 superior. El total se redondea a entero y se paga desde el 1%. La base es la clase de zona del cargo (pestaña Imputación).</p>
                {ficha.zona && <div className="mt-5"><TablaZona zona={ficha.zona} cargoBase={cargo?.zona_cargo_base as string | null} /></div>}
              </Card>
            )}

            {tab === 'liquidaciones' && (
              <Card title="Liquidaciones">
                {ficha.liquidaciones.length > 0 && (
                  <table className="min-w-full text-sm mb-5">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wide text-stone-500 border-b border-stone-200 dark:border-stone-800">
                        <th className="py-2 pr-4 font-medium">Período</th><th className="py-2 pr-4 font-medium">Tipo</th><th className="py-2 pr-4 font-medium">Estado</th>
                        <th className="py-2 pr-4 font-medium text-right">Haber / líquido</th><th />
                      </tr>
                    </thead>
                    <tbody>
                      {ficha.liquidaciones.map((l) => (
                        <tr key={l.id} className="border-b border-stone-100 dark:border-stone-800">
                          <td className="py-1.5 pr-4">{l.periodo}</td><td className="pr-4">{l.tipo} · {l.modalidad}</td><td className="pr-4">{l.estado}</td>
                          <td className="pr-4 text-right tabular-nums">{l.calculada_at ? money(l.total_liquido) : 'sin calcular'}</td>
                          <td><Link className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline" to={`/liquidaciones/${l.id}/planilla`}>Planilla</Link></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="flex flex-wrap items-end gap-3">
                  <label className="block">
                    <span className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">Mes base salarial (AAAA-MM)</span>
                    <input className={`${control} w-36`} placeholder="2025-09" value={nuevaLiq.periodo}
                      onChange={(e) => setNuevaLiq((n) => ({ ...n, periodo: e.target.value }))} />
                  </label>
                  <label className="block">
                    <span className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">Asunto</span>
                    <input className={`${control} w-64`} value={nuevaLiq.asunto} onChange={(e) => setNuevaLiq((n) => ({ ...n, asunto: e.target.value }))} />
                  </label>
                  <Button size="sm" onClick={crearLiquidacion}><Calculator className="w-4 h-4 mr-1" />Nueva liquidación proyectada</Button>
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
