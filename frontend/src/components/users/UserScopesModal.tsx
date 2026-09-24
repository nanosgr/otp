import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, Crosshair } from 'lucide-react';
import Modal from '@/components/common/Modal';
import Button from '@/components/common/Button';
import Input from '@/components/common/Input';
import ErrorAlert from '@/components/common/ErrorAlert';
import { userService } from '@/lib/api/services';
import { useToast } from '@/context/ToastContext';
import { User, UserScope } from '@/types';

interface Props {
  user: User | null;
  onClose: () => void;
}

/**
 * Gestiona los valores de alcance (user_scopes) de un usuario: pares
 * (dimensión, valor) como `warehouse = norte`. Alimentan las reglas de permiso
 * con scope = "por atributo".
 */
export default function UserScopesModal({ user, onClose }: Props) {
  const { success, error: showError } = useToast();
  const [rows, setRows] = useState<UserScope[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const load = useCallback(async (userId: number) => {
    setIsLoading(true);
    setFormError('');
    try {
      const res = await userService.getScopes(userId);
      setRows(res.items);
    } catch {
      showError('No se pudieron cargar los alcances');
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    if (user) load(user.id);
  }, [user, load]);

  if (!user) return null;

  const updateRow = (index: number, patch: Partial<UserScope>) => {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  };

  const addRow = () => setRows((prev) => [...prev, { dimension: '', value: '' }]);
  const removeRow = (index: number) => setRows((prev) => prev.filter((_, i) => i !== index));

  const handleSave = async () => {
    const cleaned = rows
      .map((r) => ({ dimension: r.dimension.trim(), value: r.value.trim() }))
      .filter((r) => r.dimension || r.value);
    if (cleaned.some((r) => !r.dimension || !r.value)) {
      setFormError('Cada fila necesita dimensión y valor.');
      return;
    }
    setIsSaving(true);
    setFormError('');
    try {
      const res = await userService.setScopes(user.id, cleaned);
      setRows(res.items);
      success(`Alcances de "${user.username}" actualizados`);
      onClose();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Error al guardar los alcances');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={!!user}
      onClose={onClose}
      title={`Alcances de datos — ${user.username}`}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSave} disabled={isSaving || isLoading}>
            {isSaving ? 'Guardando...' : 'Guardar'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <ErrorAlert message={formError} />
        <p className="text-xs text-stone-500 dark:text-stone-400 flex items-start gap-2">
          <Crosshair className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Cada fila ubica al usuario en una <strong>dimensión</strong> (ej.{' '}
            <code className="font-mono">warehouse</code>) con un <strong>valor</strong> (ej.{' '}
            <code className="font-mono">norte</code>). Un rol con un permiso de alcance
            «por atributo» sobre esa dimensión sólo verá las filas que coincidan.
          </span>
        </p>

        {isLoading ? (
          <p className="text-sm text-stone-400 py-6 text-center">Cargando...</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-stone-400 py-6 text-center">
            Sin alcances definidos — el usuario no verá filas de recursos con alcance «por atributo».
          </p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_1fr_auto] gap-2 px-1 text-xs font-medium text-stone-500 dark:text-stone-400">
              <span>Dimensión</span>
              <span>Valor</span>
              <span className="w-8" />
            </div>
            {rows.map((row, index) => (
              <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2 items-center">
                <Input
                  value={row.dimension}
                  placeholder="warehouse"
                  onChange={(e) => updateRow(index, { dimension: e.target.value })}
                />
                <Input
                  value={row.value}
                  placeholder="norte"
                  onChange={(e) => updateRow(index, { value: e.target.value })}
                />
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  className="p-2 rounded-md text-stone-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
                  title="Quitar"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        <Button variant="secondary" size="sm" onClick={addRow} className="flex items-center gap-1.5">
          <Plus className="w-3.5 h-3.5" />
          Agregar alcance
        </Button>
      </div>
    </Modal>
  );
}
