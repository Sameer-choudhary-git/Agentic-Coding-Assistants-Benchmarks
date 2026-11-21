import type { ReactNode } from 'react';
import { Link, useRouter } from '../lib/router.tsx';
import { cx } from './ui.tsx';

const NAV: { to: string; label: string; match: RegExp }[] = [
  { to: '/', label: 'Dashboard', match: /^\/$/ },
  { to: '/tasks', label: 'Benchmark tasks', match: /^\/tasks/ },
  { to: '/experiments', label: 'Experiments', match: /^\/experiments/ },
  { to: '/runs', label: 'Runs', match: /^\/runs/ },
  { to: '/results', label: 'Results', match: /^\/results/ },
  { to: '/assistants', label: 'Assistants', match: /^\/assistants/ },
  { to: '/golden', label: 'Golden dataset', match: /^\/golden/ },
  { to: '/evidence', label: 'Literature evidence', match: /^\/evidence/ },
  { to: '/exports', label: 'Exports and data', match: /^\/exports/ },
];

export function Layout({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const pathname = path.split('?')[0];
  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-panel focus:p-2">
        Skip to content
      </a>
      <aside className="border-b border-rule bg-panel md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r">
        <div className="px-5 pb-3 pt-5">
          <Link to="/" className="block">
            <span className="block text-[15px] font-semibold leading-snug">Agentic Coding Assistants</span>
            <span className="block text-sm text-ink-faint">Comparative evaluation platform</span>
          </Link>
        </div>
        <nav aria-label="Main" className="overflow-x-auto px-3 pb-3 md:pb-0">
          <ul className="flex gap-1 md:block md:space-y-0.5">
            {NAV.map((item) => {
              const active = item.match.test(pathname);
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    aria-current={active ? 'page' : undefined}
                    className={cx(
                      'block whitespace-nowrap rounded px-2.5 py-1.5 text-sm',
                      active ? 'bg-action-tint font-medium text-action-strong' : 'text-ink-soft hover:bg-paper hover:text-ink',
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <p className="hidden px-5 pt-6 text-xs leading-relaxed text-ink-faint md:block">
          Three benchmarks: an 18-task custom Python suite, a 12-issue SWE-bench Verified pilot and the golden set's Verified tasks. Results are reported per benchmark.
        </p>
      </aside>
      <main id="main" className="min-w-0 px-4 py-6 md:px-10 md:py-8">
        <div className="mx-auto max-w-[1200px]">{children}</div>
      </main>
    </div>
  );
}
