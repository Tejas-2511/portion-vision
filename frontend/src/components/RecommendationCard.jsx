import React from 'react';

export default function RecommendationCard({ recommendation, loading }) {
    if (loading) {
        return (
            <div className="mb-8 rounded-2xl bg-white p-6 shadow-md">
                <h2 className="mb-4 text-lg font-bold text-slate-800">Recommended Plate</h2>
                <div className="flex h-32 items-center justify-center text-emerald-600">
                    <span className="loading-spinner">Loading...</span>
                </div>
            </div>
        );
    }

    if (!recommendation || !recommendation.recommendedPlate) {
        return (
            <div className="mb-8 rounded-2xl bg-white p-6 shadow-md">
                <h2 className="mb-4 text-lg font-bold text-slate-800">Recommended Plate</h2>
                <div className="flex h-32 w-full items-center justify-center rounded-xl bg-slate-100 text-slate-400 flex-col gap-2">
                    <span className="text-sm font-medium">Upload a menu to get recommendations</span>
                </div>
            </div>
        );
    }

    const { mealType, recommendedPlate, optionalItems, avoidOrLimit, summary } = recommendation;

    // Helper to get emoji for role
    const getRoleIcon = (role) => {
        switch (role) {
            case 'carb': return '🌾';
            case 'protein': return '💪';
            case 'veg': return '🥗';
            case 'addon': return '🥛';
            default: return '🍽️';
        }
    };

    // Helper to get color for role
    const getRoleColor = (role) => {
        switch (role) {
            case 'carb': return 'bg-orange-50 text-orange-700 border-orange-100';
            case 'protein': return 'bg-blue-50 text-blue-700 border-blue-100';
            case 'veg': return 'bg-green-50 text-green-700 border-green-100';
            case 'addon': return 'bg-purple-50 text-purple-700 border-purple-100';
            default: return 'bg-slate-50 text-slate-700 border-slate-100';
        }
    };

    return (
        <div className="mb-8 rounded-2xl bg-white p-6 shadow-md transition-shadow hover:shadow-lg">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold text-slate-800 capitalize">
                    Recommended {mealType} Class
                </h2>
                <span className="text-xs font-medium px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full">
                    {summary.totalPlateCalories} kcal
                </span>
            </div>

            {/* Main Plate Items */}
            <div className="space-y-3 mb-6">
                {recommendedPlate.map((item, idx) => (
                    <div key={idx} className={`flex justify-between items-start p-3 rounded-xl border ${getRoleColor(item.role)}`}>
                        <div className="flex gap-3">
                            <div className="text-2xl pt-1">{getRoleIcon(item.role)}</div>
                            <div>
                                <p className="font-bold text-base capitalize">{item.item}</p>
                                <p className="text-xs opacity-80">{item.reason}</p>
                            </div>
                        </div>
                        <div className="text-right whitespace-nowrap pl-2">
                            <p className="font-bold text-lg leading-tight">
                                {item.recommendedQuantity} <span className="text-sm font-normal">{item.unit}</span>
                            </p>
                            <p className="text-[10px] opacity-70">~{item.estimatedCalories} kcal</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Optional Items */}
            {optionalItems && optionalItems.length > 0 && (
                <div className="mb-4">
                    <h3 className="text-sm font-bold text-slate-600 mb-2 uppercase tracking-wide">Optional Extras</h3>
                    <div className="flex flex-wrap gap-2">
                        {optionalItems.map((opt, idx) => (
                            <span key={idx} className="px-3 py-1 bg-slate-100 text-slate-600 text-sm rounded-lg border border-slate-200">
                                {opt.item}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Avoid Items (if any) */}
            {avoidOrLimit && avoidOrLimit.length > 0 && (
                <div>
                    <h3 className="text-sm font-bold text-slate-600 mb-2 uppercase tracking-wide">Limit / Avoid</h3>
                    <p className="text-sm text-slate-500 italic">
                        {avoidOrLimit.map(i => i.item).join(", ")}
                    </p>
                </div>
            )}

            <div className="mt-4 pt-3 border-t border-slate-100 text-center">
                <p className="text-xs text-slate-400">{summary.plateLogic}</p>
            </div>
        </div>
    );
}
