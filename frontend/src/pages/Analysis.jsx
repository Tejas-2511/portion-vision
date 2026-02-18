import { useLocation } from "react-router-dom";
import { useState, useEffect } from "react";
import { useApp } from "../contexts/AppContext";
import api from "../services/api";
import RecommendationCard from "../components/RecommendationCard";

// Analysis page - Displays portion analysis results
export default function Analysis() {
  const location = useLocation();
  const { imageFile, imagePreview } = location.state || {};
  const { userProfile } = useApp();
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (userProfile) {
      loadRecommendation();
    }
  }, [userProfile]);

  async function loadRecommendation() {
    setLoading(true);
    try {
      // Determine meal type based on time
      const hour = new Date().getHours();
      let mealType = "lunch";

      if (hour >= 6 && hour < 11) mealType = "breakfast";
      else if (hour >= 11 && hour < 16) mealType = "lunch";
      else if (hour >= 16 && hour < 19) mealType = "snack";
      else if (hour >= 19) mealType = "dinner";

      const data = await api.getRecommendations(userProfile, mealType);

      if (data && data.recommendedPlate) {
        setRecommendation(data);
      }
    } catch (err) {
      console.error("Failed to load recommendation:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-10">
      <div className="bg-emerald-600 px-6 py-4 text-white shadow-md">
        <h1 className="text-xl font-bold">Portion Analysis</h1>
      </div>

      <div className="mx-auto max-w-lg space-y-6 p-6">

        {/* Card 1 - Recommended Portion */}
        <RecommendationCard
          recommendation={recommendation}
          loading={loading}
        />

        {/* Card 2 - Captured Plate Image */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <h2 className="mb-3 text-lg font-bold text-slate-700">Captured Plate</h2>
          <div className="overflow-hidden rounded-xl bg-slate-100">
            {imagePreview ? (
              <img
                src={imagePreview}
                alt="Captured plate"
                className="w-full h-auto object-cover"
              />
            ) : (
              <div className="flex h-32 items-center justify-center text-slate-500 font-medium">
                No image captured
              </div>
            )}
          </div>
          {imageFile && (
            <p className="mt-2 text-sm text-slate-500">
              File: {imageFile.name} ({(imageFile.size / 1024).toFixed(1)} KB)
            </p>
          )}
        </div>

        {/* Card 3 - Portion Comparison */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <h2 className="mb-3 text-lg font-bold text-slate-700">Portion Comparison</h2>
          <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium">
            Comparison Coming Soon
          </div>
        </div>

      </div>
    </div>
  );
}
