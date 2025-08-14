import asyncio
import json
import os
import subprocess
from typing import Dict, Any, List, Optional, Union
import logging
import httpx

from exceptions import MCPServerError, NetworkError, GoogleMapsError, ConfigurationError

logger = logging.getLogger(__name__)

class MCPClient:
    """Client for communicating with Google Maps MCP server via JSON-RPC"""
    
    def __init__(self, server_command: str, google_maps_api_key: str):
        """
        Initialize MCP client
        
        Args:
            server_command: Command to start the MCP server (e.g., "npx -y @cablate/mcp-google-map")
            google_maps_api_key: Google Maps API key
        """
        self.server_command = server_command
        self.google_maps_api_key = google_maps_api_key
        self.process = None
        self.request_id = 1
        
        # Validate inputs
        if not server_command or not server_command.strip():
            raise ConfigurationError("MCP server command cannot be empty")
        
        if not google_maps_api_key or not google_maps_api_key.strip():
            raise ConfigurationError("Google Maps API key cannot be empty")
        
    async def start_server(self) -> bool:
        """Start the MCP server process"""
        try:
            logger.info(f"🚀 Starting MCP server with command: {self.server_command}")
            
            # Set up environment with API key
            env = os.environ.copy()
            env['GOOGLE_MAPS_API_KEY'] = self.google_maps_api_key
            
            # Start server process
            cmd_parts = self.server_command.split()
            self.process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Read the startup message with timeout
            try:
                startup_line = await asyncio.wait_for(self.process.stdout.readline(), timeout=15.0)
                startup_message = startup_line.decode().strip()
                logger.info(f"MCP server startup message: {startup_message}")
                
                if "started" not in startup_message.lower():
                    raise MCPServerError(f"Unexpected startup message: {startup_message}", server_status="startup_failed")
                
            except asyncio.TimeoutError:
                raise MCPServerError("MCP server startup timeout - server failed to start within 15 seconds", server_status="startup_timeout")
            
            # Verify process is running
            if self.process.returncode is not None:
                stderr_output = ""
                try:
                    stderr_data = await asyncio.wait_for(self.process.stderr.read(1024), timeout=2.0)
                    stderr_output = stderr_data.decode().strip()
                except:
                    pass
                
                raise MCPServerError(
                    f"MCP server process exited during startup (exit code: {self.process.returncode}). {stderr_output}",
                    server_status="process_exited"
                )
            
            logger.info(f"✅ MCP server started successfully")
            return True
            
        except MCPServerError:
            # Re-raise MCP server errors
            await self._cleanup_process()
            raise
        except FileNotFoundError as e:
            await self._cleanup_process()
            raise ConfigurationError(f"MCP server command not found: {self.server_command}. Please ensure it's installed and in PATH.")
        except PermissionError as e:
            await self._cleanup_process()
            raise ConfigurationError(f"Permission denied when starting MCP server: {e}")
        except Exception as e:
            await self._cleanup_process()
            raise MCPServerError(f"Failed to start MCP server: {str(e)}", server_status="startup_failed")
    
    async def _cleanup_process(self):
        """Clean up the process in case of errors"""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except:
                pass
            self.process = None
    
    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request to MCP server"""
        if not self.process:
            raise MCPServerError("MCP server not started. Call start_server() first.", server_status="not_started")
        
        # Check if process is still running
        if self.process.returncode is not None:
            raise MCPServerError(f"MCP server process has exited (exit code: {self.process.returncode})", server_status="process_exited")
        
        # Prepare JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        self.request_id += 1
        
        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()
            
            # Read response with timeout
            response_line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30.0)
            if not response_line:
                raise NetworkError("No response from MCP server", service="mcp_server", timeout=False)
            
            response = json.loads(response_line.decode().strip())
            
            # Check for JSON-RPC errors
            if "error" in response:
                error = response["error"]
                error_code = error.get('code', 'Unknown')
                error_message = error.get('message', 'Unknown error')
                
                # Categorize errors
                if "api key" in error_message.lower() or "authentication" in error_message.lower():
                    raise GoogleMapsError(f"Google Maps API authentication error: {error_message}", api_status="auth_failed")
                elif "quota" in error_message.lower() or "limit" in error_message.lower():
                    raise GoogleMapsError(f"Google Maps API quota exceeded: {error_message}", api_status="quota_exceeded")
                elif "invalid request" in error_message.lower():
                    raise GoogleMapsError(f"Invalid request to Google Maps API: {error_message}", api_status="invalid_request")
                else:
                    raise MCPServerError(f"MCP server error: {error_message} (Code: {error_code})", server_status="request_failed")
            
            return response.get("result", {})
            
        except asyncio.TimeoutError:
            raise NetworkError("Timeout waiting for MCP server response", service="mcp_server", timeout=True)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from MCP server: {e}")
            raise MCPServerError("Invalid JSON response from MCP server", server_status="invalid_response")
        except (GoogleMapsError, MCPServerError, NetworkError):
            # Re-raise categorized errors
            raise
        except Exception as e:
            logger.error(f"Error communicating with MCP server: {e}")
            raise NetworkError(f"Communication error with MCP server: {str(e)}", service="mcp_server")
    
    async def search_places(self, query: str, location: Optional[str] = None, radius: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for places using Google Maps (using correct search_nearby tool)
        
        Args:
            query: Search query (e.g., "restaurants", "hotels")
            location: Location to search around (address or coordinates)
            radius: Search radius in meters (default: 1000)
            
        Returns:
            List of places with details
        """
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return []
        
        # Prepare center parameter based on server schema
        center = {"value": location or "Times Square, New York"}
        
        params = {
            "center": center,
            "keyword": query.strip()
        }
        
        if radius and radius > 0:
            params["radius"] = min(radius, 50000)  # Cap at 50km for safety
        
        try:
            logger.debug(f"Searching places: {query} near {location}")
            result = await self._send_request("tools/call", {
                "name": "search_nearby",
                "arguments": params
            })
            
            # Extract content from result
            content = result.get("content", [])
            if isinstance(content, list):
                return content
            elif isinstance(content, dict):
                return [content]
            else:
                return []
                
        except (GoogleMapsError, MCPServerError, NetworkError):
            # Re-raise categorized errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching places: {e}")
            raise GoogleMapsError(f"Failed to search places: {str(e)}", api_status="search_failed")
    
    async def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific place
        
        Args:
            place_id: Google Places ID
            
        Returns:
            Detailed place information
        """
        if not place_id or not place_id.strip():
            raise GoogleMapsError("Place ID cannot be empty", api_status="invalid_input")
        
        try:
            logger.debug(f"Getting place details for: {place_id}")
            result = await self._send_request("tools/call", {
                "name": "get_place_details",
                "arguments": {"placeId": place_id.strip()}
            })
            
            content = result.get("content", {})
            return content if isinstance(content, dict) else {}
            
        except (GoogleMapsError, MCPServerError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting place details: {e}")
            raise GoogleMapsError(f"Failed to get place details: {str(e)}", api_status="details_failed")
    
    async def get_directions(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        """
        Get directions between two locations
        
        Args:
            origin: Starting location
            destination: Ending location
            mode: Travel mode ("driving", "walking", "bicycling", "transit")
            
        Returns:
            Directions with steps and route information
        """
        if not origin or not origin.strip():
            raise GoogleMapsError("Origin cannot be empty", api_status="invalid_input")
        
        if not destination or not destination.strip():
            raise GoogleMapsError("Destination cannot be empty", api_status="invalid_input")
        
        valid_modes = ["driving", "walking", "bicycling", "transit"]
        if mode not in valid_modes:
            raise GoogleMapsError(f"Invalid travel mode: {mode}. Must be one of: {', '.join(valid_modes)}", api_status="invalid_mode")
        
        try:
            logger.debug(f"Getting directions from {origin} to {destination} via {mode}")
            result = await self._send_request("tools/call", {
                "name": "maps_directions",
                "arguments": {
                    "origin": origin.strip(),
                    "destination": destination.strip(),
                    "mode": mode
                }
            })
            
            content = result.get("content", {})
            return content if isinstance(content, dict) else {}
            
        except (GoogleMapsError, MCPServerError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting directions: {e}")
            raise GoogleMapsError(f"Failed to get directions: {str(e)}", api_status="directions_failed")
    
    async def geocode(self, address: str) -> Dict[str, Any]:
        """
        Convert an address to coordinates
        
        Args:
            address: Address to geocode
            
        Returns:
            Geocoding results with coordinates
        """
        if not address or not address.strip():
            raise GoogleMapsError("Address cannot be empty", api_status="invalid_input")
        
        try:
            logger.debug(f"Geocoding address: {address}")
            result = await self._send_request("tools/call", {
                "name": "maps_geocode",
                "arguments": {"address": address.strip()}
            })
            
            content = result.get("content", {})
            return content if isinstance(content, dict) else {}
            
        except (GoogleMapsError, MCPServerError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error geocoding address: {e}")
            raise GoogleMapsError(f"Failed to geocode address: {str(e)}", api_status="geocode_failed")
    
    async def reverse_geocode(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Convert coordinates to an address
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Reverse geocoding results with address
        """
        # Validate coordinates
        if not (-90 <= lat <= 90):
            raise GoogleMapsError(f"Invalid latitude: {lat}. Must be between -90 and 90.", api_status="invalid_coordinates")
        
        if not (-180 <= lng <= 180):
            raise GoogleMapsError(f"Invalid longitude: {lng}. Must be between -180 and 180.", api_status="invalid_coordinates")
        
        try:
            logger.debug(f"Reverse geocoding coordinates: {lat}, {lng}")
            result = await self._send_request("tools/call", {
                "name": "maps_reverse_geocode",
                "arguments": {"latitude": lat, "longitude": lng}
            })
            
            content = result.get("content", {})
            return content if isinstance(content, dict) else {}
            
        except (GoogleMapsError, MCPServerError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error reverse geocoding coordinates: {e}")
            raise GoogleMapsError(f"Failed to reverse geocode coordinates: {str(e)}", api_status="reverse_geocode_failed")
    
    async def get_distance_matrix(self, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict[str, Any]:
        """
        Get distance and time between multiple origins and destinations
        
        Args:
            origins: List of origin addresses
            destinations: List of destination addresses
            mode: Travel mode ("driving", "walking", "bicycling", "transit")
            
        Returns:
            Distance matrix with travel times and distances
        """
        if not origins or not all(origin.strip() for origin in origins):
            raise GoogleMapsError("Origins list cannot be empty or contain empty strings", api_status="invalid_input")
        
        if not destinations or not all(dest.strip() for dest in destinations):
            raise GoogleMapsError("Destinations list cannot be empty or contain empty strings", api_status="invalid_input")
        
        # Limit to reasonable number of requests
        if len(origins) * len(destinations) > 100:
            raise GoogleMapsError("Too many origin-destination combinations. Maximum 100 combinations allowed.", api_status="request_too_large")
        
        valid_modes = ["driving", "walking", "bicycling", "transit"]
        if mode not in valid_modes:
            raise GoogleMapsError(f"Invalid travel mode: {mode}. Must be one of: {', '.join(valid_modes)}", api_status="invalid_mode")
        
        try:
            logger.debug(f"Getting distance matrix for {len(origins)} origins and {len(destinations)} destinations")
            result = await self._send_request("tools/call", {
                "name": "maps_distance_matrix",
                "arguments": {
                    "origins": [origin.strip() for origin in origins],
                    "destinations": [dest.strip() for dest in destinations],
                    "mode": mode
                }
            })
            
            content = result.get("content", {})
            return content if isinstance(content, dict) else {}
            
        except (GoogleMapsError, MCPServerError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting distance matrix: {e}")
            raise GoogleMapsError(f"Failed to get distance matrix: {str(e)}", api_status="distance_matrix_failed")
    
    async def stop_server(self):
        """Stop the MCP server process"""
        if self.process:
            try:
                logger.info("🛑 Stopping MCP server...")
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
                logger.info("✅ MCP server stopped successfully")
            except asyncio.TimeoutError:
                logger.warning("⚠️ MCP server shutdown timeout, forcing termination")
                self.process.kill()
                await self.process.wait()
            except Exception as e:
                logger.error(f"⚠️ Error stopping MCP server: {e}")
            finally:
                self.process = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_server()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_server() 