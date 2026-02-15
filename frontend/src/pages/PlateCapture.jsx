import { useState } from "react";
import { useNavigate } from "react-router-dom";

// PlateCapture page - Handles plate image capture for portion analysis
export default function PlateCapture() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);

  const navigate = useNavigate();

  // Handle file selection
  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
  }

  // Navigate to analysis page with captured image data
  function handleCapture() {
    if (selectedFile && preview) {
      navigate("/analysis", {
        state: {
          imageFile: selectedFile,
          imagePreview: preview
        }
      });
    }
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

        <div className="mb-8 space-y-4">
          {/* Camera Capture Button */}
          <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-400 bg-emerald-50 hover:bg-emerald-100 transition-colors">
            <svg className="w-12 h-12 text-emerald-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="text-emerald-700 font-medium">📸 Take Photo</span>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>

          {/* File Upload Button */}
          <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-300 bg-emerald-50 hover:bg-emerald-100 transition-colors">
            <svg className="w-12 h-12 text-emerald-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-emerald-700 font-medium">📁 Choose from Gallery</span>
            <input
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
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
