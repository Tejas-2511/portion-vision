export default function Analysis() {
  return (
    <div className="min-h-screen bg-slate-50 pb-10">
      <div className="bg-emerald-600 px-6 py-4 text-white shadow-md">
        <h1 className="text-xl font-bold">Portion Analysis</h1>
      </div>

      <div className="mx-auto max-w-lg space-y-6 p-6">

        {/* Card 1 */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium">
            Recommended Portion Placeholder
          </div>
        </div>

        {/* Card 2 */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium">
            Captured Plate Image Placeholder
          </div>
        </div>

        {/* Card 3 */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium">
            Portion Comparison Result Placeholder
          </div>
        </div>

      </div>
    </div>
  );
}
