import { useState, useEffect } from "react";

export default function Preferences() {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");

  const [gender, setGender] = useState("Male");
  const [activityLevel, setActivityLevel] = useState("Sedentary");
  const [goalType, setGoalType] = useState("Maintain Weight");
  const [dietPreference, setDietPreference] = useState("Vegetarian");

  const [bmi, setBmi] = useState("To be calculated...");
  const [calories, setCalories] = useState("To be calculated...");
  const [protein, setProtein] = useState("To be calculated...");

  // Load saved profile on page load
  useEffect(() => {
    const saved = localStorage.getItem("userProfile");
    if (saved) {
      const data = JSON.parse(saved);
      setName(data.name || "");
      setAge(data.age || "");
      setHeight(data.height || "");
      setWeight(data.weight || "");
      setGender(data.gender || "Male");
      setActivityLevel(data.activityLevel || "Sedentary");
      setGoalType(data.goalType || "Maintain Weight");
      setDietPreference(data.dietPreference || "Vegetarian");
      setBmi(data.bmi || "To be calculated...");
      setCalories(data.calories ? `${data.calories} kcal/day` : "To be calculated...");
      setProtein(data.protein ? `${data.protein} g/day` : "To be calculated...");
    }
  }, []);

  function handleCalculateSave() {
    const h = parseFloat(height);
    const w = parseFloat(weight);
    const a = parseInt(age);

    if (!h || !w || !a) {
      alert("Please enter valid age, height and weight");
      return;
    }

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

    // Update UI
    setBmi(bmiVal.toFixed(2));
    setCalories(`${Math.round(calorieReq)} kcal/day`);
    setProtein(`${Math.round(proteinReq)} g/day`);

    // Save locally
    const userData = {
      name,
      age,
      height,
      weight,
      gender,
      activityLevel,
      goalType,
      dietPreference,
      bmi: bmiVal.toFixed(2),
      calories: Math.round(calorieReq),
      protein: Math.round(proteinReq),
    };

    localStorage.setItem("userProfile", JSON.stringify(userData));
    alert("Profile saved!");
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#f5f5f5",
        display: "flex",
        justifyContent: "center",
        paddingTop: "40px",
      }}
    >
      <div
        style={{
          padding: "20px",
          fontFamily: "Arial",
          maxWidth: "500px",
          width: "100%",
          backgroundColor: "white",
          borderRadius: "12px",
          boxShadow: "0px 2px 8px rgba(0,0,0,0.2)",
        }}
      >
        <h2 style={{ color: "green", textAlign: "center" }}>
          User Profile
        </h2>

        <input placeholder="Name" value={name} onChange={e => setName(e.target.value)} style={inputStyle} />
        <input placeholder="Age" type="number" value={age} onChange={e => setAge(e.target.value)} style={inputStyle} />
        <input placeholder="Height (cm)" type="number" value={height} onChange={e => setHeight(e.target.value)} style={inputStyle} />
        <input placeholder="Weight (kg)" type="number" value={weight} onChange={e => setWeight(e.target.value)} style={inputStyle} />

        <select value={gender} onChange={e => setGender(e.target.value)} style={inputStyle}>
          <option>Male</option>
          <option>Female</option>
          <option>Other</option>
        </select>

        <select value={activityLevel} onChange={e => setActivityLevel(e.target.value)} style={inputStyle}>
          <option>Sedentary</option>
          <option>Lightly Active</option>
          <option>Moderately Active</option>
          <option>Very Active</option>
        </select>

        <select value={goalType} onChange={e => setGoalType(e.target.value)} style={inputStyle}>
          <option>Maintain Weight</option>
          <option>Lose Weight</option>
          <option>Gain Weight</option>
          <option>Muscle Gain</option>
          <option>Fat Loss</option>
        </select>

        <select value={dietPreference} onChange={e => setDietPreference(e.target.value)} style={inputStyle}>
          <option>Vegetarian</option>
          <option>Jain</option>
          <option>Lacto-Vegetarian</option>
          <option>Ovo-Vegetarian</option>
          <option>Non-Vegetarian</option>
          <option>Vegan</option>
        </select>

        <p><b>BMI:</b> {bmi}</p>
        <p><b>Calories:</b> {calories}</p>
        <p><b>Protein:</b> {protein}</p>

        <button onClick={handleCalculateSave} style={buttonStyle}>
          Calculate & Save
        </button>
      </div>
    </div>
  );
}

const inputStyle = {
  width: "100%",
  padding: "10px",
  marginBottom: "12px",
  borderRadius: "8px",
  border: "1px solid #ccc",
};

const buttonStyle = {
  backgroundColor: "green",
  color: "white",
  border: "none",
  padding: "12px",
  width: "100%",
  borderRadius: "10px",
  cursor: "pointer",
};
