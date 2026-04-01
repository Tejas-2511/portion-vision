import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useApp } from "../hooks/useApp";
import { validateProfileData } from "../utils/validation";
import ErrorMessage from "../components/ErrorMessage";

// Preferences page - User profile and health metrics management
export default function Preferences() {
  const { userProfile, setUserProfile } = useApp();

  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");

  const [gender, setGender] = useState("Male");
  const [activityLevel, setActivityLevel] = useState("Sedentary");
  const [goalType, setGoalType] = useState("Maintain Weight");
  const [dietPreference, setDietPreference] = useState("Vegetarian");
  const [carbsPct, setCarbsPct] = useState(50);
  const [fatPct, setFatPct] = useState(30);
  const [proteinPct, setProteinPct] = useState(20);
  const [isManualMacros, setIsManualMacros] = useState(false);

  const [bmi, setBmi] = useState("To be calculated...");
  const [calories, setCalories] = useState("To be calculated...");
  const [protein, setProtein] = useState("To be calculated...");

  const [validationError, setValidationError] = useState(null);

  // Load saved profile on page load
  useEffect(() => {
    if (userProfile) {
      setName(userProfile.name || "");
      setAge(userProfile.age || "");
      setHeight(userProfile.height || "");
      setWeight(userProfile.weight || "");
      setGender(userProfile.gender || "Male");
      setActivityLevel(userProfile.activityLevel || "Sedentary");
      setGoalType(userProfile.goalType || "Maintain Weight");
      setDietPreference(userProfile.dietPreference || "Vegetarian");
      setBmi(userProfile.bmi || "To be calculated...");
      setCalories(userProfile.calories ? `${userProfile.calories} kcal/day` : "To be calculated...");
      setProtein(userProfile.protein ? `${userProfile.protein} g/day` : "To be calculated...");
      setProteinPct(userProfile.proteinPct || 20);
      setCarbsPct(userProfile.carbsPct || 50);
      setFatPct(userProfile.fatPct || 30);
    }
  }, [userProfile]);

  // Calculate BMI, calorie requirements, and protein needs using Mifflin-St Jeor equation
  function handleCalculateSave() {
    // Clear previous validation errors
    setValidationError(null);

    // Validate input data
    const inputData = { name, age, height, weight };
    const validation = validateProfileData(inputData);

    if (!validation.isValid) {
      const errorMessages = Object.values(validation.errors).join('. ');
      setValidationError(errorMessages);
      return;
    }

    const h = parseFloat(height);
    const w = parseFloat(weight);
    const a = parseInt(age);

    // BMI
    const heightM = h / 100;
    const bmiVal = w / (heightM * heightM);

    // BMR (Mifflin–St Jeor)
    let bmr = 0;
    if (gender === "Male") {
      bmr = 10 * w + 6.25 * h - 5 * a + 5;
    } else {
      bmr = 10 * w + 6.25 * h - 5 * a - 161;
    }

    // Activity multiplier
    const activityMap = {
      "Sedentary": 1.2,
      "Lightly Active": 1.375,
      "Moderately Active": 1.55,
      "Very Active": 1.725,
    };

    let calorieReq = bmr * activityMap[activityLevel];

    // Goal adjustment
    if (goalType === "Lose Weight" || goalType === "Fat Loss") {
      calorieReq -= 500;
    } else if (goalType === "Gain Weight" || goalType === "Muscle Gain") {
      calorieReq += 400;
    }

    calorieReq = Math.max(calorieReq, 1200); // safety

    // Protein requirement
    let proteinFactor = 1.0;
    if (goalType === "Fat Loss") proteinFactor = 1.6;
    if (goalType === "Muscle Gain") proteinFactor = 2.0;

    const proteinReq = w * proteinFactor;
    
    // Calculate percentages
    const calcProteinPct = Math.round(((proteinReq * 4) / calorieReq) * 100);
    const calcFatPct = 30;
    const calcCarbsPct = 100 - calcProteinPct - calcFatPct;

    // Update UI
    setBmi(bmiVal.toFixed(2));
    setCalories(`${Math.round(calorieReq)} kcal`);
    setProtein(`${Math.round(proteinReq)} g`);

    const finalProteinPct = isManualMacros ? parseInt(proteinPct || 0) : calcProteinPct;
    const finalCarbsPct = isManualMacros ? parseInt(carbsPct || 0) : calcCarbsPct;
    const finalFatPct = isManualMacros ? parseInt(fatPct || 0) : calcFatPct;

    // Update state ONLY if not in manual mode
    if (!isManualMacros) {
      setProteinPct(calcProteinPct);
      setCarbsPct(calcCarbsPct);
      setFatPct(calcFatPct);
    }

    // Save to context using the definitive values
    const userData = {
      name, age, height, weight, gender, activityLevel, goalType, dietPreference,
      bmi: bmiVal.toFixed(2),
      calories: Math.round(calorieReq),
      protein: Math.round((calorieReq * (finalProteinPct / 100)) / 4),
      proteinPct: finalProteinPct,
      carbsPct: finalCarbsPct,
      fatPct: finalFatPct,
    };

    setUserProfile(userData);
    alert("Profile saved!");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-xl relative">
        <button 
          onClick={() => navigate(-1)}
          className="absolute top-8 left-6 text-slate-400 hover:text-slate-600 transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 className="mb-6 text-center text-2xl font-bold text-emerald-600">
          User Profile
        </h2>



        {validationError && (
          <div className="mb-4">
            <ErrorMessage error={validationError} />
          </div>
        )}

        <div className="space-y-4">
          <input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-gray-200 px-4 py-3 placeholder-gray-400 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          />
          <div className="grid grid-cols-3 gap-4">
            <input
              placeholder="Age"
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
            />
            <input
              placeholder="Height (cm)"
              type="number"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
            />
            <input
              placeholder="Weight (kg)"
              type="number"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
            />
          </div>

          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          >
            <option>Male</option>
            <option>Female</option>
            <option>Other</option>
          </select>

          <select
            value={activityLevel}
            onChange={(e) => { setActivityLevel(e.target.value); setIsManualMacros(false); }}
            className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          >
            <option>Sedentary</option>
            <option>Lightly Active</option>
            <option>Moderately Active</option>
            <option>Very Active</option>
          </select>

          <select
            value={goalType}
            onChange={(e) => { setGoalType(e.target.value); setIsManualMacros(false); }}
            className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          >
            <option>Maintain Weight</option>
            <option>Lose Weight</option>
            <option>Gain Weight</option>
            <option>Muscle Gain</option>
            <option>Fat Loss</option>
          </select>

          <select
            value={dietPreference}
            onChange={(e) => setDietPreference(e.target.value)}
            className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          >
            <option>Vegetarian</option>
            <option>Jain</option>
            <option>Lacto-Vegetarian</option>
            <option>Ovo-Vegetarian</option>
            <option>Non-Vegetarian</option>
            <option>Vegan</option>
          </select>

          <div className="pt-2">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1 mb-3">Macro Distribution (%)</p>
            <div className="grid grid-cols-3 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-100">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase">Prot %</label>
                <input
                  type="number"
                  value={proteinPct}
                  onChange={(e) => { setProteinPct(e.target.value); setIsManualMacros(true); }}
                  className="w-full mt-1 bg-transparent border-b border-slate-200 py-1 font-bold text-slate-700 outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase">Carb %</label>
                <input
                  type="number"
                  value={carbsPct}
                  onChange={(e) => { setCarbsPct(e.target.value); setIsManualMacros(true); }}
                  className="w-full mt-1 bg-transparent border-b border-slate-200 py-1 font-bold text-slate-700 outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase">Fat %</label>
                <input
                  type="number"
                  value={fatPct}
                  onChange={(e) => { setFatPct(e.target.value); setIsManualMacros(true); }}
                  className="w-full mt-1 bg-transparent border-b border-slate-200 py-1 font-bold text-slate-700 outline-none focus:border-emerald-500"
                />
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2 pl-1">
                <span className={`h-2 w-2 rounded-full ${Math.abs(parseInt(proteinPct || 0) + parseInt(carbsPct || 0) + parseInt(fatPct || 0) - 100) < 1 ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
                <p className="text-[9px] text-slate-400 italic">
                    Total: {parseInt(proteinPct || 0) + parseInt(carbsPct || 0) + parseInt(fatPct || 0)}% (Aim for exactly 100% for best results).
                </p>
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-3 rounded-lg bg-emerald-50 p-4 text-emerald-900">
            <p className="flex justify-between">
              <span className="font-semibold">BMI:</span> {bmi}
            </p>
            <p className="flex justify-between">
              <span className="font-semibold">Calories:</span> {calories}
            </p>
            <p className="flex justify-between">
              <span className="font-semibold">Protein:</span> {protein}
            </p>
          </div>

          <button
            onClick={handleCalculateSave}
            className="mt-6 w-full rounded-xl bg-emerald-600 py-3 text-lg font-bold text-white shadow-md transition-all hover:bg-emerald-700 hover:shadow-lg active:scale-[0.98]"
          >
            Calculate & Save
          </button>
        </div>
      </div>
    </div>
  );
}
