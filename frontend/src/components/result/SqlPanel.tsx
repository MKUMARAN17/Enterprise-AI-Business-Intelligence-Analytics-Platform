/** Collapsible panel showing the guard-validated SQL the agents generated. */
import { Code2 } from 'lucide-react';
import { useState } from 'react';

import { Card } from '../ui/primitives';

export function SqlPanel({ sql }: { sql: string | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!sql) return null;
  return (
    <Card>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-5 py-3 text-left text-sm font-semibold text-slate-700 dark:text-slate-200"
      >
        <Code2 size={15} className="text-brand-600" />
        Generated SQL
        <span className="ml-auto text-xs font-normal text-slate-400">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <pre className="overflow-x-auto border-t border-slate-100 bg-slate-50 px-5 py-3 text-xs leading-relaxed text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
          <code>{sql}</code>
        </pre>
      )}
    </Card>
  );
}
