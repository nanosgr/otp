import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Calculator, Download, FileText, Lock, LockOpen } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useToast } from '@/context/ToastContext';
import { useConfirm } from '@/lib/hooks/useConfirm';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import Button from '@/components/common/Button';
import ErrorAlert from '@/components/common/ErrorAlert';
import ProtectedComponent from '@/components/common/ProtectedComponent';

interface Tramo { desde: string; hasta: string; descripcion: string | null; haber_mensual: string; meses: string; importe: string; es_sac: boolean }
interface Concepto { codigo: string; descripcion: string; columna: string; secuencia: number | null; unidad: string | null; importe: string }
interface CargoTotal { secuencia: number; porcentaje: string; total: string }
interface Persona { apellido: string; nombre: string; dni?: string | null; parentesco?: string; porcentaje?: string | number; art37?: boolean }
interface Recibo {
  numero: number;
  beneficiario: Persona | null;
  rango: { desde: string; hasta: string } | null;
  haber_mensual_actual: string | null;
  tramos: Tramo[];
  credito: string;
  descuentos: { codigo: string; descripcion: string; importe: string }[];
  total_descuentos: string;
  liquido: string;
  conceptos_haber: Concepto[];
  cargos: CargoTotal[];
  haber_ponderado: string | null;
}
interface Resumen {
  liquidacion: {
    id: number; periodo: string; tipo: string; estado: string; fecha_desde: string | null; fecha_hasta: string | null;
    total_credito: string; total_debitos: string; total_liquido: string; calculada_at: string | null; anticipo_importe: string;
  };
  causante: Persona & { expediente: string | null };
  recibos: Recibo[];
}

const money = (v: string | number) =>
  new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v));
const fecha = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

function guardar(blob: Blob, nombre: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
}

export default function LiquidacionPlanilla() {
  const { id } = useParams();
  const { success, error: showError } = useToast();
  const { confirm, ConfirmationDialog } = useConfirm();
  const [data, setData] = useState<Resumen | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await apiClient.get<Resumen>(`/liquidaciones/${id}/resumen`));
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar la liquidación');
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const accion = async (path: string, ok: string) => {
    setBusy(true);
    try {
      setData(await apiClient.post<Resumen>(`/liquidaciones/${id}/${path}`));
      setError('');
      success(ok);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'No se pudo completar la acción');
    } finally {
      setBusy(false);
    }
  };

  const cerrar = async () => {
    const ok = await confirm({
      title: 'Cerrar liquidación',
      message: 'Una liquidación cerrada no puede modificarse ni recalcularse (solo un administrador puede reabrirla). ¿Cerrar?',
      confirmText: 'Cerrar', cancelText: 'Cancelar', variant: 'danger',
    });
    if (ok) await accion('cerrar', 'Liquidación cerrada');
  };

  const descargar = async (ext: 'xlsx' | 'pdf') => {
    try {
      guardar(await apiClient.download(`/liquidaciones/${id}/planilla.${ext}`), `liquidacion_${data?.liquidacion.periodo}_${id}.${ext}`);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'No se pudo descargar');
    }
  };

  const liq = data?.liquidacion;
  const abierta = liq?.estado === 'ABIERTA';

  return (
    <DashboardLayout title="Planilla de liquidación">
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link to="/liquidaciones" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">← Liquidaciones</Link>
          {liq && (
            <div className="flex flex-wrap gap-2">
              <ProtectedComponent permissions={['liquidaciones:update']}>
                {abierta && (
                  <Button size="sm" onClick={() => accion('calcular', 'Liquidación calculada')} disabled={busy}>
                    <Calculator className="w-4 h-4 mr-1" />{liq.calculada_at ? 'Recalcular' : 'Calcular'}
                  </Button>
                )}
                {abierta && liq.calculada_at && (
                  <Button size="sm" variant="secondary" onClick={cerrar} disabled={busy}><Lock className="w-4 h-4 mr-1" />Cerrar</Button>
                )}
              </ProtectedComponent>
              <ProtectedComponent permissions={['liquidaciones:delete']}>
                {!abierta && (
                  <Button size="sm" variant="secondary" onClick={() => accion('reabrir', 'Liquidación reabierta')} disabled={busy}>
                    <LockOpen className="w-4 h-4 mr-1" />Reabrir
                  </Button>
                )}
              </ProtectedComponent>
              {liq.calculada_at && (
                <>
                  <Button size="sm" variant="ghost" onClick={() => descargar('xlsx')}><Download className="w-4 h-4 mr-1" />Excel</Button>
                  <Button size="sm" variant="ghost" onClick={() => descargar('pdf')}><FileText className="w-4 h-4 mr-1" />PDF</Button>
                </>
              )}
            </div>
          )}
        </div>

        {error && <ErrorAlert message={error} />}

        {data && liq && (
          <>
            <Card title={`${liq.tipo.toUpperCase()} · período ${liq.periodo} · ${liq.estado}`}>
              <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div><dt className="text-xs text-stone-500">Causante</dt><dd>{data.causante.apellido}, {data.causante.nombre}</dd></div>
                <div><dt className="text-xs text-stone-500">DNI / Expte.</dt><dd>{data.causante.dni} / {data.causante.expediente ?? '—'}</dd></div>
                <div><dt className="text-xs text-stone-500">Rango</dt><dd>{liq.fecha_desde ? fecha(liq.fecha_desde) : '—'} al {liq.fecha_hasta ? fecha(liq.fecha_hasta) : '—'}</dd></div>
                <div><dt className="text-xs text-stone-500">Anticipo percibido</dt><dd>{money(liq.anticipo_importe)}</dd></div>
                <div><dt className="text-xs text-stone-500">Crédito</dt><dd className="font-medium">{money(liq.total_credito)}</dd></div>
                <div><dt className="text-xs text-stone-500">Débitos</dt><dd className="font-medium">{money(liq.total_debitos)}</dd></div>
                <div><dt className="text-xs text-stone-500">Líquido</dt><dd className="font-semibold text-emerald-700 dark:text-emerald-400">{money(liq.total_liquido)}</dd></div>
                <div><dt className="text-xs text-stone-500">Calculada</dt><dd>{liq.calculada_at ? new Date(liq.calculada_at).toLocaleString('es-AR') : 'Sin calcular'}</dd></div>
              </dl>
              {!liq.calculada_at && (
                <p className="mt-4 text-sm text-stone-500">Todavía no se calculó. Verificá que el causante tenga su cargo (clase, adicionales, antigüedad){liq.tipo === 'pension' ? ' y beneficiarios' : ''} y presioná Calcular.</p>
              )}
            </Card>

            {data.recibos.map((r) => {
              const persona = r.beneficiario ?? data.causante;
              return (
                <Card key={r.numero} title={`Recibo ${r.numero}: ${persona.apellido}, ${persona.nombre}${r.beneficiario ? ` (${r.beneficiario.parentesco} ${Number(r.beneficiario.porcentaje)}%${r.beneficiario.art37 ? ' + art. 37' : ''})` : ''}`}>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs uppercase text-stone-500 border-b border-stone-200 dark:border-stone-800">
                          <th className="py-2 pr-4 text-right">Nominal</th><th className="py-2 pr-4">Desde</th><th className="py-2 pr-4">Hasta</th>
                          <th className="py-2 pr-4 text-right">Meses</th><th className="py-2 text-right">Totales</th>
                        </tr>
                      </thead>
                      <tbody>
                        {r.tramos.map((t, i) => (
                          <tr key={i} className={t.es_sac ? 'bg-stone-50 dark:bg-stone-800/40 italic' : ''}>
                            <td className="py-1 pr-4 text-right tabular-nums">{money(t.es_sac ? Number(t.haber_mensual) / 2 : t.haber_mensual)}</td>
                            <td className="py-1 pr-4">{t.es_sac ? 'SAC' : fecha(t.desde)}</td>
                            <td className="py-1 pr-4">{t.es_sac ? t.descripcion : fecha(t.hasta)}</td>
                            <td className="py-1 pr-4 text-right tabular-nums">{t.es_sac ? '' : Number(t.meses).toFixed(2)}</td>
                            <td className="py-1 text-right tabular-nums">{money(t.importe)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="border-t border-stone-200 dark:border-stone-800">
                        <tr className="font-medium"><td colSpan={4} className="pt-2 text-right pr-4">Subtotal crédito</td><td className="pt-2 text-right tabular-nums">{money(r.credito)}</td></tr>
                        {r.descuentos.filter((d) => !(d.codigo === 'ANTICIPO' && Number(d.importe) === 0)).map((d) => (
                          <tr key={d.codigo}><td colSpan={4} className="text-right pr-4">{d.descripcion}</td><td className="text-right tabular-nums">{money(d.importe)}</td></tr>
                        ))}
                        <tr className="font-medium"><td colSpan={4} className="text-right pr-4">Total débito</td><td className="text-right tabular-nums">{money(r.total_descuentos)}</td></tr>
                        <tr className="font-semibold text-base"><td colSpan={4} className="pt-1 text-right pr-4">Total crédito líquido</td><td className="pt-1 text-right tabular-nums">{money(r.liquido)}</td></tr>
                      </tfoot>
                    </table>
                  </div>
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm text-stone-600 dark:text-stone-400">
                      Detalle del haber mensual vigente ({r.conceptos_haber.length} conceptos{r.cargos.length > 1 ? `, ${r.cargos.length} secuencias` : ''})
                    </summary>
                    {r.cargos.length > 1 && (
                      <table className="mt-2 mb-1 text-xs">
                        <thead><tr className="text-left text-stone-500"><th className="pr-4">Secuencia</th><th className="pr-4 text-right">Haber del cargo</th><th className="pr-4 text-right">% secuencia</th><th className="text-right">Aporte</th></tr></thead>
                        <tbody>
                          {r.cargos.map((c) => (
                            <tr key={c.secuencia}>
                              <td className="pr-4">{c.secuencia}</td><td className="pr-4 text-right tabular-nums">{money(c.total)}</td>
                              <td className="pr-4 text-right tabular-nums">{Number(c.porcentaje).toFixed(2)}%</td>
                              <td className="text-right tabular-nums">{money(Number(c.total) * Number(c.porcentaje) / 100)}</td>
                            </tr>
                          ))}
                          <tr className="font-medium border-t border-stone-200 dark:border-stone-800"><td colSpan={3} className="pr-4 text-right">Haber ponderado</td><td className="text-right tabular-nums">{money(r.haber_ponderado ?? 0)}</td></tr>
                        </tbody>
                      </table>
                    )}
                    <table className="mt-2 min-w-full text-xs">
                      <tbody>
                        {r.conceptos_haber.map((c, i) => (
                          <tr key={`${c.secuencia}-${c.codigo}-${i}`} className="border-b border-stone-100 dark:border-stone-800">
                            <td className="py-1 pr-3 text-stone-500">{c.secuencia ?? 'Beneficio'}</td>
                            <td className="pr-3 font-mono">{c.codigo}</td><td className="pr-3">{c.descripcion}</td>
                            <td className="pr-3 text-stone-500">{c.columna}</td><td className="text-right tabular-nums">{money(c.importe)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                </Card>
              );
            })}
          </>
        )}
      </div>
      <ConfirmationDialog />
    </DashboardLayout>
  );
}
