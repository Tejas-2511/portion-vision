import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { useApp } from "../hooks/useApp";
import api from "../services/api";
import RecommendationCard from "../components/RecommendationCard";
import { inferMealType } from "../utils/time";

// Analysis page - Displays portion analysis results
export default function Analysis() {
  const location = useLocation();
  const navigate = useNavigate();
  const { imageFile, imagePreview } = location.state || {};
  const { userProfile, loading: profileLoading } = useApp();
  const [recommendation, setRecommendation] = useState(null);
  const [selectedMeal, setSelectedMeal] = useState(
    location.state?.mealType || inferMealType()
  );
  const [loading, setLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzingPlate, setAnalyzingPlate] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const hasAnalyzedRef = useRef(false);

  useEffect(() => {
    if (profileLoading || !imageFile || hasAnalyzedRef.current) return;
    hasAnalyzedRef.current = true;

    async function runFlow() {
      let currentRec = null;

      if (userProfile) {
        setLoading(true);
        try {
          const initialMeal = selectedMeal || location.state?.mealType || inferMealType();
          const data = await api.getRecommendations(userProfile, initialMeal);
          if (data && data.recommendedPlate) {
            currentRec = data;
            setRecommendation(data);
          }
        } catch (err) {
          console.error("Failed to load recommendation:", err);
        } finally {
          setLoading(false);
        }
      }

      await analyzeCapturedPlate(currentRec, selectedMeal);
    }

    runFlow();
  }, [profileLoading, userProfile, imageFile]);

  async function handleMealSelect(mealId) {
    if (mealId === selectedMeal || analyzingPlate) return;
    setSelectedMeal(mealId);
    setLoading(true);
    let newRec = null;
    try {
      if (userProfile) {
        newRec = await api.getRecommendations(userProfile, mealId);
        if (newRec && newRec.recommendedPlate) {
          setRecommendation(newRec);
        }
      }
    } catch (err) {
      console.warn("Failed to update recommendation on meal select:", err);
    } finally {
      setLoading(false);
    }
    await analyzeCapturedPlate(newRec, mealId);
  }

  async function analyzeCapturedPlate(recData = null, mealTypeOverride = null) {
    if (!imageFile) return;

    setAnalyzingPlate(true);
    setAnalysisError(null);
    console.log("Starting plate portion analysis...");
    try {
      // Guard against React SyntheticEvent being passed when used directly as an onClick handler
      const activeRec = (recData && typeof recData === 'object' && !recData.nativeEvent) ? recData : recommendation;
      let expectedItemsStr = '';
      if (activeRec && activeRec.recommendedPlate) {
        const expectedItemsArray = [
          ...activeRec.recommendedPlate.map(item => item.item.toLowerCase()),
          ...(activeRec.optionalItems ? activeRec.optionalItems.map(item => item.item.toLowerCase()) : [])
        ];
        expectedItemsStr = expectedItemsArray.join(',');
      }

      const plateProfile = location.state?.plateProfile || userProfile?.plateProfile || '';
      const activeMeal = mealTypeOverride || selectedMeal || location.state?.mealType || inferMealType();
      const result = await api.analyzePlate(imageFile, expectedItemsStr, plateProfile, activeMeal);
      setAnalysisResult(result);
    } catch (err) {
      console.error("Failed to analyze plate:", err);
      setAnalysisError(err.message || "Portion analysis failed");
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
      <div className="bg-emerald-600 px-6 py-4 text-white shadow-md flex items-center gap-4">
        <button 
          onClick={() => navigate(-1)}
          className="text-white hover:text-emerald-100 transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-xl font-bold">Portion Analysis</h1>
      </div>

      <div className="mx-auto max-w-lg space-y-6 p-6">

        {/* Meal Type Selector Bar */}
        <div className="rounded-2xl bg-white p-3.5 shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Meal Selection</span>
            <span className="text-xs text-slate-400">Tap to change meal slot</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[
              { id: 'breakfast', label: 'Breakfast', icon: '🌅' },
              { id: 'lunch', label: 'Lunch', icon: '🍛' },
              { id: 'snacks', label: 'Snacks', icon: '☕' },
              { id: 'dinner', label: 'Dinner', icon: '🌙' },
            ].map(m => (
              <button
                key={m.id}
                type="button"
                onClick={() => handleMealSelect(m.id)}
                disabled={analyzingPlate}
                className={`py-2 px-1 rounded-xl text-xs font-semibold flex flex-col items-center justify-center gap-1 transition-all ${
                  selectedMeal === m.id
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-200 ring-2 ring-emerald-500'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                <span className="text-base">{m.icon}</span>
                <span>{m.label}</span>
              </button>
            ))}
          </div>
        </div>

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
            (() => {
              const totalDetectedCals = analysisResult.food_items.reduce((acc, f) => acc + f.calories, 0);
              const targetMealCals = recommendation?.summary?.targetMealCalories || 0;
              const calDiff = totalDetectedCals - targetMealCals;
              const isPlateOver = targetMealCals > 0 && totalDetectedCals > targetMealCals * 1.1;

              return (
                <div className="space-y-4">
                  {/* Overall Detected Summary Dashboard */}
                  <div className="relative overflow-hidden p-5 rounded-2xl bg-white border border-slate-100 shadow-sm mb-4">
                    {/* Background Accent */}
                    <div className="absolute top-0 right-0 -mr-4 -mt-4 h-24 w-24 rounded-full bg-emerald-50 opacity-50"></div>

                    <div className="relative flex justify-between items-start mb-4">
                      <div>
                        <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest mb-1">Plate Verdict</p>
                        <h3 className={`text-xl font-black ${isPlateOver ? 'text-rose-600' : 'text-emerald-700'}`}>
                          {isPlateOver ? 'Over-portioned' : 'Balanced Plate'}
                        </h3>
                      </div>
                      <div className="flex flex-col items-end">
                        <span className="text-3xl font-black text-slate-800">
                          {Math.round(totalDetectedCals)}
                          <span className="text-sm font-normal text-slate-400 ml-1">kcal</span>
                        </span>
                        <p className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${isPlateOver ? 'bg-rose-100 text-rose-600' : 'bg-emerald-100 text-emerald-600'}`}>
                          {Math.abs(Math.round(calDiff))} kcal {calDiff > 0 ? 'above' : 'below'} target
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-3 pt-4 border-t border-slate-50 relative">
                      <div className="text-center p-2 rounded-xl bg-blue-50/50">
                        <div className="text-sm font-bold text-blue-700">
                          {Math.round(analysisResult.food_items.reduce((acc, f) => acc + f.protein, 0))}g
                        </div>
                        <div className="text-[9px] text-blue-500 font-bold uppercase tracking-tighter">Protein</div>
                      </div>
                      <div className="text-center p-2 rounded-xl bg-orange-50/50">
                        <div className="text-sm font-bold text-orange-700">
                          {Math.round(analysisResult.food_items.reduce((acc, f) => acc + f.carbs, 0))}g
                        </div>
                        <div className="text-[9px] text-orange-500 font-bold uppercase tracking-tighter">Carbs</div>
                      </div>
                      <div className="text-center p-2 rounded-xl bg-slate-50">
                        <div className="text-sm font-bold text-slate-700">
                          {Math.round(analysisResult.food_items.reduce((acc, f) => acc + f.fat, 0))}g
                        </div>
                        <div className="text-[9px] text-slate-500 font-bold uppercase tracking-tighter">Fat</div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-sm text-slate-500 mb-2 px-1">
                    <span>Confidence: {(analysisResult.confidence * 100).toFixed(0)}%</span>
                    <span className="text-emerald-600 font-medium">Detected Items</span>
                  </div>

                  <div className="space-y-3">
                    {analysisResult.food_items.map((food, idx) => {
                      const recGrams = getRecommendedGrams(food.name);
                      const actualGrams = Math.round(food.mass_g);
                      const isOver = recGrams && actualGrams > recGrams * 1.1;
                      const isUnder = recGrams && actualGrams < recGrams * 0.9;

                      return (
                        <div key={idx} className="flex flex-col rounded-xl bg-slate-50 p-4 border border-slate-100 shadow-sm">
                          <div className="flex justify-between items-start font-medium text-slate-700 capitalize mb-1">
                            <span className="truncate pr-2 font-bold">{food.name.replace(/_/g, ' ')}</span>
                            <span className="shrink-0 text-emerald-600 font-bold">{Math.round(food.calories)} kcal</span>
                          </div>

                          <div className="flex gap-2 mt-1 mb-3 flex-wrap">
                            <span className="text-[10px] font-semibold bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">
                              {food.protein}g protein
                            </span>
                            <span className="text-[10px] font-semibold bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded">
                              {food.carbs}g carbs
                            </span>
                            <span className="text-[10px] font-semibold bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                              {food.fat}g fat
                            </span>
                          </div>

                          <div className="flex justify-between items-end mt-2">
                            <div>
                              <p className="text-xs text-slate-500">Detected Portion</p>
                              <p className={`text-lg font-bold ${isOver ? 'text-rose-500' : isUnder ? 'text-amber-500' : 'text-emerald-600'}`}>
                                {actualGrams} <span className="text-xs font-normal">g</span>
                                {recGrams && (
                                  <mark className={`ml-2 bg-transparent text-[10px] font-black uppercase ${actualGrams > recGrams ? 'text-rose-600' : 'text-emerald-600'}`}>
                                    ({actualGrams > recGrams ? '+' : ''}{actualGrams - recGrams}g)
                                  </mark>
                                )}
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

                          {food.top_k && food.top_k.length > 1 && (
                            <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-400">
                              <span className="font-bold text-slate-500">Alternatives:</span>
                              {food.top_k.slice(1, 3).map((alt, aIdx) => (
                                <span key={aIdx} className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 font-medium">
                                  {alt.label} ({Math.round(alt.confidence * 100)}%)
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  
                  <div className="mt-8 flex justify-center">
                    <button
                      onClick={() => navigate("/")}
                      className="w-full max-w-xs rounded-xl bg-slate-900 py-4 font-bold text-white shadow-lg transition active:scale-95 hover:bg-slate-800"
                    >
                      Done
                    </button>
                  </div>
                </div>
              );
            })()
          ) : analysisResult ? (
            <div className="flex h-32 items-center justify-center rounded-xl bg-amber-50 text-amber-600 font-medium text-center px-4">
              No food items detected. Try a clearer photo.
            </div>
          ) : analysisError ? (
            (() => {
              const isQualityIssue = /blur|tilt|angle|steep|steady|focus|clearer/i.test(analysisError);
              return (
                <div className={`flex flex-col gap-3 items-center justify-center rounded-xl p-6 text-center ${isQualityIssue ? 'bg-amber-50 border border-amber-200' : 'bg-rose-50 border border-rose-200'}`}>
                  <div className={`font-bold flex items-center gap-1.5 ${isQualityIssue ? 'text-amber-800' : 'text-rose-600'}`}>
                    <span>{isQualityIssue ? '⚠️ Photo Quality Tip' : '❌ Analysis Failed'}</span>
                  </div>
                  <p className={`text-sm max-w-sm ${isQualityIssue ? 'text-amber-700 font-medium' : 'text-rose-600'}`}>{analysisError}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <button
                      onClick={() => navigate("/plate", { state: { mealType: location.state?.mealType } })}
                      className="text-xs font-bold uppercase tracking-wider bg-emerald-600 text-white px-5 py-2.5 rounded-full shadow-sm hover:bg-emerald-700 transition-all active:scale-95"
                    >
                      📸 Retake Photo
                    </button>
                    <button 
                      onClick={() => analyzeCapturedPlate(recommendation)}
                      className="text-xs font-bold uppercase tracking-wider bg-slate-100 text-slate-600 px-4 py-2.5 rounded-full hover:bg-slate-200 transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                </div>
              );
            })()
          ) : (
            <div className="flex h-32 items-center justify-center rounded-xl bg-slate-100 text-slate-500 font-medium text-center px-4">
              Capture a photo to start AI portion analysis.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
