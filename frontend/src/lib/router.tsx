import { createContext, type MouseEvent, type ReactNode, useContext, useEffect, useState } from 'react';

/** A small history-API router: enough for this app without another dependency. */
const RouterContext = createContext<{ path: string; navigate: (to: string) => void }>({
  path: '/',
  navigate: () => undefined,
});

export function RouterProvider({ children, initialPath }: { children: ReactNode; initialPath?: string }) {
  const [path, setPath] = useState(
    initialPath ?? (typeof window !== 'undefined' ? window.location.pathname + window.location.search : '/'),
  );
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname + window.location.search);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  const navigate = (to: string) => {
    window.history.pushState({}, '', to);
    setPath(to);
    window.scrollTo(0, 0);
  };
  return <RouterContext.Provider value={{ path, navigate }}>{children}</RouterContext.Provider>;
}

export const useRouter = () => useContext(RouterContext);

export function matchRoute(pattern: string, path: string): Record<string, string> | null {
  const pathname = path.split('?')[0].replace(/\/+$/, '') || '/';
  const p = pattern.split('/');
  const a = pathname.split('/');
  if (p.length !== a.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i += 1) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

export function useQuery(): URLSearchParams {
  const { path } = useRouter();
  return new URLSearchParams(path.split('?')[1] ?? '');
}

export function Link({
  to,
  children,
  className,
  ...rest
}: {
  to: string;
  children: ReactNode;
  className?: string;
  title?: string;
  'aria-current'?: 'page' | undefined;
}) {
  const { navigate } = useRouter();
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(to);
  };
  return (
    <a href={to} onClick={onClick} className={className} {...rest}>
      {children}
    </a>
  );
}
