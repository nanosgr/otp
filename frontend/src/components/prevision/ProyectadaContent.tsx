/** Liquidación proyectada (renuncia/baja condicionada): puntos 1-5 y anexo de zona, como la planilla de la oficina. */
export type AMD = [number, number, number];
export interface Computo {
  filas: Record<string, AMD>;
  total_servicios: AMD; subtotal: AMD; corresponde: AMD; antiguedad_final: number;
}
export interface ZonaFila {
  desde: string; hasta: string; dependencia: string; dias: number; anios: string; zona: string; divisor: number;
  porc: string; anios_permanencia: number; porc_final: string;
}
export interface Zona { filas: ZonaFila[]; total: string; aplicado: string; porcentaje_aplicado: string; alcanza_minimo: boolean; divisor: number }
export interface EncItem { codigo: string; descripcion: string | null; valor: string | number | null; aplica: boolean }
export interface ConceptoHaber { codigo: string; descripcion: string; secuencia: number | null; unidad: string | null; unitario: string | null; importe: string }
export interface Proyectada {
  computo: Computo | null;
  imputacion: Record<string, string | number | null> | null;
  encasillamiento: EncItem[] | null;
  zona: Zona | null;
  porcentaje_retiro: string | null;
  total_haberes: string | null;
  haber_retiro: string | null;
}

export const money = (v: string | number) =>
  new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v));
export const fecha = (iso?: string | null) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '');
export const pct = (v: string | number | null | undefined, dec = 2) =>
  v === null || v === undefined || v === '' ? '' : `${Number(v).toLocaleString('es-AR', { minimumFractionDigits: dec, maximumFractionDigits: dec })}%`;
const CANTIDAD = new Set(['10', '80']);
export const cod = (c: string) => (/^\d+$/.test(c) ? c.padStart(3, '0') : c);

export const ETIQUETAS_COMPUTO: Record<string, string> = {
  cuadro_servicio: 'Período cuadro de servicio', hasta_renuncia: 'Hasta renuncia condicionada',
  servicios_adicionales: 'S. adicionales', beneficio_titulo: 'Beneficio por título', suspensiones: 'Suspensiones',
};

export function valorEncasillamiento(e: EncItem): string {
  if (!e.aplica) return '-';
  if (e.valor === null || e.valor === '') return '$';
  return CANTIDAD.has(e.codigo) ? String(Number(e.valor)) : pct(e.valor);
}

/** Filas del cómputo en el orden de la planilla, con los subtotales intercalados. */
export function filasComputo(c: Computo): { label: string; amd: AMD | null; total?: boolean; final?: number }[] {
  const f = (k: string) => (c.filas[k] && c.filas[k].some((x) => x) ? [{ label: ETIQUETAS_COMPUTO[k], amd: c.filas[k] }] : []);
  return [
    ...f('cuadro_servicio'), ...f('hasta_renuncia'), { label: 'Total servicios', amd: c.total_servicios, total: true },
    ...f('servicios_adicionales'), ...f('beneficio_titulo'), { label: 'Subtotal', amd: c.subtotal, total: true },
    ...f('suspensiones'), { label: 'Corresponde', amd: c.corresponde, total: true },
    { label: 'Antigüedad final', amd: null, total: true, final: c.antiguedad_final },
  ];
}

function ordenar(conceptos: ConceptoHaber[], enc: EncItem[]) {
  const idx = new Map(enc.map((e, i) => [e.codigo, { i, d: e.descripcion }]));
  return conceptos
    .filter((c) => c.secuencia !== null)
    .map((c) => ({ ...c, desc: idx.get(c.codigo)?.d || c.descripcion, i: idx.get(c.codigo)?.i ?? enc.length }))
    .sort((a, b) => a.i - b.i || Number(a.codigo) - Number(b.codigo));
}

const th = 'py-2 pr-4 text-left text-xs font-medium uppercase tracking-wide text-stone-500';
const td = 'py-1 pr-4';
const num = 'py-1 pr-4 text-right tabular-nums';

export function TablaComputo({ computo }: { computo: Computo }) {
  return (
    <table className="text-sm">
      <thead><tr className="border-b border-stone-200 dark:border-stone-800"><th className={th}>Concepto</th><th className={`${th} text-right`}>Años</th><th className={`${th} text-right`}>Meses</th><th className={`${th} text-right`}>Días</th></tr></thead>
      <tbody>
        {filasComputo(computo).map((f) => (
          <tr key={f.label} className={f.total ? 'font-medium' : ''}>
            <td className={td}>{f.label}</td>
            {f.amd ? f.amd.map((x, i) => <td key={i} className={num}>{x}</td>) : <><td className={`${num} text-emerald-700 dark:text-emerald-400 font-semibold`}>{f.final}</td><td /><td /></>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function TablaZona({ zona, cargoBase, base }: { zona: Zona; cargoBase?: string | null; base?: string | null }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-stone-200 dark:border-stone-800">
            {['Desde', 'Hasta', 'Dependencia', 'Días', 'Años', '% zona', `/${zona.divisor}`, 'Años perm.', 'Resultado'].map((h, i) => (
              <th key={h} className={`${th} ${i >= 3 && i !== 2 ? 'text-right' : ''}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {zona.filas.map((f, i) => (
            <tr key={i} className="border-b border-stone-100 dark:border-stone-800">
              <td className={td}>{fecha(f.desde)}</td><td className={td}>{fecha(f.hasta)}</td><td className={td}>{f.dependencia}</td>
              <td className={num}>{f.dias}</td><td className={num}>{Number(f.anios).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
              <td className={num}>{pct(Number(f.zona) * 100, 0)}</td><td className={num}>{pct(Number(f.porc) * 100)}</td>
              <td className={num}>{f.anios_permanencia}</td><td className={num}>{pct(Number(f.porc_final) * 100)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="font-medium"><td colSpan={8} className="pt-2 pr-4 text-right">Total</td><td className={`${num} pt-2`}>{pct(Number(zona.total) * 100)}</td></tr>
          <tr className="font-semibold">
            <td colSpan={8} className="pr-4 text-right">Porcentaje aplicado</td>
            <td className={num}>{zona.alcanza_minimo ? pct(zona.porcentaje_aplicado, 0) : '0%'}</td>
          </tr>
        </tfoot>
      </table>
      {!zona.alcanza_minimo && <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">No se incluye el suplemento zona: no alcanza el mínimo requerido del 1%.</p>}
      {(cargoBase || base) && (
        <p className="mt-2 text-xs text-stone-500">Cargo base: <span className="text-stone-700 dark:text-stone-300">{cargoBase || '—'}</span>{base ? <> · Base (clase): <span className="tabular-nums text-stone-700 dark:text-stone-300">{money(base)}</span></> : null}</p>
      )}
    </div>
  );
}

export default function ProyectadaContent({ pr, conceptos }: { pr: Proyectada; conceptos: ConceptoHaber[] }) {
  const filas = ordenar(conceptos, pr.encasillamiento ?? []);
  const base83 = filas.find((c) => c.codigo === '83')?.unitario;
  return (
    <div className="space-y-6">
      <section>
        <h4 className="mb-2 text-sm font-semibold text-stone-700 dark:text-stone-200">5. Liquidación proyectada</h4>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-stone-200 dark:border-stone-800">
                <th className={th}>Código</th><th className={th}>Concepto</th><th className={`${th} text-right`}>Base ($)</th>
                <th className={`${th} text-right`}>% / Cant.</th><th className={`${th} text-right`}>Importe ($)</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((c) => (
                <tr key={c.codigo} className="border-b border-stone-100 dark:border-stone-800">
                  <td className={`${td} font-mono text-stone-500`}>{cod(c.codigo)}</td>
                  <td className={td}>{c.desc}</td>
                  <td className={num}>{c.unitario === null ? '' : money(c.unitario)}</td>
                  <td className={num}>{c.unidad === null ? '' : CANTIDAD.has(c.codigo) ? Number(c.unidad) : pct(c.unidad)}</td>
                  <td className={num}>{money(c.importe)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-medium"><td colSpan={4} className="pt-2 pr-4 text-right">Total de haberes</td><td className={`${num} pt-2`}>{money(pr.total_haberes ?? 0)}</td></tr>
              <tr className="font-semibold text-base">
                <td colSpan={4} className="pr-4 text-right">Porcentaje de retiro {pct(pr.porcentaje_retiro, 0)} — haber de retiro</td>
                <td className={`${num} text-emerald-700 dark:text-emerald-400`}>{money(pr.haber_retiro ?? 0)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
      {pr.zona && (
        <section>
          <h4 className="mb-2 text-sm font-semibold text-stone-700 dark:text-stone-200">Anexo — zona inhóspita / desfavorable</h4>
          <TablaZona zona={pr.zona} cargoBase={pr.imputacion?.zona_cargo_base as string | null} base={base83} />
        </section>
      )}
      {pr.computo && (
        <details>
          <summary className="cursor-pointer text-sm text-stone-600 dark:text-stone-400">2. Cómputo de servicios (antigüedad final {pr.computo.antiguedad_final} años)</summary>
          <div className="mt-2"><TablaComputo computo={pr.computo} /></div>
        </details>
      )}
    </div>
  );
}
