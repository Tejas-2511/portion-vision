import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Splash() {
  const navigate = useNavigate();
  const [opacity, setOpacity] = useState("opacity-0");

  useEffect(() => {
    // Fade in
    setTimeout(() => setOpacity("opacity-100"), 100);

    const timer = setTimeout(() => {
      navigate("/home");
    }, 3000);

    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-emerald-600 to-green-800">
      <h1
        className={`text-6xl font-extrabold text-white tracking-widest uppercase drop-shadow-lg transition-opacity duration-1000 ${opacity}`}
      >
        Portion Vision
      </h1>
    </div>
  );
}
