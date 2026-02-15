import { useState } from "react";
import { useApp } from "../contexts/AppContext";
import { useErrorHandler } from "../hooks/useErrorHandler";
import { validateImageFile } from "../utils/validation";
import api from "../services/api";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";

// MenuUpload page - Handles mess menu image upload and OCR processing
export default function MenuUpload() {
  const { setTodaysMenu } = useApp();
  const { error, handleError, clearError, retry, canRetry } = useErrorHandler();

  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [loading, setLoading] = useState(false);

  // Handle file selection from gallery or camera
  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    clearError();

    try {
      validateImageFile(file);
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setExtractedText("");
    } catch (err) {
      handleError(err);
    }
  }

  // Process menu image with OCR to extract text
  async function handleOCR() {
    if (!selectedFile) return;

    setLoading(true);
    setExtractedText("");
    clearError();

    try {
      const data = await api.uploadMenuImage(selectedFile);

      if (!data.menuItems) {
        throw new Error("Invalid response from backend");
      }

      const menuText = data.menuItems.join("\n");
      setExtractedText(menuText);

      // Save menu to context (which auto-syncs to localStorage)
      setTodaysMenu({
        items: data.menuItems,
        text: menuText,
        date: new Date().toISOString()
      });
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center p-6 text-slate-800">
      <h2 className="mb-8 text-3xl font-bold text-emerald-600">
        Upload Mess Menu
      </h2>

      {error && (
        <div className="mb-6 w-full">
          <ErrorMessage
            error={error}
            onRetry={() => retry(handleOCR)}
            canRetry={canRetry}
          />
        </div>
      )}

      <div className="mb-6 w-full space-y-4">
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

      {preview && (
        <div className="mb-6 w-full overflow-hidden rounded-xl shadow-md">
          <img
            src={preview}
            alt="menu preview"
            className="w-full object-cover"
          />
        </div>
      )}

      <Button
        onClick={handleOCR}
        disabled={!selectedFile}
        loading={loading}
        className="mb-8 w-full"
      >
        Extract Text (OCR)
      </Button>

      {extractedText && (
        <div className="w-full rounded-xl bg-white p-6 shadow-lg border border-slate-100">
          <h3 className="mb-3 text-lg font-bold text-slate-700">Extracted Text</h3>
          <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm text-slate-600 font-mono border border-slate-200">
            {extractedText}
          </pre>
        </div>
      )}
    </div>
  );
}
