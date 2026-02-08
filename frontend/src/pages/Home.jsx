import { useNavigate } from "react-router-dom";

export default function Home() {
  const navigate = useNavigate();

  return (
    <div style={{ fontFamily: "Arial", backgroundColor: "#f5f5f5", minHeight: "100vh" }}>
      
      {/* AppBar */}
      <div
        style={{
          backgroundColor: "green",
          color: "white",
          padding: "15px 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "20px",
          fontWeight: "bold",
        }}
      >
        <span>Portion Vision</span>

        <button
          onClick={() => navigate("/preferences")}
          style={{
            background: "transparent",
            border: "none",
            color: "white",
            fontSize: "16px",
            cursor: "pointer",
          }}
        >
          Profile
        </button>
      </div>

      {/* Body */}
      <div style={{ padding: "16px" }}>

        {/* Today's Menu Card */}
        <div
          style={{
            backgroundColor: "white",
            borderRadius: "14px",
            padding: "16px",
            boxShadow: "0px 2px 6px rgba(0,0,0,0.2)",
            marginBottom: "20px",
          }}
        >
          <h2 style={{ margin: 0 }}>Today's Mess Menu</h2>

          <div
            style={{
              height: "150px",
              backgroundColor: "#ddd",
              borderRadius: "12px",
              marginTop: "10px",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            Menu Preview
          </div>

          <button
            onClick={() => navigate("/menu-upload")}
            style={{
              marginTop: "12px",
              width: "100%",
              padding: "12px",
              borderRadius: "10px",
              border: "none",
              backgroundColor: "green",
              color: "white",
              cursor: "pointer",
            }}
          >
            Upload Mess Menu
          </button>
        </div>

        {/* Recommended Portions Card */}
        <div
          style={{
            backgroundColor: "white",
            borderRadius: "14px",
            padding: "16px",
            boxShadow: "0px 2px 6px rgba(0,0,0,0.2)",
            marginBottom: "30px",
          }}
        >
          <h2 style={{ margin: 0 }}>Recommended Portions</h2>

          <div
            style={{
              height: "120px",
              backgroundColor: "#ddd",
              borderRadius: "12px",
              marginTop: "10px",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            Recommendations will appear here
          </div>
        </div>

        {/* Plate Photo Button */}
        <div style={{ textAlign: "center" }}>
          <button
            onClick={() => navigate("/upload")}
            style={{
              backgroundColor: "green",
              color: "white",
              border: "none",
              padding: "16px 40px",
              borderRadius: "12px",
              fontSize: "16px",
              cursor: "pointer",
            }}
          >
            Take Plate Photo
          </button>
        </div>
      </div>
    </div>
  );
}
