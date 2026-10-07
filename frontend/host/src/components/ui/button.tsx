import { cn } from '../../lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
}

// Neo-brutalist button (docs/design-better-ui.md §4.11): ink outline, hard shadow, lift on hover,
// press on click. Text on a fill is always text-on-fill. Focus comes from the global :focus-visible rule.
export function Button({ className, variant = 'default', size = 'md', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 font-display font-bold',
        'disabled:bg-surface-muted disabled:text-ink-muted',
        variant === 'default' && 'nb-box nb-press bg-accent text-on-fill',
        variant === 'secondary' && 'nb-box nb-press bg-accent-2 text-on-fill',
        variant === 'outline' && 'nb-box nb-press bg-surface text-ink hover:bg-surface-muted',
        variant === 'ghost' && 'border-2 border-transparent text-ink hover:border-line hover:bg-surface-muted',
        variant === 'destructive' && 'nb-box nb-press bg-danger text-on-fill',
        size === 'sm' && 'px-3 py-1.5 text-sm',
        size === 'md' && 'px-4 py-2 text-base',
        size === 'lg' && 'px-6 py-3 text-lg',
        className
      )}
      {...props}
    />
  );
}
