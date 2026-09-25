import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { Button } from './controls';

interface ToolSurfaceDockProps {
  id: string;
  title: string;
  description: string;
  triggerRef: React.RefObject<HTMLButtonElement>;
  onClose: () => void;
  children: React.ReactNode;
}

export function ToolSurfaceDock({ id, title, description, triggerRef, onClose, children }: ToolSurfaceDockProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [id]);

  const close = () => {
    onClose();
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  return (
    <aside
      id={id}
      role="region"
      aria-labelledby={`${id}-title`}
      className="a-floating a-enter h-fit min-w-0 rounded-[var(--a-radius)] border border-[var(--a-line-strong)] p-5"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && event.currentTarget.contains(document.activeElement)) {
          event.preventDefault();
          close();
        }
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="a-page-kicker">Herramienta activa</div>
          <h2 id={`${id}-title`} ref={headingRef} tabIndex={-1} className="a-tool-heading mt-2 text-lg font-bold text-[var(--a-text)] outline-none">
            {title}
          </h2>
          <p className="a-meta mt-1">{description}</p>
        </div>
        <Button variant="quiet" onClick={close} aria-label={`Cerrar ${title}`} className="shrink-0 px-2.5">
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
      <div className="mt-5">{children}</div>
    </aside>
  );
}
