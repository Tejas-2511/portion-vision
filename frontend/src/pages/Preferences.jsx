import { useState } from "react";

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

  function calculateBMI(heightCm, weightKg) {
    const heightM = heightCm / 100;
    return weightKg / (heightM * heightM);
  }

  function handleCalculateSave() {
    const h = parseFloat(height);
    const w = parseFloat(weight);

    if (!h || !w) {
      alert("Enter valid height and weight!");
      return;
    }

    const bmiVal = calculateBMI(h, w);

    setBmi(bmiVal.toFixed(2));
    setCalories("Calculated value here...");
    setProtein("Calculated value here...");

    // Save locally in browser
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
    };

    localStorage.setItem("userProfile", JSON.stringify(userData));
    alert("Profile saved locally!");
  }

  return (
    <div style={{ fontFamily: "Arial", padding: "20px" }}>
      <h2 style={{ color: "green" }}>User Profile</h2>

      <div style={{ maxWidth: "400px" }}>
        <label>Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={inputStyle}
        />

        <label>Age</label>
        <input
          value={age}
          type="number"
          onChange={(e) => setAge(e.target.value)}
          style={inputStyle}
        />

        <label>Height (cm)</label>
        <input
          value={height}
          type="number"
          onChange={(e) => setHeight(e.target.value)}
          style={inputStyle}
        />

        <label>Weight (kg)</label>
        <input
          value={weight}
          type="number"
          onChange={(e) => setWeight(e.target.value)}
          style={inputStyle}
        />

        <br />

        <label>Gender</label>
        <select value={gender} onChange={(e) => setGender(e.target.value)} style={inputStyle}>
          <option value="Male">Male</option>
          <option value="Female">Female</option>
          <option value="Other">Other</option>
        </select>

        <label>Activity Level</label>
        <select value={activityLevel} onChange={(e) => setActivityLevel(e.target.value)} style={inputStyle}>
          <option value="Sedentary">Sedentary</option>
          <option value="Lightly Active">Lightly Active</option>
          <option value="Moderately Active">Moderately Active</option>
          <option value="Very Active">Very Active</option>
        </select>

        <label>Goal Type</label>
        <select value={goalType} onChange={(e) => setGoalType(e.target.value)} style={inputStyle}>
          <option value="Maintain Weight">Maintain Weight</option>
          <option value="Lose Weight">Lose Weight</option>
          <option value="Gain Weight">Gain Weight</option>
          <option value="Muscle Gain">Muscle Gain</option>
          <option value="Fat Loss">Fat Loss</option>
        </select>

        <label>Dietary Preference</label>
        <select value={dietPreference} onChange={(e) => setDietPreference(e.target.value)} style={inputStyle}>
          <option value="Jain">Jain (No onion, garlic, root vegetables)</option>
          <option value="Vegetarian">Vegetarian</option>
          <option value="Lacto-Vegetarian">Lacto-Vegetarian (Veg + Dairy)</option>
          <option value="Ovo-Vegetarian">Ovo-Vegetarian (Veg + Eggs)</option>
          <option value="Non-Vegetarian">Non-Vegetarian</option>
          <option value="Vegan">Vegan</option>
        </select>

        <br />

        <h3>Calculated BMI:</h3>
        <p>{bmi}</p>

        <h3>Estimated Daily Calorie Requirement:</h3>
        <p>{calories}</p>

        <h3>Estimated Daily Protein Requirement:</h3>
        <p>{protein}</p>

        <button
          onClick={handleCalculateSave}
          style={{
            backgroundColor: "green",
            color: "white",
            border: "none",
            padding: "12px 20px",
            borderRadius: "10px",
            cursor: "pointer",
            marginTop: "15px",
            width: "100%",
          }}
        >
          Calculate & Save
        </button>
      </div>
    </div>
  );
}

const inputStyle = {
  width: "100%",
  padding: "10px",
  marginTop: "6px",
  marginBottom: "14px",
  borderRadius: "8px",
  border: "1px solid #ccc",
};
