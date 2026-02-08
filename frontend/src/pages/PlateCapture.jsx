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
    <div style={{ fontFamily: "Arial", backgroundColor: "#f5f5f5", minHeight: "100vh" }}>
      <div
        style={{
          backgroundColor: "green",
          color: "white",
          padding: "15px 20px",
          fontSize: "20px",
          fontWeight: "bold",
        }}
      >
        Plate Photo
      </div>

      <div style={{ padding: "16px" }}>
        <div
          style={{
            height: "260px",
            backgroundColor: "#ddd",
            borderRadius: "12px",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            overflow: "hidden",
          }}
        >
          {preview ? (
            <img
              src={preview}
              alt="plate preview"
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <p>Camera Preview Placeholder</p>
          )}
        </div>

        <br />

        <input type="file" accept="image/*" onChange={handleFileChange} />

        <br />
        <br />

        <button
          onClick={handleCapture}
          disabled={!selectedFile}
          style={{
            backgroundColor: "green",
            color: "white",
            border: "none",
            padding: "14px",
            borderRadius: "10px",
            fontSize: "16px",
            width: "100%",
            cursor: selectedFile ? "pointer" : "not-allowed",
            opacity: selectedFile ? 1 : 0.6,
          }}
        >
          Capture Photo
        </button>
      </div>
    </div>
  );
}
