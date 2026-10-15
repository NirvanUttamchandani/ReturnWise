import type { ButtonHTMLAttributes, ReactNode } from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import type { ApiError, Tone } from "../lib/api";

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(" ");

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ children, className, as: Tag = "section", ...rest }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" } & React.HTMLAttributes<HTMLElement>) {
  return <Tag className={cx("rounded-xl border border-line bg-surface shadow-card", className)} {...rest}>{children}</Tag>;
}

export function CardHeader({ title, hint, right }: { title: string; hint?: string; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-3.5">
      <div>
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
      </div>
      {right}
    </div>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; loading?: boolean };
export function Button({ variant = "secondary", loading, disabled, className, children, ...rest }: BtnProps) {
  const styles = {
    primary: "bg-teal-600 text-white hover:bg-teal-700 border-transparent",
    secondary: "bg-surface text-ink border-line-strong hover:bg-paper",
    ghost: "bg-transparent text-muted border-transparent hover:bg-idle-bg hover:text-ink",
  }[variant];
  return (
    <button {...rest} disabled={disabled || loading} aria-busy={loading || undefined}
      className={cx("inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border px-3.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60", styles, className)}>
      {loading && <RefreshCw className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

const TONES: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok", warn: "bg-warn-bg text-warn", bad: "bg-bad-bg text-bad", info: "bg-info-bg text-info", idle: "bg-idle-bg text-idle",
};
const DOT: Record<Tone, string> = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", info: "bg-info", idle: "bg-idle" };

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", TONES[tone])}>
      <span className={cx("size-1.5 rounded-full", DOT[tone])} aria-hidden />{children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton h-4 w-full", className)} aria-hidden />;
}

export function LoadingBlock({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3 p-5">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-5 w-1/3" /><Skeleton /><Skeleton className="w-5/6" /><Skeleton className="w-2/3" />
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 grid size-10 place-items-center rounded-full bg-idle-bg text-muted"><Inbox className="size-5" aria-hidden /></div>
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "This could not be loaded" }: { error: ApiError; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-10 text-center">
      <div className="mb-3 grid size-10 place-items-center rounded-full bg-bad-bg text-bad"><AlertTriangle className="size-5" aria-hidden /></div>
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="mt-1 max-w-md text-sm text-muted">{error.message}</p>
      {onRetry && <Button className="mt-4" onClick={onRetry}><RefreshCw className="size-4" aria-hidden />Try again</Button>}
    </div>
  );
}

export function Notice({ tone, title, children }: { tone: Tone; title?: string; children: ReactNode }) {
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={cx("rounded-lg px-4 py-3 text-sm", TONES[tone])}>
      {title && <p className="font-semibold">{title}</p>}<div className={title ? "mt-0.5" : ""}>{children}</div>
    </div>
  );
}

export function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>
      {children}
      {error ? <p id={`${id}-error`} className="mt-1.5 text-sm text-bad">{error}</p>
        : hint ? <p id={`${id}-hint`} className="mt-1.5 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
export const inputCls = (invalid?: boolean) =>
  cx("w-full rounded-lg border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-teal-600", invalid ? "border-bad" : "border-line-strong");

export function Dl({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
      {items.map(([k, v]) => (<div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="text-ink">{v}</dd></div>))}
    </dl>
  );
}
