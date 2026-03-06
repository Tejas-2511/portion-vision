import React from 'react';

// Macro progress bar sub-component
function MacroBar({ label, value, target, color }) {
    const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
    return (
        <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 w-10 shrink-0">{label}</span>
            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all ${color}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
            <span className="text-xs font-semibold text-slate-600 w-16 text-right shrink-0">
                {value}g <span className="text-slate-400 font-normal">/ {target}g</span>
            </span>
        </div>
    );
}

export default function RecommendationCard({ recommendation, loading }) {
    // Loading state
    if (loading) {
        return (
            <div className="mb-8 rounded-2xl bg-white p-6 shadow-md">
                <h2 className="mb-4 text-lg font-bold text-slate-800">Recommended Plate</h2>
                <div className="flex h-32 items-center justify-center">
                    <div className="flex flex-col items-center gap-3 text-emerald-600">
                        <div className="w-8 h-8 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin" />
                        <span className="text-sm font-medium text-slate-500">Calculating your plate…</span>
                    </div>
                </div>
            </div>
        );
    }

    // Empty / no-menu state
    if (!recommendation || !recommendation.recommendedPlate) {
        return (
            <div className="mb-8 rounded-2xl bg-white p-6 shadow-md">
                <h2 className="mb-4 text-lg font-bold text-slate-800">Recommended Plate</h2>
                <div className="flex flex-col items-center justify-center gap-3 py-8 rounded-xl bg-slate-50 border border-dashed border-slate-200">
                    <span className="text-4xl">🍽️</span>
                    <p className="text-sm font-semibold text-slate-600">No recommendation yet</p>
                    <p className="text-xs text-slate-400 text-center max-w-xs">
                        Upload today's mess menu to get a personalised plate recommendation.
                    </p>
                </div>
            </div>
        );
    }

    // No-items-on-plate state (menu uploaded but nothing suitable)
    const { mealType, recommendedPlate, optionalItems, avoidOrLimit, summary } = recommendation;
    if (recommendedPlate.length === 0) {
        return (
            <div className="mb-8 rounded-2xl bg-white p-6 shadow-md">
                <h2 className="mb-4 text-lg font-bold text-slate-800">Recommended Plate</h2>
                <div className="flex flex-col items-center justify-center gap-3 py-8 rounded-xl bg-orange-50 border border-orange-100">
                    <span className="text-4xl">⚠️</span>
                    <p className="text-sm font-semibold text-orange-700">No compatible items found</p>
                    <p className="text-xs text-orange-500 text-center max-w-xs">
                        {summary?.notes || "The current menu has no items matching your dietary preference. Try updating your profile or uploading a new menu."}
                    </p>
                </div>
            </div>
        );
    }

    // Role styling helpers
    const getRoleStyle = (role) => {
        switch (role) {
            case 'carb':    return { border: 'border-orange-100', bg: 'bg-orange-50', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-600', icon: '🌾' };
            case 'protein': return { border: 'border-blue-100',   bg: 'bg-blue-50',   text: 'text-blue-700',   badge: 'bg-blue-100 text-blue-600',   icon: '💪' };
            case 'veg':     return { border: 'border-green-100',  bg: 'bg-green-50',  text: 'text-green-700',  badge: 'bg-green-100 text-green-600',  icon: '🥗' };
            case 'mixed':   return { border: 'border-purple-100', bg: 'bg-purple-50', text: 'text-purple-700', badge: 'bg-purple-100 text-purple-600', icon: '🍲' };
            case 'addon':   return { border: 'border-slate-100',  bg: 'bg-slate-50',  text: 'text-slate-700',  badge: 'bg-slate-100 text-slate-600',  icon: '🥛' };
            default:        return { border: 'border-slate-100',  bg: 'bg-slate-50',  text: 'text-slate-700',  badge: 'bg-slate-100 text-slate-600',  icon: '🍽️' };
        }
    };

    const totalCal  = summary.totalPlateCalories ?? 0;
    const totalProt = summary.totalPlateProtein ?? 0;
    const totalCarbs = summary.totalPlateCarbs ?? 0;
    const totalFat  = summary.totalPlateFat ?? 0;
    const targetCal  = summary.targetMealCalories ?? 0;
    const targetProt = summary.targetProtein ?? 0;
    // Derive approximate carb/fat targets from calories (45%/30% split)
    const targetCarbsG = targetCal > 0 ? Math.round((targetCal * 0.45) / 4) : 0;
    const maxFatG    = targetCal > 0 ? Math.round((targetCal * 0.35) / 9) : 0;

    // Calorie fill percentage for the header pill
    const calPct = targetCal > 0 ? Math.min(100, Math.round((totalCal / targetCal) * 100)) : 0;
    const calColor = calPct > 110 ? 'bg-red-500' : calPct > 90 ? 'bg-emerald-500' : 'bg-yellow-400';

    return (
        <div className="mb-8 rounded-2xl bg-white p-6 shadow-md transition-shadow hover:shadow-lg">

            {/* Header */}
            <div className="flex justify-between items-center mb-1">
                <h2 className="text-lg font-bold text-slate-800 capitalize">
                    {mealType} Plate
                </h2>
                <span className="text-xs font-semibold px-3 py-1 rounded-full bg-emerald-100 text-emerald-700">
                    {totalCal} kcal
                </span>
            </div>
            <p className="text-xs text-slate-400 mb-5">{summary.plateLogic}</p>

            {/* Main Plate Items */}
            <div className="space-y-3 mb-6">
                {recommendedPlate.map((item, idx) => {
                    const s = getRoleStyle(item.role);
                    return (
                        <div key={idx} className={`flex justify-between items-start p-3 rounded-xl border ${s.border} ${s.bg}`}>
                            <div className="flex gap-3 min-w-0 pr-2">
                                <div className="text-2xl pt-0.5 shrink-0">{s.icon}</div>
                                <div className="min-w-0">
                                    <p className={`font-bold text-sm capitalize break-words leading-tight ${s.text}`}>{item.item}</p>
                                    {item.reason && (
                                        <p className="text-[10px] opacity-70 mt-0.5">{item.reason}</p>
                                    )}
                                    <div className="flex gap-2 mt-1 flex-wrap">
                                        {item.protein > 0 && (
                                            <span className="text-[10px] font-semibold bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">
                                                {item.protein}g protein
                                            </span>
                                        )}
                                        {item.carbs > 0 && (
                                            <span className="text-[10px] font-semibold bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded">
                                                {item.carbs}g carbs
                                            </span>
                                        )}
                                        {item.fat > 0 && (
                                            <span className="text-[10px] font-semibold bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                                                {item.fat}g fat
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <div className="text-right shrink-0">
                                <p className={`font-bold text-base leading-tight ${s.text}`}>
                                    {item.recommendedQuantity} <span className="text-xs font-normal">{item.unit}</span>
                                </p>
                                {item.totalGrams > 0 && (
                                    <p className="text-[10px] text-slate-400 mt-0.5">{item.totalGrams}g</p>
                                )}
                                <p className="text-[10px] font-medium opacity-75 mt-0.5">~{item.estimatedCalories} kcal</p>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Macro Progress Bars */}
            {targetCal > 0 && (
                <div className="mb-5 p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-2">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Macro Breakdown</p>

                    {/* Calorie bar */}
                    <div className="flex items-center gap-2 mb-3">
                        <span className="text-xs text-slate-500 w-10 shrink-0">Kcal</span>
                        <div className="flex-1 h-3 bg-slate-200 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all ${calColor}`}
                                style={{ width: `${calPct}%` }}
                            />
                        </div>
                        <span className="text-xs font-semibold text-slate-600 w-24 text-right shrink-0">
                            {totalCal} <span className="text-slate-400 font-normal">/ {targetCal} kcal</span>
                        </span>
                    </div>

                    <MacroBar label="Protein" value={totalProt} target={targetProt} color="bg-blue-400" />
                    <MacroBar label="Carbs" value={totalCarbs} target={targetCarbsG} color="bg-orange-400" />
                    <MacroBar label="Fat" value={totalFat} target={maxFatG} color="bg-slate-400" />
                </div>
            )}

            {/* Optional Items */}
            {optionalItems && optionalItems.length > 0 && (
                <div className="mb-4">
                    <h3 className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Optional Extras</h3>
                    <div className="flex flex-wrap gap-2">
                        {optionalItems.map((opt, idx) => (
                            <div key={idx} className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs">
                                <span className="font-semibold text-slate-700 capitalize">{opt.item}</span>
                                <span className="text-slate-400 ml-1">({opt.limit})</span>
                                {opt.note && <span className="block text-slate-400 text-[10px]">{opt.note}</span>}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Avoid list */}
            {avoidOrLimit && avoidOrLimit.length > 0 && (
                <div className="mb-4">
                    <h3 className="text-xs font-bold text-red-500 mb-2 uppercase tracking-wide">Limit / Avoid</h3>
                    <p className="text-xs text-slate-500 italic">{avoidOrLimit.map(i => i.item).join(', ')}</p>
                </div>
            )}

            <div className="pt-3 border-t border-slate-100 text-center">
                <p className="text-xs text-slate-400">{summary.notes}</p>
            </div>
        </div>
    );
}
