import LoadingSpinner from './LoadingSpinner';

export default function Button({
    children,
    variant = 'primary',
    loading = false,
    disabled = false,
    className = '',
    ...props
}) {
    const variants = {
        primary: 'bg-emerald-600 hover:bg-emerald-700 text-white',
        secondary: 'bg-slate-600 hover:bg-slate-700 text-white',
        danger: 'bg-red-600 hover:bg-red-700 text-white',
        outline: 'border-2 border-emerald-600 text-emerald-600 hover:bg-emerald-50',
    };

    const isDisabled = loading || disabled;

    return (
        <button
            className={`
        rounded-xl py-3 px-6 font-bold transition-all
        ${variants[variant]}
        ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'active:scale-[0.98]'}
        ${className}
      `}
            disabled={isDisabled}
            {...props}
        >
            {loading ? (
                <div className="flex items-center justify-center gap-2">
                    <LoadingSpinner size="sm" />
                    <span>Loading...</span>
                </div>
            ) : (
                children
            )}
        </button>
    );
}
