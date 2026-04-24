class KDeepMatrixAIError(Exception):
    """Base exception for the platform."""
    pass

class DataLoadError(KDeepMatrixAIError):
    """Raised when data loading fails."""
    pass

class ColumnNotFoundError(KDeepMatrixAIError):
    """Raised when required columns are missing."""
    pass

class EmptyDataError(KDeepMatrixAIError):
    """Raised when filtered data is empty."""
    pass

class DistributionFitError(KDeepMatrixAIError):
    """Raised when distribution fitting fails."""
    pass

class VisualizationError(KDeepMatrixAIError):
    """Raised when visualization generation fails."""
    pass

class ModelNotFoundError(KDeepMatrixAIError):
    """Raised when requested model is not found."""
    pass
