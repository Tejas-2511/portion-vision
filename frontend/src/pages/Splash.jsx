import { useEffect, useState } from "react";

export default function Splash({ onFinish }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    setShow(true);

    const timer = setTimeout(() => {
      onFinish();
    }, 4000);

    return () => clearTimeout(timer);
  }, [onFinish]);

  return (
    <div
      style={{
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
          fontSize: "50px",
          fontWeight: "bold",
          letterSpacing: "2px",
          opacity: show ? 1 : 0,
          transform: show ? "scale(1)" : "scale(0.8)",
          transition: "all 1.8s ease",
        }}
      >
        Portion Vision
      </h1>
    </div>
  );
}
