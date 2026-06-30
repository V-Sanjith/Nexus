'use client';

interface StatusConsoleProps {
  statusText: string;
  activeCategory: string;
  productCount: number;
  isActive: boolean;
}

export function StatusConsole({ statusText, activeCategory, productCount, isActive }: StatusConsoleProps) {
  return (
    <div className="absolute top-3 left-3 right-3 z-[25] flex items-center justify-between px-3.5 py-2 rounded-lg border border-slate-800/50 bg-slate-950/85 backdrop-blur-md font-mono text-[10px] text-slate-400 select-none">
      <div className="flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full transition-colors duration-300 ${
            isActive ? 'bg-purple-500 animate-ping' : 'bg-indigo-500/70'
          }`}
        />
        <span className="text-white/90 font-bold truncate max-w-[200px] sm:max-w-none">
          {statusText}
        </span>
      </div>
      <div className="hidden sm:flex items-center gap-3 text-slate-500">
        <span>
          CAT: <span className="text-indigo-400 font-bold">{activeCategory.toUpperCase()}</span>
        </span>
        <span className="text-slate-700">|</span>
        <span>
          PRODUCTS: <span className="text-slate-300">{productCount}</span>
        </span>
      </div>
    </div>
  );
}
