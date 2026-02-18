/**
 * Normalizes a food name string for consistent matching.
 * - Converts to lowercase
 * - Removes special characters (except spaces)
 * - Collapses multiple spaces
 * - Trims whitespace
 * 
 * @param {string} text - The input string to normalize
 * @returns {string} The normalized string
 */
function normalizeFoodName(text) {
    if (!text) return "";
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '') // Remove special chars
        .replace(/\s+/g, ' ')        // Collapse spaces
        .trim();                     // Trim structure
}

module.exports = { normalizeFoodName };
