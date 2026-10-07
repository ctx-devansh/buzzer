import { cn } from '../../lib/utils';

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

// Placeholder colour and the focus outline come from the preset's base rules (§4.3).
export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'w-full border-2 border-line bg-surface px-3 py-2 text-ink',
        className
      )}
      {...props}
    />
  );
}
