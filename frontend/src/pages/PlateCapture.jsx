import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function PlateCapture() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);

  const navigate = useNavigate();

  function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
  }

  function handleCapture() {
    navigate("/analysis");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-emerald-600 px-6 py-4 text-white shadow-md">
        <h1 className="text-xl font-bold">Plate Photo</h1>
      </div>

      <div className="mx-auto max-w-lg p-6">
        <div className="relative mb-6 flex h-80 w-full items-center justify-center overflow-hidden rounded-2xl bg-slate-200 shadow-inner">
          {preview ? (
            <img
              src={preview}
              alt="plate preview"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex flex-col items-center text-slate-400">
              <span className="text-4xl mb-2">📷</span>
              <p>Camera Preview Placeholder</p>
            </div>
          )}
        </div>

        <div className="mb-8 flex justify-center">
          <label className="flex cursor-pointer items-center justify-center rounded-full bg-emerald-100 px-6 py-3 font-semibold text-emerald-700 transition hover:bg-emerald-200">
            <span>Select Image</span>
            <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
          </label>
        </div>

        <button
          onClick={handleCapture}
          disabled={!selectedFile}
          className={`w-full rounded-xl py-4 text-lg font-bold text-white shadow-lg transition-all 
            ${!selectedFile
              ? "bg-slate-400 opacity-50 cursor-not-allowed"
              : "bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98]"
            }
          `}
        >
          Capture Photo
        </button>
      </div>
    </div>
  );
}
