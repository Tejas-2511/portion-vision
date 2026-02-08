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
    <div
      style={{
        fontFamily: "Arial",
        padding: "20px",
        maxWidth: "600px",
        margin: "0 auto",
      }}
    >
      <h2 style={{ color: "green", marginBottom: "20px" }}>
        Upload Mess Menu
      </h2>

      <div style={{ marginBottom: "20px" }}>
        <input type="file" accept="image/*" onChange={handleFileChange} />
      </div>

      {preview && (
        <div style={{ marginBottom: "20px" }}>
          <img
            src={preview}
            alt="menu preview"
            style={{
              width: "100%",
              maxWidth: "400px",
              borderRadius: "10px",
              border: "1px solid #ccc",
            }}
          />
        </div>
      )}

      <button
        onClick={handleOCR}
        disabled={loading || !selectedFile}
        style={{
          backgroundColor: "green",
          color: "white",
          border: "none",
          padding: "12px 20px",
          borderRadius: "10px",
          cursor: loading || !selectedFile ? "not-allowed" : "pointer",
          marginBottom: "30px",
        }}
      >
        {loading ? "Extracting..." : "Extract Text (OCR)"}
      </button>

      <h3 style={{ marginBottom: "10px" }}>Extracted Text</h3>

      <pre
        style={{
          background: "#f0f0f0",
          padding: "12px",
          borderRadius: "8px",
          whiteSpace: "pre-wrap",
          minHeight: "80px",
        }}
      >
        {extractedText}
      </pre>
    </div>
  );
}
