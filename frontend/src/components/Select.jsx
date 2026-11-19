import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown } from 'lucide-react';

export default function Select({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKeyDown = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((isOpen) => !isOpen)}
        aria-haspopup="true"
        aria-expanded={open}
        className="cursor-pointer flex w-full items-center justify-between gap-6 border-b border-line py-2.5 text-left transition-colors duration-300 hover:border-ink/40 focus-visible:border-teal-600 focus-visible:outline-none dark:hover:border-bone/40 dark:focus-visible:border-teal-400"
      >
        <span className="truncate">
          <span className="mr-2 text-sm italic text-muted">{label}</span>
          {selected.label}
        </span>
        <ChevronDown
          className={`size-4 shrink-0 text-muted transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
          strokeWidth={1.25}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.ul
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="absolute left-0 z-30 mt-2 max-h-72 w-full overflow-y-auto sm:left-auto sm:right-0 sm:min-w-56 border border-line bg-ivory py-2 shadow-[0_24px_48px_-24px_rgba(0,0,0,0.35)] dark:bg-[#181818]"
          >
            {options.map((option) => {
              const isSelected = option.value === value;
              return (
                <li key={option.value}>
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                    }}
                    className={`cursor-pointer flex w-full items-center justify-between gap-4 px-4 py-2 text-left text-sm transition-colors hover:bg-ink/5 focus-visible:bg-ink/5 focus-visible:outline-none dark:hover:bg-bone/5 dark:focus-visible:bg-bone/5 ${
                      isSelected ? 'text-teal-700 dark:text-teal-400' : ''
                    }`}
                  >
                    {option.label}
                    {isSelected && <Check className="size-3.5" strokeWidth={1.5} />}
                  </button>
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
