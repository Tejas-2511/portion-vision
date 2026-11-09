/**
 * Enhanced Fuzzy Matching and Similarity Engine for Indian Food Items.
 * 
 * Capabilities:
 * 1. Exact string & normalized key matching (ignoring casing, spacing, and punctuation).
 * 2. Transliteration & synonym normalization for common Indian mess foods
 *    (e.g., roti <-> chapati <-> phulka, sambhar <-> sambar, daal <-> dal, poori <-> puri).
 * 3. Multi-word token overlap & Jaccard index (handles word order flips like "Egg Boiled" vs "Boiled Egg").
 * 4. Substring containment & prefix matching (e.g., "Paneer Butter Masala" vs "Paneer Masala").
 * 5. Levenshtein edit distance with length-normalized similarity ratio.
 */

function levenshteinDistance(a, b) {
    if (!a || !b) return (a || b || "").length;
    if (a.length === 0) return b.length;
    if (b.length === 0) return a.length;

    const matrix = [];
    for (let i = 0; i <= b.length; i++) {
        matrix[i] = [i];
    }
    for (let j = 0; j <= a.length; j++) {
        matrix[0][j] = j;
    }
    for (let i = 1; i <= b.length; i++) {
        for (let j = 1; j <= a.length; j++) {
            if (b.charAt(i - 1) === a.charAt(j - 1)) {
                matrix[i][j] = matrix[i - 1][j - 1];
            } else {
                matrix[i][j] = Math.min(
                    matrix[i - 1][j - 1] + 1,
                    Math.min(matrix[i][j - 1] + 1, matrix[i - 1][j] + 1)
                );
            }
        }
    }
    return matrix[b.length][a.length];
}

/**
 * Common Indian food synonyms and transliteration variants
 * Maps variant terms to a canonical cluster identifier.
 */
const SYNONYM_MAP = {
    // Breads / Flatbreads
    'chapati': 'roti',
    'chappati': 'roti',
    'chappathi': 'roti',
    'chapatti': 'roti',
    'phulka': 'roti',
    'fulka': 'roti',
    'rotti': 'roti',
    'roti': 'roti',
    'paratha': 'paratha',
    'parotta': 'paratha',
    'porotta': 'paratha',
    'puri': 'puri',
    'poori': 'puri',
    'bhatura': 'bhatura',
    'bhatoora': 'bhatura',
    'naan': 'naan',

    // Dals / Lentils / Soups
    'dal': 'dal',
    'daal': 'dal',
    'dhal': 'dal',
    'sambhar': 'sambar',
    'sambar': 'sambar',
    'rasam': 'rasam',

    // Vegetables / Curries
    'sabzi': 'sabzi',
    'sabji': 'sabzi',
    'subzi': 'sabzi',
    'subji': 'sabzi',
    'bhaji': 'sabzi',
    'curry': 'curry',
    'tarkari': 'sabzi',
    'alu': 'aloo',
    'aloo': 'aloo',
    'gobhi': 'gobi',
    'gobi': 'gobi',
    'mutter': 'matar',
    'matar': 'matar',
    'panir': 'paneer',
    'paneer': 'paneer',
    'chana': 'chole',
    'chole': 'chole',
    'chhole': 'chole',
    'rajma': 'rajma',
    'rajmah': 'rajma',
    'palak': 'palak',
    'spinach': 'palak',
    'methi': 'methi',
    'bhindi': 'bhindi',
    'okra': 'bhindi',
    'baingan': 'baingan',
    'brinjal': 'baingan',
    'eggplant': 'baingan',

    // Rice
    'chawal': 'rice',
    'rice': 'rice',
    'pulav': 'pulao',
    'pulao': 'pulao',
    'pilaf': 'pulao',
    'khichdi': 'khichdi',
    'khichuri': 'khichdi',

    // Dairy & Sides
    'curd': 'curd',
    'dahi': 'curd',
    'yogurt': 'curd',
    'yoghurt': 'curd',
    'raita': 'raita',
    'rayta': 'raita',

    // South Indian
    'dosa': 'dosa',
    'dosai': 'dosa',
    'dose': 'dosa',
    'idli': 'idli',
    'idly': 'idli',
    'vada': 'vada',
    'vadai': 'vada',

    // Non-veg
    'anda': 'egg',
    'egg': 'egg',
    'murgh': 'chicken',
    'chicken': 'chicken',
    'gosht': 'mutton',
    'mutton': 'mutton',
    'machli': 'fish',
    'fish': 'fish'
};

const { normalizeFoodName } = require("./normalize");
const cleanString = normalizeFoodName;

/**
 * Tokenize string and resolve known synonyms for each token
 */
function getCanonicalTokens(str) {
    const cleaned = cleanString(str);
    if (!cleaned) return [];
    return cleaned.split(' ').map(t => SYNONYM_MAP[t] || t);
}

/**
 * Computes a multi-metric similarity score [0.0 - 1.0] between two food names
 */
function calculateSimilarity(str1, str2) {
    if (!str1 || !str2) return 0.0;

    const s1 = cleanString(str1);
    const s2 = cleanString(str2);

    // 1. Exact match
    if (s1 === s2) return 1.0;

    // Compact comparison (spaces removed, e.g. "eggcurry" vs "egg curry")
    const c1 = s1.replace(/\s/g, '');
    const c2 = s2.replace(/\s/g, '');
    if (c1 === c2) return 0.98;

    // 2. Canonical tokens and synonym resolution
    const tokens1 = getCanonicalTokens(str1);
    const tokens2 = getCanonicalTokens(str2);

    const norm1 = tokens1.join(' ');
    const norm2 = tokens2.join(' ');
    if (norm1 === norm2) return 0.96;

    // 3. Token set intersection and Jaccard similarity
    const set1 = new Set(tokens1);
    const set2 = new Set(tokens2);

    let intersectionCount = 0;
    for (const t of set1) {
        if (set2.has(t)) {
            intersectionCount++;
        } else {
            // Check minor typo in token (e.g. "masla" vs "masala")
            for (const t2 of set2) {
                if (Math.abs(t.length - t2.length) <= 1 && levenshteinDistance(t, t2) <= 1) {
                    intersectionCount += 0.85;
                    break;
                }
            }
        }
    }

    const unionCount = set1.size + set2.size - Math.floor(intersectionCount);
    const jaccard = unionCount > 0 ? intersectionCount / unionCount : 0.0;

    // Subset containment: e.g. "paneer butter" in "paneer butter masala"
    const minTokens = Math.min(set1.size, set2.size);
    const containment = minTokens > 0 ? intersectionCount / minTokens : 0.0;

    let tokenScore = 0.0;
    if (containment >= 1.0) {
        tokenScore = 0.82 + (0.13 * jaccard); // High confidence containment
    } else if (containment >= 0.75) {
        tokenScore = 0.70 + (0.15 * jaccard);
    } else {
        tokenScore = jaccard * 0.85;
    }

    // 4. Normalized Levenshtein distance on strings
    const maxLen = Math.max(s1.length, s2.length);
    const editDist = levenshteinDistance(s1, s2);
    const levRatio = maxLen > 0 ? (1.0 - (editDist / maxLen)) : 0.0;

    // 5. Normalized Levenshtein on canonicalized strings
    const canonMaxLen = Math.max(norm1.length, norm2.length);
    const canonEditDist = levenshteinDistance(norm1, norm2);
    const canonLevRatio = canonMaxLen > 0 ? (1.0 - (canonEditDist / canonMaxLen)) : 0.0;

    return Math.max(tokenScore, levRatio, canonLevRatio);
}

/**
 * Searches a food database or list of items for the best matching food.
 * 
 * @param {string} query - Food name or OCR snippet to search for
 * @param {Array<object|string>} foodList - Array of food objects (with .name) or food strings
 * @param {number} minThreshold - Minimum similarity score (default 0.65)
 * @returns {{ food: object|string, score: number, type: string } | null}
 */
function findBestFoodMatch(query, foodList, minThreshold = 0.65) {
    if (!query || !foodList || foodList.length === 0) return null;

    const cleanedQuery = cleanString(query);
    if (!cleanedQuery || cleanedQuery.length < 2) return null;

    let bestMatch = null;
    let bestScore = 0.0;
    let matchType = 'none';

    for (const item of foodList) {
        const targetName = typeof item === 'string' ? item : (item && item.name);
        if (!targetName) continue;

        const score = calculateSimilarity(query, targetName);

        if (score > bestScore) {
            bestScore = score;
            bestMatch = item;
            if (score >= 0.98) matchType = 'exact';
            else if (score >= 0.90) matchType = 'synonym_or_minor_variant';
            else if (score >= 0.75) matchType = 'token_overlap';
            else matchType = 'fuzzy_levenshtein';
        }

        // Fast-path breakout for perfect match
        if (bestScore === 1.0) break;
    }

    if (bestScore >= minThreshold && bestMatch) {
        return {
            food: bestMatch,
            score: Math.round(bestScore * 1000) / 1000,
            type: matchType
        };
    }

    return null;
}

/**
 * Backward-compatible helper for existing code.
 * Matches a query against a database array with an optional Levenshtein/similarity threshold.
 */
function fuzzyMatchFood(name, db, threshold = 3) {
    if (!name || !db) return null;

    // Try enhanced multi-metric match first
    const result = findBestFoodMatch(name, db, 0.65);
    if (result && result.food) {
        return result.food;
    }

    // Fallback to classic Levenshtein search if needed
    let bestMatch = null;
    let minDistance = Infinity;
    const normalizedName = cleanString(name);

    for (const item of db) {
        if (!item || !item.name) continue;
        const itemName = cleanString(item.name);
        if (itemName === normalizedName) return item;

        const dist = levenshteinDistance(normalizedName, itemName);
        if (dist < minDistance && dist <= threshold) {
            minDistance = dist;
            bestMatch = item;
        }
    }
    return bestMatch;
}

module.exports = {
    levenshteinDistance,
    calculateSimilarity,
    findBestFoodMatch,
    fuzzyMatchFood,
    SYNONYM_MAP
};
