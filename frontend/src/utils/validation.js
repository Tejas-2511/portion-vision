/**
 * Validation utilities for forms and file uploads
 */

/**
 * Validate user profile data
 * @param {object} data - User profile data
 * @returns {{isValid: boolean, errors: object}}
 */
export function validateProfileData(data) {
    const errors = {};

    // Name validation
    if (!data.name || data.name.trim().length === 0) {
        errors.name = 'Name is required';
    } else if (data.name.trim().length < 2) {
        errors.name = 'Name must be at least 2 characters';
    }

    // Age validation
    const age = parseInt(data.age);
    if (!data.age || isNaN(age)) {
        errors.age = 'Age is required';
    } else if (age < 10 || age > 120) {
        errors.age = 'Age must be between 10 and 120';
    }

    // Height validation
    const height = parseFloat(data.height);
    if (!data.height || isNaN(height)) {
        errors.height = 'Height is required';
    } else if (height < 100 || height > 250) {
        errors.height = 'Height must be between 100-250 cm';
    }

    // Weight validation
    const weight = parseFloat(data.weight);
    if (!data.weight || isNaN(weight)) {
        errors.weight = 'Weight is required';
    } else if (weight < 30 || weight > 300) {
        errors.weight = 'Weight must be between 30-300 kg';
    }

    return {
        isValid: Object.keys(errors).length === 0,
        errors
    };
}

/**
 * Validate image file before upload
 * @param {File} file - Image file to validate
 * @throws {Error} If validation fails
 */
export function validateImageFile(file) {
    if (!file) {
        throw new Error('No file selected');
    }

    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp'];

    if (!allowedTypes.includes(file.type)) {
        throw new Error('Please upload a JPEG, PNG, or WEBP image');
    }

    if (file.size > maxSize) {
        throw new Error('Image must be less than 10MB');
    }

    return true;
}

/**
 * Format validation errors for display
 * @param {object} errors - Validation errors object
 * @returns {string} Formatted error message
 */
export function formatValidationErrors(errors) {
    return Object.values(errors).join('. ');
}
