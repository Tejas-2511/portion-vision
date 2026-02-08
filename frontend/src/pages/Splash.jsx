import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function Splash() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/home");
    }, 3000);

    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        backgroundColor: "#2e7d32",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Arial",
      }}
    >
      <h1
        style={{
          color: "white",
          fontSize: "48px",
          fontWeight: "bold",
          letterSpacing: "2px",
        }}
      >
        Portion Vision
      </h1>
    </div>
  );
}
