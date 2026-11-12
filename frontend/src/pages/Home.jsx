import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useApp } from "../hooks/useApp";
import api from "../services/api";
import RecommendationCard from "../components/RecommendationCard";
import { inferMealType, MEAL_TYPES, getMealLabel } from "../utils/time";

// Home page - Main dashboard displaying today's mess menu
export default function Home() {
  const navigate = useNavigate();
  const { todaysMenu, userProfile } = useApp();
  const [recommendations, setRecommendations] = useState(null);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [mealType, setMealType] = useState(todaysMenu?.mealType || inferMealType());

  const menuItems = Array.isArray(todaysMenu?.items) ? todaysMenu.items : [];

  // Re-fetch whenever menu, profile or mealType changes
  useEffect(() => {
    if (todaysMenu && userProfile) {
      loadRecommendations(mealType);
    }
  }, [todaysMenu, userProfile, mealType]);

  async function loadRecommendations(type) {
    setLoadingRecs(true);
    try {
      const data = await api.getRecommendations(userProfile, type, menuItems);
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

  function handleMealTypeChange(type) {
    setMealType(type);
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-24">

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

      <div className="mx-auto max-w-lg px-4 pt-6">

        {/* Dynamic Greeting */}
        <div className="mb-6">
          <h1 className="text-2xl font-black text-slate-800">
            Hello, {userProfile?.name?.split(' ')[0] || 'there'}! 👋
          </h1>
          <p className="text-sm text-slate-500 font-medium">
            Based on the time, it's almost {getMealLabel(inferMealType())} time.
          </p>
        </div>

        {/* Daily Summary Dashboard */}
        <div className="mb-8 p-6 rounded-[2rem] bg-white text-slate-800 shadow-lg relative overflow-hidden border border-slate-100">
          <div className="absolute top-0 right-0 -mr-6 -mt-6 h-40 w-40 rounded-full bg-emerald-500/5 blur-3xl"></div>

          <div className="flex justify-between items-center relative z-10">
            <div>
              <p className="text-[10px] font-black text-emerald-600 uppercase tracking-[0.2em] mb-2">Today's Target</p>
              <h2 className="text-4xl font-black tracking-tight text-slate-900 leading-none">
                {userProfile?.calories ? userProfile.calories : 'Set Profile'}
                {userProfile?.calories && <span className="text-xl font-medium text-slate-400 ml-2">kcal</span>}
              </h2>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-8 relative z-10">
            <div className="p-4 rounded-2xl bg-blue-50/50 text-center border border-blue-100">
              <p className="text-lg font-black text-blue-600">
                {userProfile?.protein ? `${userProfile.protein}g` : '--'}
              </p>
              <p className="text-[10px] text-blue-400 uppercase font-black tracking-widest mt-1">Protein</p>
            </div>
            <div className="p-4 rounded-2xl bg-orange-50/50 text-center border border-orange-100">
              <p className="text-lg font-black text-orange-600">
                {userProfile?.calories && userProfile?.carbsPct
                  ? `${Math.round((userProfile.calories * (userProfile.carbsPct / 100)) / 4)}g`
                  : '--'}
              </p>
              <p className="text-[10px] text-orange-400 uppercase font-black tracking-widest mt-1">Carbs</p>
            </div>
            <div className="p-4 rounded-2xl bg-emerald-50/50 text-center border border-emerald-100">
              <p className="text-lg font-black text-emerald-600">
                {userProfile?.calories && userProfile?.fatPct
                  ? `${Math.round((userProfile.calories * (userProfile.fatPct / 100)) / 9)}g`
                  : '--'}
              </p>
              <p className="text-[10px] text-emerald-400 uppercase font-black tracking-widest mt-1">Fat</p>
            </div>
          </div>
        </div>

        {/* Today's Menu Card */}
        <div className="mb-5 rounded-2xl bg-white p-6 shadow-md transition-shadow hover:shadow-lg">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold text-slate-800">Today's Mess Menu</h2>
            <span className="text-[10px] font-bold px-2 py-1 bg-emerald-100 text-emerald-700 rounded-lg uppercase">Live</span>
          </div>

          {todaysMenu ? (
            <div className="space-y-3">
              <div className="rounded-xl bg-emerald-50 p-4 border border-emerald-200">
                <div className="space-y-2">
                  {menuItems.map((item, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <span className="text-emerald-600 font-bold mt-0.5">•</span>
                      <span className="text-slate-700 text-sm capitalize">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-xs text-slate-400 text-right">
                Uploaded: {new Date(todaysMenu.date).toLocaleDateString()} at{" "}
                {new Date(todaysMenu.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
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

        {/* Meal Type Selector */}
        {todaysMenu && userProfile && (
          <div className="mb-5 rounded-2xl bg-white p-4 shadow-md">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Recommending for</p>
            <div className="grid grid-cols-4 gap-2">
              {MEAL_TYPES.map(type => (
                <button
                  key={type}
                  onClick={() => handleMealTypeChange(type)}
                  className={`py-2 rounded-xl text-xs font-semibold capitalize transition-all ${mealType === type
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Recommended Portions Card */}
        {!userProfile ? (
          <div className="mb-6 rounded-2xl bg-orange-50 p-6 shadow-md border border-orange-100 text-center">
            <h2 className="mb-2 text-lg font-bold text-orange-800">Complete Your Profile</h2>
            <p className="text-sm text-orange-600 mb-4">We need your details to recommend portion sizes.</p>
            <button
              onClick={() => navigate("/preferences")}
              className="px-6 py-2 bg-orange-600 text-white rounded-lg font-bold shadow-sm hover:bg-orange-700 transition"
            >
              Set Profile
            </button>
          </div>
        ) : (
          <RecommendationCard
            recommendation={recommendations}
            loading={loadingRecs}
          />
        )}
      </div>

      {/* FAB */}
      <div className="fixed bottom-8 left-0 right-0 z-40 flex justify-center px-4">
        <button
          onClick={() => navigate("/plate", { state: { mealType } })}
          className="flex items-center gap-2 rounded-full bg-slate-900 px-8 py-4 text-lg font-bold text-white shadow-xl transition-transform hover:scale-105 active:scale-95"
        >
          <span>📸</span>
          Take Plate Photo
        </button>
      </div>
    </div>
  );
}
