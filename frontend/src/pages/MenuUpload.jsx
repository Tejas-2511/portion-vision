import { useState } from "react";

export default function MenuUpload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [loading, setLoading] = useState(false);

  function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
    setExtractedText("");
  }

  async function handleOCR() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("image", selectedFile);

    setLoading(true);
    setExtractedText("");

    try {
      const res = await fetch("http://localhost:5000/ocr", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error("OCR request failed");
      }

      const data = await res.json();

      if (!data.menuItems) {
        throw new Error("Invalid response from backend");
      }

      setExtractedText(data.menuItems.join("\n"));
    } catch (err) {
      console.error(err);
      alert("OCR failed. Check backend.");
    }

    setLoading(false);
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center p-6 text-slate-800">
      <h2 className="mb-8 text-3xl font-bold text-emerald-600">
        Upload Mess Menu
      </h2>

      <div className="mb-6 w-full">
        <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-300 bg-emerald-50 hover:bg-emerald-100 transition-colors">
          <span className="text-emerald-700 font-medium">Click to select image</span>
          <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
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

      <button
        onClick={handleOCR}
        disabled={loading || !selectedFile}
        className={`mb-8 w-full rounded-xl py-3 text-lg font-bold text-white shadow-md transition-all 
          ${loading || !selectedFile
            ? "bg-slate-400 cursor-not-allowed"
            : "bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98]"
          }
        `}
      >
        {loading ? "Extracting..." : "Extract Text (OCR)"}
      </button>

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
