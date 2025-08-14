"""
Custom exception classes for the Travel Itinerary Generator.

This module defines specific exception types that provide more granular
error handling and better user feedback.
"""

class TravelItineraryError(Exception):
    """Base exception for all Travel Itinerary Generator errors"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "GENERAL_ERROR"
        self.details = details or {}
    
    def to_dict(self):
        """Convert exception to dictionary for JSON responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }

class ConfigurationError(TravelItineraryError):
    """Raised when there are configuration issues (missing API keys, invalid settings)"""
    
    def __init__(self, message: str, missing_vars: list = None):
        super().__init__(
            message, 
            "CONFIGURATION_ERROR",
            {"missing_variables": missing_vars or []}
        )

class MCPServerError(TravelItineraryError):
    """Raised when there are issues with the MCP server communication"""
    
    def __init__(self, message: str, server_status: str = None):
        super().__init__(
            message, 
            "MCP_SERVER_ERROR",
            {"server_status": server_status}
        )

class AIServiceError(TravelItineraryError):
    """Raised when there are issues with AI services (OpenAI, LangChain)"""
    
    def __init__(self, message: str, service: str = None, api_error_code: str = None):
        super().__init__(
            message, 
            "AI_SERVICE_ERROR",
            {"service": service, "api_error_code": api_error_code}
        )

class GoogleMapsError(TravelItineraryError):
    """Raised when there are issues with Google Maps API"""
    
    def __init__(self, message: str, api_status: str = None):
        super().__init__(
            message, 
            "GOOGLE_MAPS_ERROR",
            {"api_status": api_status}
        )

class ValidationError(TravelItineraryError):
    """Raised when user input validation fails"""
    
    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(
            message, 
            "VALIDATION_ERROR",
            {"field": field, "invalid_value": value}
        )

class NetworkError(TravelItineraryError):
    """Raised when there are network connectivity issues"""
    
    def __init__(self, message: str, service: str = None, timeout: bool = False):
        super().__init__(
            message, 
            "NETWORK_ERROR",
            {"service": service, "timeout": timeout}
        )

class RateLimitError(TravelItineraryError):
    """Raised when API rate limits are exceeded"""
    
    def __init__(self, message: str, service: str = None, retry_after: int = None):
        super().__init__(
            message, 
            "RATE_LIMIT_ERROR",
            {"service": service, "retry_after_seconds": retry_after}
        )

class DataProcessingError(TravelItineraryError):
    """Raised when there are issues processing or formatting data"""
    
    def __init__(self, message: str, data_type: str = None):
        super().__init__(
            message, 
            "DATA_PROCESSING_ERROR",
            {"data_type": data_type}
        ) 