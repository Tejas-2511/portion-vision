import { useLocation } from "react-router-dom";

// Analysis page - Displays portion analysis results
export default function Analysis() {
  const location = useLocation();
  const { imageFile, imagePreview } = location.state || {};

  return (
    <div className="min-h-screen bg-slate-50 pb-10">
      <div className="bg-emerald-600 px-6 py-4 text-white shadow-md">
        <h1 className="text-xl font-bold">Portion Analysis</h1>
      </div>

      <div className="mx-auto max-w-lg space-y-6 p-6">

        {/* Card 1 - Recommended Portion */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <h2 className="mb-3 text-lg font-bold text-slate-700">Recommended Portion</h2>
          <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium">
            Recommended Portion Placeholder
          </div>
        </div>

        {/* Card 2 - Captured Plate Image */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <h2 className="mb-3 text-lg font-bold text-slate-700">Captured Plate</h2>
          <div className="overflow-hidden rounded-xl bg-slate-100">
            {imagePreview ? (
              <img
                src={imagePreview}
                alt="Captured plate"
                className="w-full h-auto object-cover"
              />
            ) : (
              <div className="flex h-32 items-center justify-center text-slate-500 font-medium">
                No image captured
              </div>
            )}
          </div>
          {imageFile && (
            <p className="mt-2 text-sm text-slate-500">
              File: {imageFile.name} ({(imageFile.size / 1024).toFixed(1)} KB)
            </p>
          )}
        </div>

        {/* Card 3 - Portion Comparison */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <h2 className="mb-3 text-lg font-bold text-slate-700">Portion Comparison</h2>
          <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium">
            Portion Comparison Result Placeholder
          </div>
        </div>

      </div>
    </div>
  );
}
