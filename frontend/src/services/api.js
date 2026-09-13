/**
 * Centralized API Service for PortionVision
 * Handles all backend communication with error handling and request management
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiService {
    normalizeMenu(raw) {
        if (!raw) return null;

        const items = Array.isArray(raw.items) ? raw.items : [];

        const text = typeof raw.text === 'string'
            ? raw.text
            : items.length
                ? items.join('\n')
                : '';

        return {
            ...raw,
            items,
            text,
        };
    }

    /**
     * Make a generic HTTP request
     * @param {string} endpoint - API endpoint (e.g., '/api/foods')
     * @param {object} options - Fetch options
     * @returns {Promise<any>} Response data
     */
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;

        try {
            // console.log(`Requesting: ${url}`);

            const response = await fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                },
            });

            if (!response.ok) {
                // Try to parse error message from response
                let errorMessage = `Request failed with status ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorData.message || errorMessage;
                } catch {
                    // If response is not JSON, use status text
                    errorMessage = response.statusText || errorMessage;
                }
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            // Network errors or other failures
            if (error.message.includes('fetch')) {
                throw new Error('Network error. Please check your connection.');
            }
            throw error;
        }
    }

    /**
     * Upload menu image for OCR processing
     * @param {File} file - Image file to upload
     * @returns {Promise<{items: string[], date: string}>}
     */
    async uploadMenuImage(file) {
        const formData = new FormData();
        formData.append('image', file);

        return this.request('/ocr', {
            method: 'POST',
            body: formData,
            // Don't set Content-Type header - let browser set it for FormData
        });
    }

    /**
     * Get all foods from database
     * @returns {Promise<Array>} Array of food items
     */
    async getFoods() {
        return this.request('/api/foods');
    }

    /**
     * Search foods by name
     * @param {string} query - Search query
     * @returns {Promise<Array>} Array of matching food items
     */
    async searchFoods(query) {
        if (!query || !query.trim()) {
            throw new Error('Search query cannot be empty');
        }
        return this.request(`/api/foods/search?q=${encodeURIComponent(query)}`);
    }

    /**
     * Get portion recommendations based on user profile
     * @param {object} userProfile - User profile data
     * @param {string} mealType - Breakfast, Lunch, Dinner, etc.
     * @returns {Promise<{recommendations: Array}>}
     */
    async getRecommendations(userProfile, mealType = 'lunch', menuItems = []) {
        return this.request('/api/recommend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ userProfile, mealType, menuItems })
        });
    }

    /**
     * Get the current menu from the server
     * @returns {Promise<object|null>} Menu object or null
     */
    async getMenu() {
        const menu = await this.request('/api/menu');
        return this.normalizeMenu(menu);
    }



    /**
     * Upload captured plate image for CV analysis
     * Automatically deduplicates in-flight calls for the same file/items to prevent double triggers
     * @param {File} file - Image file to upload
     * @param {string} expectedItems - Comma-separated list of expected items
     * @returns {Promise<{food_items: Array<{name: string, volume_ml: number, mass_g: number}>, confidence: number}>}
     */
    async analyzePlate(file, expectedItems = '') {
        const fileKey = file ? `${file.name}_${file.size}_${file.lastModified}_${expectedItems}` : null;

        // 1. If we already have the completed result for this exact image and items, return it immediately
        if (fileKey && this._lastPlateKey === fileKey && this._lastPlateResult) {
            console.log('[api.analyzePlate] Returning cached completed analysis result:', fileKey);
            return this._lastPlateResult;
        }

        // 2. If an analysis for this exact image is currently in flight, reuse the active promise
        if (fileKey && this._activePlatePromise && this._activePlateKey === fileKey) {
            console.log('[api.analyzePlate] Concurrent/Strict-mode duplicate call detected, reusing active promise:', fileKey);
            return this._activePlatePromise;
        }

        const formData = new FormData();
        formData.append('image', file);
        if (expectedItems) {
            formData.append('expectedItems', expectedItems);
        }

        const reqPromise = this.request('/api/analyze-plate', {
            method: 'POST',
            body: formData,
            // Don't set Content-Type header - let browser set it for FormData
        }).then(result => {
            if (fileKey) {
                this._lastPlateKey = fileKey;
                this._lastPlateResult = result;
            }
            return result;
        });

        if (fileKey) {
            this._activePlateKey = fileKey;
            this._activePlatePromise = reqPromise.finally(() => {
                if (this._activePlateKey === fileKey) {
                    this._activePlatePromise = null;
                    this._activePlateKey = null;
                }
            });
            return this._activePlatePromise;
        }

        return reqPromise;
    }
}

// Export singleton instance
export default new ApiService();
