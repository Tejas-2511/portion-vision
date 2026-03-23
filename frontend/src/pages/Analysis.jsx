import { useLocation } from "react-router-dom";
import { useState, useEffect } from "react";
import { useApp } from "../hooks/useApp";
import api from "../services/api";
import RecommendationCard from "../components/RecommendationCard";

// Analysis page - Displays portion analysis results
export default function Analysis() {
  const location = useLocation();
  const { imageFile, imagePreview } = location.state || {};
  const { userProfile } = useApp();
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzingPlate, setAnalyzingPlate] = useState(false);

  useEffect(() => {
    if (userProfile) {
      loadRecommendation();
    }
  }, [userProfile]);

  useEffect(() => {
    if (recommendation && imageFile && !analysisResult && !analyzingPlate) {
      analyzeCapturedPlate();
    }
  }, [recommendation, imageFile]);

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

  async function analyzeCapturedPlate() {
    if (!imageFile || !recommendation) return;

    setAnalyzingPlate(true);
    try {
      // Build a comma-separated list of expected items from recommendation
      const expectedItemsArray = [
        ...recommendation.recommendedPlate.map(item => item.item.toLowerCase()),
        ...(recommendation.optionalItems ? recommendation.optionalItems.map(item => item.item.toLowerCase()) : [])
      ];
      const expectedItemsStr = expectedItemsArray.join(',');

      const result = await api.analyzePlate(imageFile, expectedItemsStr);
      setAnalysisResult(result);
    } catch (err) {
      console.error("Failed to analyze plate:", err);
    } finally {
      setAnalyzingPlate(false);
    }
  }

  // Helper to find recommended grams for a detected food item
  const getRecommendedGrams = (foodName) => {
    if (!recommendation) return null;

    // Check main plate
    const mainMatch = recommendation.recommendedPlate.find(
      item => item.item.toLowerCase() === foodName.toLowerCase()
    );
    if (mainMatch) return mainMatch.totalGrams;

    // Check optional
    if (recommendation.optionalItems) {
      const optMatch = recommendation.optionalItems.find(
        item => item.item.toLowerCase() === foodName.toLowerCase()
      );
      if (optMatch) return optMatch.totalGrams;
    }

    return null;
  };

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

        {/* Card 3 - Portion Comparison (CV Analysis) */}
        <div className="rounded-2xl bg-white p-4 shadow-md">
          <h2 className="mb-3 text-lg font-bold text-slate-700 mt-2">Computer Vision Analysis</h2>

          {!imageFile ? (
            <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium text-center px-4">
              Capture a photo to start AI portion analysis.
            </div>
          ) : analyzingPlate ? (
            <div className="flex flex-col h-32 items-center justify-center rounded-xl bg-slate-50 text-slate-500 font-medium text-center">
              <div className="mb-3 h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent"></div>
              Analyzing plate & estimating mass...
            </div>
          ) : analysisResult && analysisResult.food_items && analysisResult.food_items.length > 0 ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm text-slate-500 mb-2 px-1">
                <span>Confidence: {(analysisResult.confidence * 100).toFixed(0)}%</span>
                <span className="text-emerald-600 font-medium">Analysis Complete</span>
              </div>

              <div className="space-y-3">
                {analysisResult.food_items.map((food, idx) => {
                  const recGrams = getRecommendedGrams(food.name);
                  const actualGrams = Math.round(food.mass_g);
                  const isOver = recGrams && actualGrams > recGrams * 1.1; // 10% tolerance
                  const isUnder = recGrams && actualGrams < recGrams * 0.9;

                  return (
                    <div key={idx} className="flex flex-col rounded-xl bg-slate-50 p-3 border border-slate-100">
                      <div className="flex justify-between font-medium text-slate-700 capitalize mb-1">
                        <span className="truncate">{food.name.replace(/_/g, ' ')}</span>
                      </div>

                      <div className="flex justify-between items-end mt-2">
                        <div>
                          <p className="text-xs text-slate-500">Detected Portion</p>
                          <p className={`text-lg font-bold ${isOver ? 'text-rose-500' : isUnder ? 'text-amber-500' : 'text-emerald-600'}`}>
                            {actualGrams} <span className="text-xs font-normal">g</span>
                          </p>
                          <p className="text-[10px] text-slate-400 mt-0.5">
                            ~{Math.round(food.volume_ml)} ml volume
                          </p>
                        </div>

                        {recGrams && (
                          <div className="text-right">
                            <p className="text-xs text-slate-500">Recommended</p>
                            <p className="text-sm font-semibold text-slate-600">
                              {Math.round(recGrams)} <span className="text-xs font-normal">g</span>
                            </p>
                          </div>
                        )}
                      </div>

                      {recGrams && (
                        <div className="w-full bg-slate-200 rounded-full h-1.5 mt-3">
                          <div
                            className={`h-1.5 rounded-full ${isOver ? 'bg-rose-500' : isUnder ? 'bg-amber-500' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.min(100, (actualGrams / recGrams) * 100)}%` }}
                          ></div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : analysisResult ? (
            <div className="flex h-32 items-center justify-center rounded-xl bg-amber-50 text-amber-600 font-medium text-center px-4">
              No food items detected. Try a clearer photo.
            </div>
          ) : (
            <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-rose-500 font-medium text-center px-4">
              Analysis failed. Please try capturing again.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
