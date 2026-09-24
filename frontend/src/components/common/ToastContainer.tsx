import { useToast, Toast, ToastType } from '@/context/ToastContext';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const toastConfig: Record<ToastType, { bg: string; icon: typeof CheckCircle }> = {
  success: { bg: 'bg-emerald-600',  icon: CheckCircle    },
  error:   { bg: 'bg-red-600',      icon: XCircle        },
  warning: { bg: 'bg-amber-500',    icon: AlertTriangle  },
  info:    { bg: 'bg-blue-600',     icon: Info           },
};

function ToastItem({ toast }: { toast: Toast }) {
  const { removeToast } = useToast();
  const { bg, icon: Icon } = toastConfig[toast.type];

  return (
    <div
      className={`
        ${bg} text-white
        px-4 py-3 rounded-lg shadow-lg
        flex items-center gap-3
        min-w-[280px] max-w-sm
        animate-slide-in-right
      `}
    >
      <Icon className="w-4 h-4 shrink-0 opacity-90" />
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 opacity-70 hover:opacity-100 transition-opacity ml-1"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export default function ToastContainer() {
  const { toasts } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
