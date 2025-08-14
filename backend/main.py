import asyncio
import logging
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
import uvicorn

from config import config
from itinerary_generator import get_itinerary_generator, ItineraryGenerator
from exceptions import (
    TravelItineraryError, ConfigurationError, ValidationError, 
    AIServiceError, NetworkError, RateLimitError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if config.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global itinerary generator instance
itinerary_generator: ItineraryGenerator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    global itinerary_generator
    
    # Startup
    try:
        logger.info("🚀 Starting Travel Itinerary Generator API...")
        config.validate()  # Validate configuration
        itinerary_generator = await get_itinerary_generator()
        logger.info("✅ API startup completed successfully")
        yield
    except ConfigurationError as e:
        logger.error(f"❌ Configuration error during startup: {e.message}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"❌ Failed to start API: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during startup")
    finally:
        # Shutdown
        logger.info("🛑 Shutting down Travel Itinerary Generator API...")
        if itinerary_generator:
            try:
                await itinerary_generator.cleanup()
                logger.info("✅ Itinerary generator cleaned up successfully")
            except Exception as e:
                logger.error(f"⚠️ Error during cleanup: {e}")
        logger.info("✅ API shutdown completed")

# Create FastAPI app
app = FastAPI(
    title="Travel Itinerary Generator API",
    description="AI-powered travel itinerary generator using LangChain and Google Maps",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class ItineraryRequest(BaseModel):
    destination: str = Field(..., description="Travel destination (e.g., 'Paris, France')", min_length=2, max_length=100)
    duration: int = Field(..., ge=1, le=30, description="Trip duration in days (1-30)")
    interests: List[str] = Field(default=[], description="List of user interests", max_items=10)

class ItineraryResponse(BaseModel):
    destination: str
    duration: int
    interests: List[str]
    itinerary: str
    generated_at: str

class ChatRequest(BaseModel):
    message: str = Field(..., description="Chat message to the travel assistant", min_length=1, max_length=1000)

class ChatResponse(BaseModel):
    response: str
    timestamp: str

class GoogleMapsRequest(BaseModel):
    query: str = Field(..., description="Place name or address to search for", min_length=1, max_length=200)

class GoogleMapsResponse(BaseModel):
    image: Optional[str] = None
    mapsUrl: Optional[str] = None
    directionsUrl: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: str
    config_status: Dict[str, Any]

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Dict[str, Any] = {}
    timestamp: str

# Enhanced error handlers
@app.exception_handler(TravelItineraryError)
async def travel_itinerary_error_handler(request: Request, exc: TravelItineraryError):
    """Handle custom travel itinerary errors"""
    logger.error(f"Travel Itinerary Error: {exc.error_code} - {exc.message}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=400 if exc.error_code in ["VALIDATION_ERROR", "CONFIGURATION_ERROR"] else 500,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(PydanticValidationError)
async def validation_error_handler(request: Request, exc: PydanticValidationError):
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": {"validation_errors": exc.errors()},
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "details": {},
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {exc}", exc_info=True)
    
    from datetime import datetime
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An internal error occurred while processing your request" if config.is_production() else str(exc),
            "details": {"debug_mode": config.DEBUG},
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend application"""
    try:
        with open("../frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        logger.error("Frontend file not found")
        raise HTTPException(status_code=404, detail="Frontend application not found. Please ensure the frontend files are properly deployed.")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with comprehensive status information"""
    try:
        config_status = config.get_summary()
        
        # Check if critical components are available
        status = "healthy"
        message = "All systems operational"
        
        # Check API key configuration
        if not config_status["openai_api_key_set"]:
            status = "unhealthy"
            message = "OpenAI API key not configured"
        elif not config_status["google_maps_api_key_set"]:
            status = "unhealthy" 
            message = "Google Maps API key not configured"
        elif not itinerary_generator:
            status = "unhealthy"
            message = "Itinerary generator not initialized"
        
        # Add system information
        config_status.update({
            "system_status": status,
            "uptime_status": "running",
            "dependencies": {
                "openai_service": "available" if config_status["openai_api_key_set"] else "unavailable",
                "google_maps_service": "available" if config_status["google_maps_api_key_set"] else "unavailable",
                "mcp_server": "configured"
            }
        })
        
        return HealthResponse(
            status=status,
            message=message,
            config_status=config_status
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Health check failed: {str(e) if config.DEBUG else 'Internal error'}"
        )

@app.post("/generate-itinerary", response_model=ItineraryResponse)
async def generate_itinerary(request: ItineraryRequest):
    """Generate a personalized travel itinerary with enhanced error handling"""
    try:
        if not itinerary_generator:
            raise ConfigurationError("Itinerary generator not initialized. Please check server startup logs.")
        
        # Validate destination
        if not request.destination.strip():
            raise ValidationError("Destination cannot be empty", field="destination", value=request.destination)
        
        # Additional validation for interests
        if request.interests and len(request.interests) > 10:
            raise ValidationError("Too many interests specified. Maximum 10 allowed.", field="interests")
        
        logger.info(f"🗺️ Generating itinerary for {request.destination} ({request.duration} days) with interests: {request.interests}")
        
        # Generate itinerary using the AI agent
        result = await itinerary_generator.generate_itinerary(
            destination=request.destination,
            duration=request.duration,
            interests=request.interests
        )
        
        logger.info(f"✅ Successfully generated itinerary for {request.destination}")
        return ItineraryResponse(**result)
        
    except TravelItineraryError:
        # Re-raise custom errors to be handled by the error handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating itinerary: {e}", exc_info=True)
        
        # Check for specific error patterns
        error_str = str(e).lower()
        if "api key" in error_str or "authentication" in error_str:
            raise AIServiceError("Authentication failed with AI service. Please check API key configuration.", service="openai")
        elif "rate limit" in error_str or "quota" in error_str:
            raise RateLimitError("AI service rate limit exceeded. Please try again later.", service="openai")
        elif "network" in error_str or "timeout" in error_str:
            raise NetworkError("Network error while connecting to AI service", service="openai", timeout="timeout" in error_str)
        else:
            raise AIServiceError(f"Failed to generate itinerary: {str(e) if config.DEBUG else 'AI service error'}", service="itinerary_generator")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """Chat with the travel assistant with enhanced error handling"""
    try:
        if not itinerary_generator:
            raise ConfigurationError("Travel assistant not initialized. Please check server startup logs.")
        
        # Validate message content
        message = request.message.strip()
        if not message:
            raise ValidationError("Message cannot be empty", field="message", value=request.message)
        
        if len(message) > 1000:
            raise ValidationError("Message too long. Maximum 1000 characters allowed.", field="message")
        
        logger.info(f"💬 Processing chat message: {message[:50]}...")
        
        # Process message through the AI agent
        response = await itinerary_generator.chat(message)
        
        from datetime import datetime
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat()
        )
        
    except TravelItineraryError:
        # Re-raise custom errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing chat message: {e}", exc_info=True)
        
        # Check for specific error patterns
        error_str = str(e).lower()
        if "api key" in error_str or "authentication" in error_str:
            raise AIServiceError("Authentication failed with AI service", service="openai")
        elif "rate limit" in error_str or "quota" in error_str:
            raise RateLimitError("AI service rate limit exceeded. Please try again later.", service="openai") 
        else:
            raise AIServiceError(f"Chat processing failed: {str(e) if config.DEBUG else 'AI service error'}", service="chat_agent")

@app.post("/google-maps-data", response_model=GoogleMapsResponse)
async def get_google_maps_data(request: GoogleMapsRequest):
    """Get Google Maps data including images and URLs for a place"""
    try:
        query = request.query.strip()
        if not query:
            raise ValidationError("Query cannot be empty", field="query", value=request.query)
        
        logger.info(f"🗺️ Fetching Google Maps data for: {query}")
        
        # Use the itinerary generator's MCP client to get place information
        if not itinerary_generator:
            raise ConfigurationError("Google Maps service not initialized")
        
        try:
            # Call the Google Maps MCP server through our itinerary generator
            maps_data = await itinerary_generator.get_place_info(query)
            
            # Extract relevant information
            image_url = None
            place_id = None
            formatted_address = None
            
            if maps_data and 'places' in maps_data and maps_data['places']:
                place = maps_data['places'][0]  # Get first result
                
                # Get place photo if available
                if 'photos' in place and place['photos']:
                    # Get the first photo reference
                    photo_ref = place['photos'][0].get('photo_reference')
                    if photo_ref:
                        # Construct Google Places photo URL
                        image_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={config.GOOGLE_MAPS_API_KEY}"
                
                place_id = place.get('place_id')
                formatted_address = place.get('formatted_address', query)
            
            # Generate Maps URLs
            encoded_query = query.replace(' ', '+').replace(',', '%2C')
            maps_url = f"https://www.google.com/maps/search/{encoded_query}"
            directions_url = f"https://www.google.com/maps/dir//{encoded_query}"
            
            # If we have a place_id, use more specific URLs
            if place_id:
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                directions_url = f"https://www.google.com/maps/dir/?api=1&destination=place_id:{place_id}"
            
            logger.info(f"✅ Successfully fetched Google Maps data for: {query}")
            
            return GoogleMapsResponse(
                image=image_url,
                mapsUrl=maps_url,
                directionsUrl=directions_url
            )
            
        except Exception as mcp_error:
            logger.warning(f"⚠️ MCP Google Maps call failed for '{query}': {mcp_error}")
            
            # Fallback to basic URLs without MCP data
            encoded_query = query.replace(' ', '+').replace(',', '%2C')
            return GoogleMapsResponse(
                image=None,
                mapsUrl=f"https://www.google.com/maps/search/{encoded_query}",
                directionsUrl=f"https://www.google.com/maps/dir//{encoded_query}"
            )
            
    except TravelItineraryError:
        # Re-raise custom errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching Google Maps data: {e}", exc_info=True)
        
        # Return minimal fallback data
        encoded_query = request.query.replace(' ', '+').replace(',', '%2C')
        return GoogleMapsResponse(
            image=None,
            mapsUrl=f"https://www.google.com/maps/search/{encoded_query}",
            directionsUrl=f"https://www.google.com/maps/dir//{encoded_query}"
        )

# Mount static files for frontend assets
try:
    app.mount("/static", StaticFiles(directory="../frontend"), name="static")
    logger.info("✅ Static files mounted successfully")
except RuntimeError as e:
    logger.warning(f"⚠️ Frontend static files directory not found: {e}")

# Development server configuration
if __name__ == "__main__":
    try:
        logger.info(f"🚀 Starting server on {config.HOST}:{config.PORT}")
        uvicorn.run(
            "main:app",
            host=config.HOST,
            port=config.PORT,
            reload=config.DEBUG,
            log_level="info" if config.DEBUG else "warning"
        )
    except Exception as e:
        logger.critical(f"Failed to start server: {e}")
        raise 