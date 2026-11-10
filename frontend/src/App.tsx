import { Layout } from './components/Layout.tsx';
import { EmptyState, PageHeader } from './components/ui.tsx';
import { matchRoute, useRouter } from './lib/router.tsx';
import { Assistants } from './pages/Assistants.tsx';
import { Dashboard } from './pages/Dashboard.tsx';
import { ExperimentDetail, Experiments, NewExperiment, Runs } from './pages/Experiments.tsx';
import { Evidence } from './pages/Evidence.tsx';
import { Exports } from './pages/Exports.tsx';
import { Results } from './pages/Results.tsx';
import { RunDetail } from './pages/RunDetail.tsx';
import { TaskDetail, Tasks } from './pages/Tasks.tsx';

export function Routes() {
  const { path } = useRouter();
  let m: Record<string, string> | null;
  if (matchRoute('/', path)) return <Dashboard />;
  if (matchRoute('/tasks', path)) return <Tasks />;
  if ((m = matchRoute('/tasks/:id', path))) return <TaskDetail key={m.id} id={m.id} />;
  if (matchRoute('/experiments', path)) return <Experiments />;
  if (matchRoute('/experiments/new', path)) return <NewExperiment />;
  if ((m = matchRoute('/experiments/:id', path))) return <ExperimentDetail key={m.id} id={m.id} />;
  if (matchRoute('/runs', path)) return <Runs />;
  if ((m = matchRoute('/runs/:id', path))) return <RunDetail key={m.id} id={m.id} />;
  if (matchRoute('/results', path)) return <Results />;
  if (matchRoute('/assistants', path)) return <Assistants />;
  if (matchRoute('/evidence', path)) return <Evidence />;
  if (matchRoute('/exports', path)) return <Exports />;
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState title="There is no page at this address">Use the navigation to go to the dashboard or the task list.</EmptyState>
    </>
  );
}

export function App() {
  return (
    <Layout>
      <Routes />
    </Layout>
  );
}
