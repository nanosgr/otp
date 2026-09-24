import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  fullWidth?: boolean;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, fullWidth = true, className = '', ...props }, ref) => {
    return (
      <div className={fullWidth ? 'w-full' : ''}>
        {label && (
          <label className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            px-3 py-2 text-sm rounded-md border transition-colors duration-150
            bg-white dark:bg-stone-900
            text-stone-900 dark:text-stone-100
            placeholder:text-stone-400 dark:placeholder:text-stone-600
            focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error
              ? 'border-red-400 dark:border-red-600'
              : 'border-stone-200 dark:border-stone-700 hover:border-stone-300 dark:hover:border-stone-600'
            }
            ${fullWidth ? 'w-full' : ''}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p className="mt-1 text-xs text-red-500 dark:text-red-400">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
