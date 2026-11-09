import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../hooks/useApp";
import { useErrorHandler } from "../hooks/useErrorHandler";
import { validateImageFile } from "../utils/validation";
import api from "../services/api";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";

// MenuUpload page - Handles mess menu image upload and OCR processing
export default function MenuUpload() {
  const navigate = useNavigate();
  const { setTodaysMenu } = useApp();
  const { error, handleError, clearError, retry, canRetry } = useErrorHandler();

  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [loading, setLoading] = useState(false);
  const [updateDatabase, setUpdateDatabase] = useState(false);

  useEffect(() => {
    api.getOcrDbUpdateSetting()
      .then(res => {
        if (res && typeof res.allowOcrDbUpdate === 'boolean') {
          setUpdateDatabase(res.allowOcrDbUpdate);
        }
      })
      .catch(err => console.warn("Failed to fetch OCR DB setting:", err));
  }, []);
  const [syncStatus, setSyncStatus] = useState(null);

  // Handle file selection from gallery or camera
  // Validates file type and size before setting state
  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    clearError();

    try {
      validateImageFile(file);
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setExtractedText("");
      setSyncStatus(null);
    } catch (err) {
      handleError(err);
    }
  }

  // Process menu image with OCR to extract text
  // 1. Uploads image to backend via API (with updateDatabase toggle)
  // 2. Receives extracted menu items
  // 3. Updates global state (AppContext) with new menu
  async function handleOCR() {
    if (!selectedFile) return;

    setLoading(true);
    setExtractedText("");
    setSyncStatus(null);
    clearError();

    try {
      const data = await api.uploadMenuImage(selectedFile, updateDatabase);

      if (!data.items) {
        throw new Error("Invalid response from backend");
      }

      const menuText = data.items.join("\n");
      setExtractedText(menuText);
      setSyncStatus({
        dbUpdated: data.dbUpdated,
        addedCount: data.addedCount || 0,
        matchedCount: data.matchedCount || 0,
        dbUpdateEnabled: data.dbUpdateEnabled
      });

      // Save menu to context (which auto-syncs to localStorage)
      setTodaysMenu({
        items: data.items,
        text: menuText,
        date: data.date,
      });
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center p-6 text-slate-800 relative">
      <button 
        onClick={() => navigate(-1)}
        className="absolute top-8 left-6 text-slate-400 hover:text-slate-600 transition-colors"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
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

      {/* Database Auto-Update Toggle */}
      <div className="mb-6 w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-slate-300">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${updateDatabase ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-slate-800 text-sm">Update Food Database</span>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${updateDatabase ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
                  {updateDatabase ? "Auto-Save" : "Read-Only"}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {updateDatabase 
                  ? "Unrecognized menu items will be permanently added to the database."
                  : "Database is protected. Unrecognized items will use fallback nutrition for this session."}
              </p>
            </div>
          </div>

          <label className="relative inline-flex items-center cursor-pointer ml-3">
            <input 
              type="checkbox" 
              checked={updateDatabase}
              onChange={(e) => setUpdateDatabase(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
          </label>
        </div>
      </div>

      <Button
        onClick={handleOCR}
        disabled={!selectedFile}
        loading={loading}
        className="mb-8 w-full"
      >
        Extract Menu
      </Button>

      {syncStatus && (
        <div className={`mb-6 w-full rounded-xl p-4 border text-sm ${syncStatus.dbUpdated ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-sky-50 border-sky-200 text-sky-800'}`}>
          <div className="flex items-start space-x-2">
            <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="font-semibold">
                {syncStatus.dbUpdated
                  ? `💾 Added ${syncStatus.addedCount} new food items to the database!`
                  : `🛡️ Database Read-Only: ${syncStatus.matchedCount} items matched to existing database.`}
              </p>
              <p className="text-xs mt-1 opacity-90">
                {syncStatus.dbUpdated
                  ? "Items were saved with estimated macros and can now be recognized across future scans."
                  : "Database was not modified. Similar foods were resolved via fuzzy matching."}
              </p>
            </div>
          </div>
        </div>
      )}

      {extractedText && (
        <div className="w-full rounded-xl bg-white p-6 shadow-lg border border-slate-100">
          <h3 className="mb-3 text-lg font-bold text-slate-700">Extracted Menu Items</h3>
          <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm text-slate-600 font-mono border border-slate-200">
            {extractedText}
          </pre>
        </div>
      )}
    </div>
  );
}
