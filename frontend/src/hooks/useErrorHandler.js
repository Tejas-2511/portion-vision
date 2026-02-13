import { useState } from 'react';

/**
 * Custom hook for error handling with retry logic
 * @returns {object} Error state and handlers
 */
export function useErrorHandler() {
    const [error, setError] = useState(null);
    const [retryCount, setRetryCount] = useState(0);

    const handleError = (err) => {
        console.error('Error occurred:', err);
        setError(err.message || 'An unexpected error occurred');
    };

    const clearError = () => {
        setError(null);
        setRetryCount(0);
    };

    const retry = (callback) => {
        if (retryCount < 3) {
            setRetryCount(prev => prev + 1);
            setError(null);
            callback();
        } else {
            setError('Maximum retry attempts reached. Please try again later.');
        }
    };

    return {
        error,
        retryCount,
        handleError,
        clearError,
        retry,
        canRetry: retryCount < 3,
    };
}
