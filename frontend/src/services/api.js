/**
 * Centralized API Service for PortionVision
 * Handles all backend communication with error handling and request management
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiService {
    /**
     * Make a generic HTTP request
     * @param {string} endpoint - API endpoint (e.g., '/api/foods')
     * @param {object} options - Fetch options
     * @returns {Promise<any>} Response data
     */
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;

        try {
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

    // Future endpoints can be added here:
    // - User authentication
    // - Save user profile
    // - Get recommendations
    // - Upload plate image for analysis
}

// Export singleton instance
export default new ApiService();
