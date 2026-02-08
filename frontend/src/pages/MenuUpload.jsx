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
  }

  async function handleOCR() {
    if (!selectedFile) {
      alert("Select a menu image first!");
      return;
    }

    const formData = new FormData();
    formData.append("image", selectedFile);

    setLoading(true);
    setExtractedText("");

    try {
      const res = await fetch("http://localhost:5000/ocr", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setExtractedText(data.text);
    } catch (err) {
      console.log(err);
      alert("OCR Failed");
    }

    setLoading(false);
  }

  return (
    <div style={{ fontFamily: "Arial", padding: "20px" }}>
      <h2 style={{ color: "green" }}>Upload Mess Menu</h2>

      <input type="file" accept="image/*" onChange={handleFileChange} />

      <br />
      <br />

      {preview && (
        <img
          src={preview}
          alt="menu preview"
          style={{ width: "100%", maxWidth: "400px", borderRadius: "10px" }}
        />
      )}

      <br />
      <br />

      <button
        onClick={handleOCR}
        disabled={loading}
        style={{
          backgroundColor: "green",
          color: "white",
          border: "none",
          padding: "12px 20px",
          borderRadius: "10px",
          cursor: "pointer",
        }}
      >
        {loading ? "Extracting..." : "Extract Text (OCR)"}
      </button>

      <h3>Extracted Text:</h3>
      <pre style={{ background: "#eee", padding: "10px", borderRadius: "10px" }}>
        {extractedText}
      </pre>
    </div>
  );
}
