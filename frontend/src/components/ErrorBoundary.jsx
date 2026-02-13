import { Component } from 'react';

/**
 * Error Boundary component to catch and display React errors gracefully
 */
class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('Error caught by boundary:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
                    <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
                        <div className="text-center">
                            <span className="text-6xl mb-4 block">😕</span>
                            <h2 className="text-2xl font-bold text-slate-800 mb-2">
                                Oops! Something went wrong
                            </h2>
                            <p className="text-slate-600 mb-6">
                                We encountered an unexpected error. Please refresh the page to try again.
                            </p>
                            <button
                                onClick={() => window.location.reload()}
                                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 px-6 rounded-xl transition"
                            >
                                Refresh Page
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
