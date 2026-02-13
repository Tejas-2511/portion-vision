export default function ErrorMessage({ error, onRetry, canRetry = false }) {
    if (!error) return null;

    return (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4">
            <div className="flex items-start gap-3">
                <span className="text-red-600 text-xl">⚠️</span>
                <div className="flex-1">
                    <p className="text-red-800 font-medium mb-1">Error</p>
                    <p className="text-red-700 text-sm">{error}</p>
                    {canRetry && onRetry && (
                        <button
                            onClick={onRetry}
                            className="mt-3 text-sm font-medium text-red-600 hover:text-red-700 underline"
                        >
                            Try Again
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
