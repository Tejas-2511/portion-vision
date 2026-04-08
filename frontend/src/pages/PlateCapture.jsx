import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";

// PlateCapture page — Image capture with quality guidance
// Updated to reflect CV pipeline quality gate (#7): blur + tilt validation
export default function PlateCapture() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
  }

  function handleCapture() {
    if (selectedFile && preview) {
      navigate("/analysis", {
        state: {
          imageFile: selectedFile,
          imagePreview: preview,
          mealType: location.state?.mealType,
        },
      });
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-emerald-600 px-6 py-4 text-white shadow-md flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="text-white hover:text-emerald-100 transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-xl font-bold">Plate Photo</h1>
      </div>

      <div className="mx-auto max-w-lg p-6">

        {/* Preview / Guidelines */}
        <div className="relative mb-6 flex h-80 w-full items-center justify-center overflow-hidden rounded-2xl bg-slate-200 shadow-inner">
          {preview ? (
            <img
              src={preview}
              alt="plate preview"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex flex-col items-start justify-center p-6 text-slate-700 bg-emerald-50/50 h-full w-full">
              <h3 className="text-sm font-black text-emerald-800 mb-4 uppercase tracking-widest flex items-center gap-2">
                <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                AI Camera Rules
              </h3>
              <ul className="text-xs space-y-3 text-left pl-2">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">■</span>
                  <span>
                    <strong className="text-slate-800">Top-Down Only:</strong>{" "}
                    Hold your phone <em>flat directly above</em> the plate : the AI
                    rejects angled shots automatically.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">■</span>
                  <span>
                    <strong className="text-slate-800">Tap to Focus First:</strong>{" "}
                    Tap the plate on your screen before shooting. Blurry images are
                    rejected : the AI needs sharp food edges to measure depth.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">■</span>
                  <span>
                    <strong className="text-slate-800">One Light Source:</strong>{" "}
                    Avoid harsh phone-shadows cutting across the food. Overhead
                    room lighting works best : no flash.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">■</span>
                  <span>
                    <strong className="text-slate-800">Full Plate in Frame:</strong>{" "}
                    The whole plate must be visible. The AI detects the plate rim to
                    calibrate real-world scale.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">■</span>
                  <span>
                    <strong className="text-slate-800">Keep Items Separated:</strong>{" "}
                    Don&apos;t dump foods into one pile : the AI segments each item
                    inside its own compartment separately.
                  </span>
                </li>
              </ul>
            </div>
          )}
        </div>

        {/* Quality Note Banner */}
        {!preview && (
          <div className="mb-4 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-800 flex items-start gap-2">
            <span className="text-amber-500 mt-0.5 text-base">⚠</span>
            <span>
              Images that are <strong>blurry</strong> or taken at an{" "}
              <strong>angle</strong> will be automatically rejected with a
              retake prompt. This protects measurement accuracy.
            </span>
          </div>
        )}

        {/* Camera / Gallery Buttons */}
        <div className="mb-8 space-y-4">
          <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-400 bg-emerald-50 hover:bg-emerald-100 transition-colors">
            <svg className="w-12 h-12 text-emerald-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="text-emerald-700 font-medium">📸 Take Photo</span>
            <input
              id="plate-camera-input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>

          <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-300 bg-emerald-50 hover:bg-emerald-100 transition-colors">
            <svg className="w-12 h-12 text-emerald-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-emerald-700 font-medium">📁 Choose from Gallery</span>
            <input
              id="plate-gallery-input"
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>
        </div>

        <button
          id="plate-capture-submit"
          onClick={handleCapture}
          disabled={!selectedFile}
          className={`w-full rounded-xl py-4 text-lg font-bold text-white shadow-lg transition-all
            ${!selectedFile
              ? "bg-slate-400 opacity-50 cursor-not-allowed"
              : "bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98]"
            }
          `}
        >
          Analyse Plate
        </button>
      </div>
    </div>
  );
}
