import { type ButtonHTMLAttributes, type ReactNode, useEffect, useId, useRef, useState } from 'react';
import { CAPABILITY_LABEL, STATUS_LABEL } from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { RunStatus } from '../lib/types.ts';

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

type Variant = 'primary' | 'secondary' | 'danger' | 'quiet';
const VARIANT: Record<Variant, string> = {
  primary: 'bg-action text-white hover:bg-action-strong border border-action',
  secondary: 'bg-panel text-ink border border-rule-strong hover:border-ink-faint',
  danger: 'bg-panel text-fail border border-fail/50 hover:bg-fail-tint',
  quiet: 'bg-transparent text-action border border-transparent hover:bg-action-tint',
};

export function Button({
  variant = 'secondary',
  busy,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || busy}
      className={cx(
        'inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT[variant],
        className,
      )}
    >
      {busy ? <span aria-hidden className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" /> : null}
      {children}
    </button>
  );
}

const STATUS_TONE: Record<RunStatus, string> = {
  planned: 'bg-void-tint text-ink-soft',
  ready: 'bg-action-tint text-action-strong',
  running: 'bg-pending-tint text-pending',
  awaiting_human: 'bg-pending-tint text-pending',
  submitted: 'bg-action-tint text-action-strong',
  evaluating: 'bg-action-tint text-action-strong',
  completed: 'bg-pass-tint text-pass',
  failed: 'bg-fail-tint text-fail',
  invalidated: 'bg-void-tint text-void line-through',
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={cx('inline-block whitespace-nowrap rounded-sm px-1.5 py-0.5 text-xs font-medium', STATUS_TONE[status])}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function OutcomeBadge({ success, status }: { success: boolean | null; status: RunStatus }) {
  if (status !== 'completed') return <span className="text-ink-faint">—</span>;
  return success ? (
    <span className="inline-block rounded-sm bg-pass-tint px-1.5 py-0.5 text-xs font-semibold text-pass">Passed</span>
  ) : (
    <span className="inline-block rounded-sm bg-fail-tint px-1.5 py-0.5 text-xs font-semibold text-fail">Did not pass</span>
  );
}

export function CapabilityBadge({ status }: { status: string }) {
  const tone =
    status === 'supported'
      ? 'bg-pass-tint text-pass'
      : status === 'requires_authentication'
        ? 'bg-pending-tint text-pending'
        : 'bg-void-tint text-ink-soft';
  return (
    <span className={cx('inline-block rounded-sm px-1.5 py-0.5 text-xs font-medium', tone)}>{CAPABILITY_LABEL[status] ?? status}</span>
  );
}

export function PageHeader({
  title,
  crumbs = [],
  actions,
  children,
}: {
  title: string;
  crumbs?: { label: string; to?: string }[];
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="mb-6 border-b border-rule pb-4">
      {crumbs.length ? (
        <nav aria-label="Breadcrumb" className="mb-1 text-sm text-ink-faint">
          <ol className="flex flex-wrap gap-1">
            {crumbs.map((c, i) => (
              <li key={c.label} className="flex gap-1">
                {c.to ? (
                  <Link to={c.to} className="hover:text-action hover:underline">
                    {c.label}
                  </Link>
                ) : (
                  <span>{c.label}</span>
                )}
                {i < crumbs.length - 1 ? <span aria-hidden>/</span> : null}
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      {children ? <div className="mt-2 max-w-[78ch] text-ink-soft">{children}</div> : null}
    </header>
  );
}

export function Section({
  title,
  aside,
  children,
  className,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx('mb-8', className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-1.5">
        <h2 className="text-base font-semibold">{title}</h2>
        {aside ? <div className="text-sm text-ink-faint">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div role="status" className="rounded border border-dashed border-rule-strong bg-panel px-5 py-6">
      <p className="font-medium">{title}</p>
      {children ? <div className="mt-1 max-w-[70ch] text-sm text-ink-soft">{children}</div> : null}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded border border-fail/40 bg-fail-tint px-4 py-3 text-sm text-fail">
      <p className="font-medium">{error.message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="mt-1 underline">
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <p role="status" className="text-sm text-ink-faint">
      {label}…
    </p>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'warn' | 'success'; children: ReactNode }) {
  const cls =
    tone === 'warn'
      ? 'border-pending/40 bg-pending-tint text-ink'
      : tone === 'success'
        ? 'border-pass/40 bg-pass-tint text-ink'
        : 'border-action/30 bg-action-tint text-ink';
  return <div className={cx('rounded border px-4 py-2.5 text-sm', cls)}>{children}</div>;
}

/** Explanatory tooltip for research metrics; keyboard accessible. */
export function Info({ children, label = 'What does this mean?' }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-block align-middle">
      <button
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="ml-1 inline-flex size-4 items-center justify-center rounded-full border border-rule-strong text-[10px] font-semibold text-ink-faint"
      >
        ?
      </button>
      {open ? (
        <span
          role="tooltip"
          id={id}
          className="absolute left-0 top-6 z-20 w-72 rounded border border-rule-strong bg-panel p-2.5 text-xs font-normal leading-relaxed text-ink shadow-lg"
        >
          {children}
        </span>
      ) : null}
    </span>
  );
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
      {hint && !error ? <span className="mt-1 block text-xs text-ink-faint">{hint}</span> : null}
      {error ? <span className="mt-1 block text-xs text-fail">{error}</span> : null}
    </label>
  );
}

export const inputClass =
  'w-full rounded border border-rule-strong bg-panel px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:border-action';

export function Stat({ label, value, note }: { label: ReactNode; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="min-w-[8rem]">
      <dt className="text-sm text-ink-soft">{label}</dt>
      <dd className="tabular text-2xl font-semibold leading-tight">{value}</dd>
      {note ? <dd className="text-xs text-ink-faint">{note}</dd> : null}
    </div>
  );
}

export function Hash({ value, n = 12 }: { value: string | null | undefined; n?: number }) {
  if (!value) return <span className="text-ink-faint">—</span>;
  return (
    <code title={value} className="font-mono text-xs text-ink-soft">
      {value.slice(0, n)}
    </code>
  );
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? 'Copied' : label}
    </Button>
  );
}

/** Confirmation dialog for consequential actions. Optional reason input. */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  danger,
  reason,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  reason?: { label: string; minLength: number };
  onConfirm: (reason: string) => Promise<void> | void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      setText('');
      setError(undefined);
      d.showModal();
    }
    if (!open && d.open) d.close();
  }, [open]);
  const tooShort = reason ? text.trim().length < reason.minLength : false;
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-[min(32rem,92vw)] rounded border border-rule-strong bg-panel p-0 text-ink backdrop:bg-ink/40"
    >
      <form
        method="dialog"
        className="p-5"
        onSubmit={async (e) => {
          e.preventDefault();
          if (tooShort) return;
          setBusy(true);
          try {
            await onConfirm(text.trim());
            onClose();
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="mt-2 text-sm text-ink-soft">{body}</div>
        {reason ? (
          <div className="mt-3">
            <Field label={reason.label} hint={`At least ${reason.minLength} characters; stored in the audit log.`}>
              <textarea className={inputClass} rows={3} value={text} onChange={(e) => setText(e.target.value)} />
            </Field>
          </div>
        ) : null}
        {error ? <p className="mt-2 text-sm text-fail">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant={danger ? 'danger' : 'primary'} busy={busy} disabled={tooShort}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </dialog>
  );
}

export function Table({ children, caption }: { children: ReactNode; caption?: string }) {
  return (
    <div className="overflow-x-auto rounded border border-rule bg-panel">
      <table className="w-full border-collapse text-sm [&_td]:border-t [&_td]:border-rule [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-medium [&_th]:text-ink-soft [&_thead]:bg-paper">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}
