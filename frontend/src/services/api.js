/**
 * Centralized API Service for PortionVision
 * Handles all backend communication with error handling and request management
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiService {
    normalizeMenu(raw) {
        if (!raw) return null;

        const items = Array.isArray(raw.items)
            ? raw.items
            : Array.isArray(raw.menuItems)
                ? raw.menuItems
                : [];

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
     * @returns {Promise<{menuItems: string[]}>}
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
     * Get the user profile from the server
     * @returns {Promise<object|null>} Profile object or null
     */
    async getProfile() {
        return this.request('/api/profile');
    }

    /**
     * Save the user profile to the server
     * @param {object} profile - User profile data
     * @returns {Promise<object>} Response
     */
    async saveProfile(profile) {
        return this.request('/api/profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(profile)
        });
    }

    /**
     * Upload captured plate image for CV analysis
     * @param {File} file - Image file to upload
     * @param {string} expectedItems - Comma-separated list of expected items
     * @returns {Promise<{sections: object, confidence: number}>}
     */
    async analyzePlate(file, expectedItems = '') {
        const formData = new FormData();
        formData.append('image', file);
        if (expectedItems) {
            formData.append('expectedItems', expectedItems);
        }

        return this.request('/api/analyze-plate', {
            method: 'POST',
            body: formData,
            // Don't set Content-Type header - let browser set it for FormData
        });
    }
}

// Export singleton instance
export default new ApiService();
