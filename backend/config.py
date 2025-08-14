import os
import logging
from dotenv import load_dotenv
from exceptions import ConfigurationError, ValidationError

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the Travel Itinerary Generator MVP"""
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    
    # MCP Server Configuration
    MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH", "npx -y @cablate/mcp-google-map")
    
    # Server Configuration
    HOST = os.getenv("HOST", "localhost")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    
    # Request Configuration
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    
    @classmethod
    def validate(cls):
        """Validate that all required environment variables are set"""
        missing_vars = []
        
        # Check required API keys
        if not cls.OPENAI_API_KEY:
            missing_vars.append("OPENAI_API_KEY")
        elif len(cls.OPENAI_API_KEY.strip()) < 10:
            logger.warning("OPENAI_API_KEY appears to be invalid (too short)")
        
        if not cls.GOOGLE_MAPS_API_KEY:
            missing_vars.append("GOOGLE_MAPS_API_KEY")
        elif len(cls.GOOGLE_MAPS_API_KEY.strip()) < 10:
            logger.warning("GOOGLE_MAPS_API_KEY appears to be invalid (too short)")
        
        # Validate server configuration
        try:
            if not (1 <= cls.PORT <= 65535):
                raise ValidationError(
                    f"Invalid PORT value: {cls.PORT}. Must be between 1 and 65535.",
                    field="PORT",
                    value=str(cls.PORT)
                )
                
            if not (1 <= cls.REQUEST_TIMEOUT <= 300):
                raise ValidationError(
                    f"Invalid REQUEST_TIMEOUT value: {cls.REQUEST_TIMEOUT}. Must be between 1 and 300 seconds.",
                    field="REQUEST_TIMEOUT", 
                    value=str(cls.REQUEST_TIMEOUT)
                )
                
            if not (1 <= cls.MAX_RETRIES <= 10):
                raise ValidationError(
                    f"Invalid MAX_RETRIES value: {cls.MAX_RETRIES}. Must be between 1 and 10.",
                    field="MAX_RETRIES",
                    value=str(cls.MAX_RETRIES)
                )
                
        except ValueError as e:
            raise ValidationError(
                f"Configuration value type error: {str(e)}",
                field="configuration"
            )
        
        # Raise configuration error if missing variables
        if missing_vars:
            error_message = (
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please check your .env file and ensure all required variables are set. "
                f"Refer to .env.example for guidance."
            )
            logger.error(error_message)
            raise ConfigurationError(error_message, missing_vars)
        
        logger.info("✅ Configuration validation passed")
    
    @classmethod
    def get_summary(cls):
        """Get a summary of the current configuration (without exposing sensitive data)"""
        # Mask API keys for security
        def mask_key(key):
            if not key:
                return False
            if len(key) <= 8:
                return "***"
            return f"{key[:3]}***{key[-3:]}"
        
        return {
            "openai_api_key_set": bool(cls.OPENAI_API_KEY),
            "openai_api_key_preview": mask_key(cls.OPENAI_API_KEY) if cls.OPENAI_API_KEY else None,
            "google_maps_api_key_set": bool(cls.GOOGLE_MAPS_API_KEY),
            "google_maps_api_key_preview": mask_key(cls.GOOGLE_MAPS_API_KEY) if cls.GOOGLE_MAPS_API_KEY else None,
            "mcp_server_path": cls.MCP_SERVER_PATH,
            "host": cls.HOST,
            "port": cls.PORT,
            "debug": cls.DEBUG,
            "request_timeout": cls.REQUEST_TIMEOUT,
            "max_retries": cls.MAX_RETRIES
        }
    
    @classmethod
    def is_development(cls):
        """Check if running in development mode"""
        return cls.DEBUG
    
    @classmethod
    def is_production(cls):
        """Check if running in production mode"""
        return not cls.DEBUG

# Create a global config instance
config = Config() 

# Validate configuration on module load in production
if not config.is_development():
    try:
        config.validate()
    except (ConfigurationError, ValidationError) as e:
        logger.critical(f"Critical configuration error: {e.message}")
        # In production, we might want to exit gracefully
        # import sys
        # sys.exit(1)
        raise 