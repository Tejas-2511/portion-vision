import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useApp } from "../contexts/AppContext";
import api from "../services/api";
import RecommendationCard from "../components/RecommendationCard";

// Home page - Main dashboard displaying today's mess menu
export default function Home() {
  const navigate = useNavigate();
  const { todaysMenu, userProfile } = useApp();
  const [recommendations, setRecommendations] = useState(null);
  const [loadingRecs, setLoadingRecs] = useState(false);

  useEffect(() => {
    if (todaysMenu && userProfile) {
      loadRecommendations();
    }
  }, [todaysMenu, userProfile]);

  async function loadRecommendations() {
    setLoadingRecs(true);
    try {
      // Determine meal type based on time
      const hour = new Date().getHours();
      let mealType = "lunch";

      if (hour >= 6 && hour < 11) mealType = "breakfast";
      else if (hour >= 11 && hour < 16) mealType = "lunch";
      else if (hour >= 16 && hour < 19) mealType = "snack";
      else if (hour >= 19) mealType = "dinner";

      const data = await api.getRecommendations(userProfile, mealType);

      // The backend returns the full object { mealType, recommendedPlate, ... }
      if (data && data.recommendedPlate) {
        setRecommendations(data);
      } else {
        setRecommendations(null);
      }
    } catch (err) {
      console.error("Failed to load recommendations:", err);
      setRecommendations(null);
    } finally {
      setLoadingRecs(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-20">

      {/* AppBar */}
      <div className="sticky top-0 z-50 flex items-center justify-between bg-emerald-600 px-6 py-4 shadow-md text-white">
        <span className="text-xl font-bold tracking-wide">Portion Vision</span>
        <button
          onClick={() => navigate("/preferences")}
          className="rounded-full bg-white/20 px-4 py-2 text-sm font-medium transition hover:bg-white/30"
        >
          Profile
        </button>
      </div>

      {/* Body */}
      <div className="mx-auto max-w-lg px-4 pt-6">

        {/* Today's Menu Card */}
        <div className="mb-6 rounded-2xl bg-white p-6 shadow-md transition-shadow hover:shadow-lg">
          <h2 className="mb-4 text-lg font-bold text-slate-800">Today's Mess Menu</h2>

          {todaysMenu ? (
            <div className="space-y-3">
              <div className="rounded-xl bg-emerald-50 p-4 border border-emerald-200">
                <div className="space-y-2">
                  {todaysMenu.items.map((item, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <span className="text-emerald-600 font-bold mt-0.5">•</span>
                      <span className="text-slate-700 text-sm">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-xs text-slate-400 text-right">
                Uploaded: {new Date(todaysMenu.date).toLocaleDateString()} at {new Date(todaysMenu.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          ) : (
            <div className="flex h-40 w-full items-center justify-center rounded-xl bg-slate-100 text-slate-400">
              <span className="text-sm font-medium">No menu uploaded yet</span>
            </div>
          )}

          <button
            onClick={() => navigate("/menu-upload")}
            className="mt-4 w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white shadow-sm transition active:scale-[0.98] hover:bg-emerald-700"
          >
            {todaysMenu ? "Update Menu" : "Upload Mess Menu"}
          </button>
        </div>

        {/* Recommended Portions Card */}
        <RecommendationCard
          recommendation={recommendations}
          loading={loadingRecs}
        />

        {/* FAB / Action Button */}
        <div className="fixed bottom-8 left-0 right-0 z-40 flex justify-center px-4">
          <button
            onClick={() => navigate("/plate")}
            className="flex items-center gap-2 rounded-full bg-slate-900 px-8 py-4 text-lg font-bold text-white shadow-xl transition-transform hover:scale-105 active:scale-95"
          >
            <span>📸</span>
            Take Plate Photo
          </button>
        </div>
      </div>
    </div>
  );
}
