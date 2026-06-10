import './GenerateButton.css'

function GenerateButton({ onClick, loading, disabled }) {
    return (
        <button
            className={`generate-btn ${loading ? 'generate-btn--loading' : ''}`}
            onClick={onClick}
            disabled={disabled || loading}
        >
            {loading ? 'Generating...' : 'Generate Schedule'}
        </button>
    )
}

export default GenerateButton