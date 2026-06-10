export function BrandingHeader() {
  return (
    <div className="flex flex-col items-center mb-4">
      <img src="/logo.svg" alt="PAVE Dark Factory logo" className="w-10 h-10 mb-2" />
      <span className="text-xl font-semibold text-[var(--text-primary)]">PAVE Dark Factory</span>
      <span className="text-sm text-[var(--text-secondary)]">
        Agentic CargoWise work from PAVE tasks
      </span>
    </div>
  );
}
