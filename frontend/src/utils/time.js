/**
 * Centralized utility for meal-related time inference.
 * Used to automatically select breakfast, lunch, snack, or dinner based on system clock.
 */

export const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];

/**
 * Infers the current meal type based on the time of day.
 * @returns {string} One of: breakfast, lunch, snack, dinner
 */
export function inferMealType() {
  const hour = new Date().getHours();
  
  if (hour >= 5 && hour < 11) return "breakfast";
  if (hour >= 11 && hour < 16) return "lunch";
  if (hour >= 16 && hour < 19) return "snack";
  
  // Late night or early morning is dinner
  return "dinner";
}

/**
 * Returns a human-friendly label for a meal type.
 */
export function getMealLabel(type) {
  if (!type) return "";
  return type.charAt(0).toUpperCase() + type.slice(1);
}

/**
 * Formats a date string for display.
 */
export function formatDisplayDate(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, { 
    weekday: 'short', 
    month: 'short', 
    day: 'numeric' 
  });
}
