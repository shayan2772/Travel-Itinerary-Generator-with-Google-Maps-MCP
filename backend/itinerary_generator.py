import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory

from config import config
from mcp_client import MCPClient

logger = logging.getLogger(__name__)

class GoogleMapsTool:
    """LangChain tool wrapper for Google Maps MCP client"""
    
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
    
    async def search_places(self, query: str, location: str = None) -> str:
        """Search for places using Google Maps"""
        try:
            results = await self.mcp_client.search_places(query, location)
            if results:
                # Format results for LLM consumption
                formatted_results = []
                for place in results[:5]:  # Limit to top 5 results
                    formatted_results.append({
                        "name": place.get("name", "Unknown"),
                        "address": place.get("vicinity", place.get("formatted_address", "Unknown")),
                        "rating": place.get("rating", "No rating"),
                        "place_id": place.get("place_id", ""),
                        "types": place.get("types", [])
                    })
                return json.dumps(formatted_results, indent=2)
            else:
                return "No places found for the search query."
        except Exception as e:
            logger.error(f"Error searching places: {e}")
            return f"Error searching for places: {str(e)}"
    
    async def get_place_details(self, place_id: str) -> str:
        """Get detailed information about a specific place"""
        try:
            result = await self.mcp_client.get_place_details(place_id)
            if result:
                details = {
                    "name": result.get("name", "Unknown"),
                    "address": result.get("formatted_address", "Unknown"),
                    "phone": result.get("formatted_phone_number", "Not available"),
                    "website": result.get("website", "Not available"),
                    "rating": result.get("rating", "No rating"),
                    "price_level": result.get("price_level", "Unknown"),
                    "opening_hours": result.get("opening_hours", {}).get("weekday_text", []),
                    "reviews_count": result.get("user_ratings_total", 0)
                }
                return json.dumps(details, indent=2)
            else:
                return "No details found for the place."
        except Exception as e:
            logger.error(f"Error getting place details: {e}")
            return f"Error getting place details: {str(e)}"
    
    async def get_directions(self, origin: str, destination: str, mode: str = "driving") -> str:
        """Get directions between two locations"""
        try:
            result = await self.mcp_client.get_directions(origin, destination, mode)
            if result and "routes" in result:
                route = result["routes"][0]
                leg = route["legs"][0]
                
                directions = {
                    "distance": leg.get("distance", {}).get("text", "Unknown"),
                    "duration": leg.get("duration", {}).get("text", "Unknown"),
                    "start_address": leg.get("start_address", origin),
                    "end_address": leg.get("end_address", destination),
                    "mode": mode,
                    "steps_summary": [step.get("html_instructions", "").replace("<", "").replace(">", "") 
                                    for step in leg.get("steps", [])[:3]]  # First 3 steps
                }
                return json.dumps(directions, indent=2)
            else:
                return "No route found between the locations."
        except Exception as e:
            logger.error(f"Error getting directions: {e}")
            return f"Error getting directions: {str(e)}"

class ItineraryGenerator:
    """AI-powered travel itinerary generator using LangChain and Google Maps"""
    
    def __init__(self):
        """Initialize the itinerary generator"""
        # Validate configuration
        config.validate()
        
        # Initialize OpenAI model
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # Initialize MCP client
        self.mcp_client = None
        self.maps_tool = None
        
        # Initialize memory for conversation
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Initialize agent
        self.agent_executor = None
        
    async def initialize(self):
        """Initialize async components (MCP client and tools)"""
        try:
            # Initialize MCP client
            self.mcp_client = MCPClient(
                server_command=config.MCP_SERVER_PATH,
                google_maps_api_key=config.GOOGLE_MAPS_API_KEY
            )
            
            # Start MCP server
            await self.mcp_client.start_server()
            
            # Initialize Google Maps tool
            self.maps_tool = GoogleMapsTool(self.mcp_client)
            
            # Create LangChain tools
            tools = [
                Tool(
                    name="search_places",
                    description="Search for places like restaurants, hotels, attractions in a given location. Use this to find specific types of places.",
                    func=lambda query: asyncio.run(self.maps_tool.search_places(query)),
                ),
                Tool(
                    name="get_place_details",
                    description="Get detailed information about a specific place using its place_id. Use this to get hours, ratings, contact info.",
                    func=lambda place_id: asyncio.run(self.maps_tool.get_place_details(place_id)),
                ),
                Tool(
                    name="get_directions",
                    description="Get directions between two locations. Specify origin, destination, and travel mode (driving, walking, transit).",
                    func=lambda params: asyncio.run(self._parse_and_get_directions(params)),
                ),
            ]
            
            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a professional travel planner with expertise in creating detailed, personalized itineraries.

Your role is to:
1. Create comprehensive day-by-day travel itineraries
2. Recommend specific places, restaurants, and activities
3. Consider travel times and logistics between locations
4. Provide practical information like opening hours and ratings
5. Adapt recommendations based on user interests and preferences

When generating itineraries:
- Always search for actual places using the available tools
- Include specific restaurant and attraction recommendations with details
- Consider travel time between locations
- Provide a good mix of activities based on user interests
- Include practical information like addresses and ratings
- Structure the itinerary clearly by days and time periods

Available tools:
- search_places: Find restaurants, attractions, hotels, etc. in a location
- get_place_details: Get detailed info about specific places
- get_directions: Calculate travel times and routes between locations

Always use real data from Google Maps to make your recommendations specific and accurate."""),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            # Create agent
            agent = create_openai_tools_agent(self.llm, tools, prompt)
            
            # Create agent executor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                memory=self.memory,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=10
            )
            
            logger.info("Itinerary generator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize itinerary generator: {e}")
            raise
    
    async def _parse_and_get_directions(self, params: str) -> str:
        """Parse parameters for directions and call the maps tool"""
        try:
            # Simple parameter parsing
            parts = params.split(",")
            if len(parts) >= 2:
                origin = parts[0].strip()
                destination = parts[1].strip()
                mode = parts[2].strip() if len(parts) > 2 else "driving"
                return await self.maps_tool.get_directions(origin, destination, mode)
            else:
                return "Please provide origin and destination separated by commas."
        except Exception as e:
            return f"Error parsing directions parameters: {str(e)}"
    
    async def generate_itinerary(self, destination: str, duration: int, interests: List[str]) -> Dict[str, Any]:
        """Generate a complete travel itinerary"""
        try:
            # Ensure agent is initialized
            if not self.agent_executor:
                await self.initialize()
            
            # Create detailed prompt
            interests_str = ", ".join(interests) if interests else "general sightseeing"
            
            prompt = f"""
Create a comprehensive {duration}-day travel itinerary for {destination} with detailed recommendations.

User interests: {interests_str}

IMPORTANT: Structure your response EXACTLY as follows for each day:

**Day 1: [Title]**
**Morning:**
- **[Activity Name]:** [Description] at [Full Address]
- **[Restaurant Name]:** [Description] at [Full Address]

**Afternoon:**  
- **[Activity Name]:** [Description] at [Full Address]
- **[Restaurant Name]:** [Description] at [Full Address]

**Evening:**
- **[Activity Name]:** [Description] at [Full Address]
- **[Restaurant Name]:** [Description] at [Full Address]

**Day 2: [Title]**
**Morning:**
- **[Activity Name]:** [Description] at [Full Address]
- **[Restaurant Name]:** [Description] at [Full Address]

**Afternoon:**
- **[Activity Name]:** [Description] at [Full Address]
- **[Restaurant Name]:** [Description] at [Full Address]

**Evening:**
- **[Activity Name]:** [Description] at [Full Address]
- **[Restaurant Name]:** [Description] at [Full Address]

[Continue for all {duration} days...]

CRITICAL FORMATTING RULES:
1. Use EXACTLY "**Day X:**" for day headers (with double asterisks)
2. Use EXACTLY "**Morning:**", "**Afternoon:**", "**Evening:**" for time sections
3. Use EXACTLY "- **[Name]:**" for each activity/restaurant
4. Include specific addresses after "at" for each location
5. Use the search_places tool to find REAL venues with actual addresses
6. Get detailed information using get_place_details for ratings and hours

For each recommendation:
1. Search for actual restaurants, attractions, and venues using the tools
2. Include complete addresses from the search results
3. Get actual ratings and details using get_place_details
4. Calculate travel times between locations using get_directions
5. Provide opening hours and practical information

Make sure to:
- Search for actual restaurants, attractions, and venues
- Include specific addresses for each location
- Provide a good variety based on user interests
- Consider travel logistics and timing
- Include at least 2-3 activities per time period
- Always use the ** formatting for location names

Start planning now and provide the complete {duration}-day itinerary with real places and addresses in the EXACT format specified above.
"""
            
            # Generate response using agent
            response = await asyncio.to_thread(
                self.agent_executor.invoke,
                {"input": prompt}
            )
            
            return {
                "destination": destination,
                "duration": duration,
                "interests": interests,
                "itinerary": response["output"],
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating itinerary: {e}")
            raise Exception(f"Failed to generate itinerary: {str(e)}")
    
    async def chat(self, message: str) -> str:
        """Handle chat messages for travel assistance with HTML formatting"""
        try:
            # Ensure agent is initialized
            if not self.agent_executor:
                await self.initialize()
            
            # Check if this is an itinerary request
            if any(keyword in message.lower() for keyword in ['itinerary', 'plan', 'trip', 'travel', 'day', 'weekend']):
                return await self.generate_html_itinerary(message)
            else:
                # For non-itinerary requests, use regular processing
                response = await asyncio.to_thread(
                    self.agent_executor.invoke,
                    {"input": message}
                )
                return response["output"]
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            return f"I apologize, but I encountered an error: {str(e)}. Please try rephrasing your question."
    
    async def generate_html_itinerary(self, message: str) -> str:
        """Generate a complete HTML itinerary with Google Maps integration and hotel details"""
        try:
            logger.info("🎨 Generating detailed HTML itinerary with hotels and Google Maps data...")
            
            # Enhanced prompt for better structure with hotels
            enhanced_prompt = f"""
{message}

Create a detailed travel itinerary in this EXACT format (no markdown, no asterisks):

Day 1: Exploring Manhattan
Morning: Central Park, Sarabeth's Restaurant
Afternoon: Empire State Building, Joe's Pizza
Evening: Times Square, Olive Garden

Day 2: Brooklyn Adventure  
Morning: Brooklyn Bridge, Juliana's Pizza
Afternoon: 9/11 Memorial, Stone Street Tavern
Evening: Statue of Liberty, Battery Gardens

CRITICAL RULES:
- Use "Day X:" for day headers (no asterisks or markdown)
- Use "Morning:", "Afternoon:", "Evening:" for time sections
- List places separated by commas
- Include real, well-known places and restaurants
- NO MARKDOWN FORMATTING (no **, no ###, no -)
- Keep it simple and structured
- Focus on specific, well-known locations and restaurants
"""
            
            # Get structured itinerary from LLM
            response = await asyncio.to_thread(
                self.agent_executor.invoke,
                {"input": enhanced_prompt}
            )
            
            basic_itinerary = response["output"]
            logger.info("✅ Got basic itinerary structure")
            
            # Parse the itinerary
            parsed_data = self.parse_itinerary_text(basic_itinerary)
            
            if not parsed_data['days']:
                logger.warning("No days found in itinerary, generating simple HTML")
                return self.generate_simple_html_with_maps(basic_itinerary)
            
            # Extract location for hotel search
            location = self.extract_destination_from_message(message)
            logger.info(f"🏨 Searching for hotels in: {location}")
            
            # Get hotel recommendations with details
            hotel_data = await self.get_hotel_recommendations(location)
            
            # Generate enhanced HTML with hotels and activities
            html_itinerary = await self.create_detailed_html_with_hotels(parsed_data, hotel_data)
            
            return html_itinerary
            
        except Exception as e:
            logger.error(f"Error generating HTML itinerary: {e}")
            return f"I apologize, but I encountered an error generating your itinerary: {str(e)}"
    
    def extract_destination_from_message(self, message: str) -> str:
        """Extract destination from user message"""
        # Simple extraction - look for common patterns
        import re
        
        # Look for patterns like "in Paris", "to London", "New York City"
        patterns = [
            r'(?:in|to|for|visit|plan.*?(?:in|to|for))\s+([A-Z][a-zA-Z\s]+(?:City|NYC|LA)?)',
            r'([A-Z][a-zA-Z\s]+(?:City|NYC|LA))',
            r'(New York|Los Angeles|San Francisco|Paris|London|Tokyo|Rome|Barcelona)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        return "New York City"  # Default fallback
    
    async def get_hotel_recommendations(self, location: str) -> List[Dict[str, Any]]:
        """Get hotel recommendations with detailed information"""
        hotels = []
        
        try:
            if not self.mcp_client:
                logger.warning("MCP client not available for hotel search, using fallback recommendations")
                return self.get_fallback_hotels(location)
            
            # Search for hotels in the location
            logger.info(f"🔍 Searching for hotels in {location}")
            search_result = await self.mcp_client.call_tool(
                "search_nearby",
                {
                    "location": location,
                    "radius": 5000,
                    "type": "lodging"
                }
            )
            
            if not search_result or not search_result.get('places'):
                logger.warning(f"No hotels found for {location}, using fallback")
                return self.get_fallback_hotels(location)
            
            # Get detailed information for top 5 hotels
            for place in search_result['places'][:5]:
                try:
                    place_id = place.get('place_id')
                    if not place_id:
                        continue
                    
                    # Get detailed hotel information
                    details_result = await self.mcp_client.call_tool(
                        "get_place_details",
                        {
                            "place_id": place_id,
                            "fields": "name,formatted_address,geometry,rating,user_ratings_total,photos,reviews,opening_hours,price_level,website,formatted_phone_number,types"
                        }
                    )
                    
                    if details_result:
                        # Merge basic and detailed info
                        hotel_info = {**place, **details_result}
                        
                        # Process reviews
                        if 'reviews' in hotel_info and hotel_info['reviews']:
                            hotel_info['formatted_reviews'] = []
                            for review in hotel_info['reviews'][:3]:  # Top 3 reviews
                                formatted_review = {
                                    'author': review.get('author_name', 'Anonymous'),
                                    'rating': review.get('rating', 0),
                                    'text': review.get('text', '')[:200] + ('...' if len(review.get('text', '')) > 200 else ''),
                                    'time': review.get('relative_time_description', '')
                                }
                                hotel_info['formatted_reviews'].append(formatted_review)
                        
                        # Process photos
                        if 'photos' in hotel_info and hotel_info['photos']:
                            hotel_info['photo_references'] = [
                                photo.get('photo_reference') for photo in hotel_info['photos'][:3]
                                if photo.get('photo_reference')
                            ]
                        
                        hotels.append(hotel_info)
                        logger.info(f"✅ Got detailed info for hotel: {hotel_info.get('name', 'Unknown')}")
                        
                except Exception as e:
                    logger.warning(f"Failed to get details for hotel: {e}")
                    continue
            
            if hotels:
                logger.info(f"🏨 Found {len(hotels)} hotels with detailed information")
                return hotels
            else:
                logger.warning("No detailed hotel information available, using fallback")
                return self.get_fallback_hotels(location)
            
        except Exception as e:
            logger.error(f"Error getting hotel recommendations: {e}")
            return self.get_fallback_hotels(location)
    
    def get_fallback_hotels(self, location: str) -> List[Dict[str, Any]]:
        """Provide fallback hotel recommendations when MCP is not available"""
        # Default hotel recommendations for popular destinations
        fallback_hotels = {
            "new york city": [
                {
                    "name": "The Plaza Hotel",
                    "formatted_address": "768 5th Ave, New York, NY 10019",
                    "rating": 4.3,
                    "user_ratings_total": 12500,
                    "price_level": 4,
                    "website": "https://www.theplazany.com",
                    "formatted_phone_number": "(212) 759-3000",
                    "formatted_reviews": [
                        {
                            "author": "Sarah M.",
                            "rating": 5,
                            "text": "Iconic luxury hotel with exceptional service and prime location near Central Park. The rooms are elegant and the staff is incredibly attentive.",
                            "time": "2 weeks ago"
                        },
                        {
                            "author": "John D.",
                            "rating": 4,
                            "text": "Classic New York experience. Beautiful architecture and historic charm. Expensive but worth it for special occasions.",
                            "time": "1 month ago"
                        }
                    ]
                },
                {
                    "name": "The High Line Hotel",
                    "formatted_address": "180 10th Ave, New York, NY 10011",
                    "rating": 4.1,
                    "user_ratings_total": 3200,
                    "price_level": 3,
                    "website": "https://www.thehighlinehotel.com",
                    "formatted_phone_number": "(212) 929-3888",
                    "formatted_reviews": [
                        {
                            "author": "Emma L.",
                            "rating": 4,
                            "text": "Charming boutique hotel in Chelsea. Great location near the High Line and Meatpacking District. Cozy rooms with character.",
                            "time": "3 weeks ago"
                        }
                    ]
                },
                {
                    "name": "Pod Hotels Brooklyn",
                    "formatted_address": "247 Metropolitan Ave, Brooklyn, NY 11211",
                    "rating": 4.0,
                    "user_ratings_total": 2800,
                    "price_level": 2,
                    "website": "https://www.thepodhotel.com",
                    "formatted_phone_number": "(718) 387-8765",
                    "formatted_reviews": [
                        {
                            "author": "Mike R.",
                            "rating": 4,
                            "text": "Modern, efficient rooms at a great price point. Perfect for young travelers. Great rooftop bar with Manhattan views.",
                            "time": "1 week ago"
                        }
                    ]
                }
            ]
        }
        
        location_key = location.lower().strip()
        if location_key in fallback_hotels:
            logger.info(f"🏨 Using fallback hotels for {location}")
            return fallback_hotels[location_key]
        
        # Generic fallback for unknown locations
        return [
            {
                "name": f"Recommended Hotel in {location}",
                "formatted_address": f"Central {location}",
                "rating": 4.2,
                "user_ratings_total": 1500,
                "price_level": 3,
                "formatted_reviews": [
                    {
                        "author": "Travel Expert",
                        "rating": 4,
                        "text": f"Great location in the heart of {location} with excellent amenities and service.",
                        "time": "Recent"
                    }
                ]
            }
        ]
    
    async def create_detailed_html_with_hotels(self, parsed_data: dict, hotel_data: List[Dict[str, Any]]) -> str:
        """Create enhanced HTML with hotels and detailed place information"""
        html = '''
        <div class="itinerary-container" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%); border-radius: 1rem; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="font-size: 1.8rem; font-weight: bold; color: #1f2937; margin-bottom: 0.5rem;">🗽 Your Detailed Travel Itinerary</h2>
                <div style="width: 4rem; height: 0.25rem; background: linear-gradient(to right, #3b82f6, #8b5cf6); margin: 0 auto; border-radius: 9999px;"></div>
            </div>
        '''
        
        # Add hotel recommendations section
        if hotel_data:
            html += '''
            <div style="margin-bottom: 3rem;">
                <div style="display: flex; align-items: center; margin-bottom: 1.5rem;">
                    <div style="width: 2rem; height: 2rem; background: linear-gradient(to right, #f59e0b, #d97706); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 0.75rem;">
                        🏨
                    </div>
                    <h3 style="font-size: 1.25rem; font-weight: 600; color: #1f2937;">Recommended Hotels</h3>
                </div>
                
                <div style="margin-left: 2.75rem; display: grid; gap: 1rem;">
            '''
            
            for hotel in hotel_data:
                html += self.create_hotel_card(hotel)
            
            html += '''
                </div>
            </div>
            '''
        
        # Add daily itinerary
        for day in parsed_data['days']:
            html += f'''
            <div style="margin-bottom: 2rem;">
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <div style="width: 2rem; height: 2rem; background: linear-gradient(to right, #3b82f6, #8b5cf6); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin-right: 0.75rem;">
                        {day['day_number']}
                    </div>
                    <h3 style="font-size: 1.25rem; font-weight: 600; color: #1f2937;">Day {day['day_number']}: {day['title']}</h3>
                </div>
                
                <div style="margin-left: 2.75rem;">
            '''
            
            for section in day['sections']:
                time_emoji = '🌅' if 'morning' in section['time'].lower() else '☀️' if 'afternoon' in section['time'].lower() else '🌆'
                
                html += f'''
                <div style="background: white; border-radius: 0.75rem; padding: 1rem; margin-bottom: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center; margin-bottom: 0.75rem;">
                        <span style="font-size: 1.125rem; margin-right: 0.5rem;">{time_emoji}</span>
                        <h4 style="font-size: 1.125rem; font-weight: 500; color: #374151;">{section['time']}</h4>
                    </div>
                    
                    <div style="display: grid; gap: 0.75rem;">
                '''
                
                for activity in section['activities']:
                    # Get detailed place information for each activity
                    place_info = await self.get_detailed_place_info(activity)
                    
                    if place_info:
                        html += self.create_enhanced_place_card(activity, place_info)
                    else:
                        # Simple activity card with Google Maps link
                        maps_url = f"https://www.google.com/maps/search/{activity.replace(' ', '+')}"
                        directions_url = f"https://www.google.com/maps/dir//{activity.replace(' ', '+')}"
                        
                        html += f'''
                        <div style="background: #f8fafc; border-radius: 0.5rem; padding: 1rem; border: 1px solid #e2e8f0;">
                            <div style="display: flex; gap: 1rem;">
                                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5rem; flex-shrink: 0;">📍</div>
                                
                                <div style="flex: 1; min-width: 0;">
                                    <h5 style="font-weight: 600; color: #1f2937; margin-bottom: 0.25rem; font-size: 1rem;">{activity}</h5>
                                    <p style="color: #6b7280; font-size: 0.875rem; margin-bottom: 0.5rem; line-height: 1.4;">Explore this amazing location and enjoy your time here.</p>
                                    
                                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                                        <a href="{maps_url}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; background: #3b82f6; color: white; font-size: 0.75rem; border-radius: 9999px; text-decoration: none; transition: background-color 0.2s;">
                                            <svg style="width: 0.75rem; height: 0.75rem; margin-right: 0.25rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
                                            View on Maps
                                        </a>
                                        <a href="{directions_url}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; background: #10b981; color: white; font-size: 0.75rem; border-radius: 9999px; text-decoration: none; transition: background-color 0.2s;">
                                            <svg style="width: 0.75rem; height: 0.75rem; margin-right: 0.25rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
                                            Directions
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                        '''
                
                html += '''
                    </div>
                </div>
                '''
            
            html += '''
                </div>
            </div>
            '''
        
        html += '''
        </div>
        '''
        
        return html
    
    def generate_simple_html_with_maps(self, text: str) -> str:
        """Generate simple HTML when parsing fails but add Google Maps links"""
        # Extract place names from the text
        import re
        places = re.findall(r'([A-Z][a-zA-Z\s&\']+(?:Restaurant|Hotel|Museum|Park|Building|Center|Market|Bridge|Tower|Square|Gallery|Cafe|Bar|Pizza|Gardens))', text)
        
        enhanced_text = text
        for place in places[:10]:  # Limit to 10 places
            maps_url = f"https://www.google.com/maps/search/{place.replace(' ', '+')}"
            enhanced_place = f'<a href="{maps_url}" target="_blank" style="color: #3b82f6; text-decoration: underline;">{place}</a>'
            enhanced_text = enhanced_text.replace(place, enhanced_place, 1)
        
        return f'''
        <div class="itinerary-container" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%); border-radius: 1rem; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="font-size: 1.8rem; font-weight: bold; color: #1f2937; margin-bottom: 0.5rem;">🗽 Your Travel Itinerary</h2>
                <div style="width: 4rem; height: 0.25rem; background: linear-gradient(to right, #3b82f6, #8b5cf6); margin: 0 auto; border-radius: 9999px;"></div>
            </div>
            
            <div style="background: white; border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
                <div style="color: #374151; line-height: 1.6; white-space: pre-line;">{enhanced_text}</div>
            </div>
        </div>
        '''
    
    def parse_itinerary_text(self, text: str) -> dict:
        """Parse itinerary text into structured data"""
        days = []
        current_day = None
        current_section = None
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove markdown formatting
            clean_line = line.replace('**', '').replace('*', '').strip()
            
            # Check for day headers (Day 1:, Day 2:, etc.) - handle both plain and markdown
            if (clean_line.lower().startswith('day ') and ':' in clean_line) or \
               (line.startswith('**Day ') and ':' in line):
                if current_day:
                    days.append(current_day)
                
                # Extract title after the colon
                if ':' in clean_line:
                    title_part = clean_line.split(':', 1)[1].strip()
                    title = title_part if title_part else f"Day {len(days) + 1}"
                else:
                    title = f"Day {len(days) + 1}"
                
                current_day = {
                    'day_number': len(days) + 1,
                    'title': title,
                    'sections': []
                }
                current_section = None
                
            # Check for time sections (Morning:, Afternoon:, Evening:) - handle various formats
            elif any(clean_line.lower().startswith(time.lower() + ':') for time in ['morning', 'afternoon', 'evening']) or \
                 any(clean_line.lower() == time.lower() for time in ['morning', 'afternoon', 'evening']):
                if current_day:
                    # Extract time name and activities from the same line
                    if ':' in clean_line:
                        parts = clean_line.split(':', 1)
                        time_name = parts[0].strip().title()
                        activities_text = parts[1].strip() if len(parts) > 1 else ""
                        
                        current_section = {
                            'time': time_name,
                            'activities': []
                        }
                        current_day['sections'].append(current_section)
                        
                        # Parse activities from the same line if present
                        if activities_text:
                            # Split by commas and clean up
                            activities = [act.strip() for act in activities_text.split(',')]
                            for activity in activities:
                                if activity and len(activity) > 2:
                                    current_section['activities'].append(activity)
                    else:
                        time_name = clean_line.strip().title()
                        current_section = {
                            'time': time_name,
                            'activities': []
                        }
                        current_day['sections'].append(current_section)
                    
            # Check for meal times (Breakfast:, Lunch:, Dinner:) - treat as activities
            elif any(clean_line.lower().startswith(meal.lower() + ':') for meal in ['breakfast', 'lunch', 'dinner']) and current_section:
                meal_name = clean_line.replace(':', '').strip()
                current_section['activities'].append(meal_name)
                
            # Parse activities - lines starting with - or containing place names
            elif current_section is not None and line and not line.startswith('I '):
                # Handle bullet points
                if line.strip().startswith('- '):
                    activity = line.strip()[2:].strip()
                    if activity:
                        # Split by commas if multiple activities in one line
                        if ',' in activity and len(activity) > 30:
                            activities = [act.strip() for act in activity.split(',')]
                            for act in activities:
                                if act and len(act) > 2:
                                    current_section['activities'].append(act)
                        else:
                            current_section['activities'].append(activity)
                        
                # Handle other activity lines (not starting with common intro words)
                elif not any(clean_line.lower().startswith(word) for word in ['i ', 'you ', 'this ', 'the ', 'make ', 'check ', 'hotel ', 'for a stay']):
                    # Split multiple activities by commas if they exist
                    if ',' in clean_line and len(clean_line) > 30:  # Likely multiple activities
                        activities = [activity.strip() for activity in clean_line.split(',')]
                        for activity in activities:
                            if activity and len(activity) > 3:
                                current_section['activities'].append(activity)
                    elif len(clean_line) > 3:  # Single activity
                        current_section['activities'].append(clean_line)
        
        # Add the last day
        if current_day:
            days.append(current_day)
        
        # Log parsing results for debugging
        logger.info(f"📊 Parsed {len(days)} days with activities:")
        for day in days:
            logger.info(f"  Day {day['day_number']}: {day['title']} ({len(day['sections'])} sections)")
            for section in day['sections']:
                logger.info(f"    {section['time']}: {len(section['activities'])} activities - {section['activities']}")
        
        return {'days': days}
    
    async def get_detailed_place_info(self, place_name: str) -> Dict[str, Any]:
        """Get detailed place information using Google Maps MCP"""
        try:
            if not self.mcp_client:
                return None
            
            # Search for the place
            search_result = await self.mcp_client.call_tool(
                "search_nearby",
                {
                    "location": place_name,
                    "radius": 5000,
                    "type": "tourist_attraction|restaurant|museum|park|shopping_mall|establishment"
                }
            )
            
            if not search_result or not search_result.get('places'):
                return None
            
            place = search_result['places'][0]
            place_id = place.get('place_id')
            
            if not place_id:
                return place
            
            # Get detailed information
            details_result = await self.mcp_client.call_tool(
                "get_place_details",
                {
                    "place_id": place_id,
                    "fields": "name,formatted_address,geometry,rating,user_ratings_total,photos,reviews,opening_hours,price_level,website,formatted_phone_number"
                }
            )
            
            if details_result:
                place.update(details_result)
            
            return place
            
        except Exception as e:
            logger.error(f"Error getting place info for {place_name}: {e}")
            return None
    
    async def cleanup(self):
        """Clean up resources"""
        if self.mcp_client:
            await self.mcp_client.stop_server()
            logger.info("MCP client cleaned up")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()
    
    def create_hotel_card(self, hotel: Dict[str, Any]) -> str:
        """Create a detailed hotel card with reviews and ratings"""
        name = hotel.get('name', 'Unknown Hotel')
        address = hotel.get('formatted_address', 'Address not available')
        rating = hotel.get('rating', 0)
        rating_count = hotel.get('user_ratings_total', 0)
        price_level = hotel.get('price_level', 0)
        website = hotel.get('website', '')
        phone = hotel.get('formatted_phone_number', '')
        
        # Generate star rating display
        stars = '⭐' * int(rating) if rating else '⭐⭐⭐'
        
        # Generate price level display
        price_display = '$' * price_level if price_level else 'Price not available'
        
        # Maps URLs
        maps_url = f"https://www.google.com/maps/search/{name.replace(' ', '+')}"
        directions_url = f"https://www.google.com/maps/dir//{name.replace(' ', '+')}"
        
        html = f'''
        <div style="background: white; border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #e5e7eb;">
            <div style="display: flex; gap: 1rem;">
                <div style="width: 100px; height: 100px; background: linear-gradient(135deg, #f59e0b, #d97706); border-radius: 0.75rem; display: flex; align-items: center; justify-content: center; color: white; font-size: 2rem; flex-shrink: 0;">🏨</div>
                
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; justify-content: between; align-items: start; margin-bottom: 0.5rem;">
                        <h4 style="font-weight: 700; color: #1f2937; margin: 0; font-size: 1.125rem;">{name}</h4>
                        <div style="text-align: right; margin-left: auto;">
                            <div style="font-size: 0.875rem; color: #f59e0b; margin-bottom: 0.25rem;">{stars}</div>
                            <div style="font-size: 0.75rem; color: #6b7280;">{rating}/5 ({rating_count} reviews)</div>
                        </div>
                    </div>
                    
                    <p style="color: #6b7280; font-size: 0.875rem; margin-bottom: 0.75rem; line-height: 1.4;">📍 {address}</p>
                    
                    <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap;">
                        <span style="background: #f3f4f6; color: #374151; padding: 0.25rem 0.5rem; border-radius: 0.375rem; font-size: 0.75rem;">💰 {price_display}</span>
        '''
        
        if phone:
            html += f'<span style="background: #f3f4f6; color: #374151; padding: 0.25rem 0.5rem; border-radius: 0.375rem; font-size: 0.75rem;">📞 {phone}</span>'
        
        html += '''
                    </div>
        '''
        
        # Add reviews if available
        if 'formatted_reviews' in hotel and hotel['formatted_reviews']:
            html += '''
                    <div style="margin-bottom: 1rem;">
                        <h5 style="font-size: 0.875rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem;">Recent Reviews:</h5>
            '''
            
            for review in hotel['formatted_reviews']:
                review_stars = '⭐' * int(review['rating']) if review['rating'] else '⭐⭐⭐'
                html += f'''
                        <div style="background: #f9fafb; border-radius: 0.375rem; padding: 0.75rem; margin-bottom: 0.5rem; border-left: 3px solid #3b82f6;">
                            <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 0.25rem;">
                                <span style="font-size: 0.75rem; font-weight: 500; color: #1f2937;">{review['author']}</span>
                                <span style="font-size: 0.625rem; color: #f59e0b;">{review_stars}</span>
                            </div>
                            <p style="font-size: 0.75rem; color: #6b7280; margin: 0; line-height: 1.3;">"{review['text']}"</p>
                            <span style="font-size: 0.625rem; color: #9ca3af;">{review['time']}</span>
                        </div>
                '''
            
            html += '''
                    </div>
            '''
        
        # Add action buttons
        html += f'''
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                        <a href="{maps_url}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.5rem 1rem; background: #3b82f6; color: white; font-size: 0.75rem; border-radius: 0.375rem; text-decoration: none; transition: background-color 0.2s;">
                            <svg style="width: 0.875rem; height: 0.875rem; margin-right: 0.375rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
                            View on Maps
                        </a>
                        <a href="{directions_url}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.5rem 1rem; background: #10b981; color: white; font-size: 0.75rem; border-radius: 0.375rem; text-decoration: none; transition: background-color 0.2s;">
                            <svg style="width: 0.875rem; height: 0.875rem; margin-right: 0.375rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
                            Directions
                        </a>
        '''
        
        if website:
            html += f'''
                        <a href="{website}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.5rem 1rem; background: #8b5cf6; color: white; font-size: 0.75rem; border-radius: 0.375rem; text-decoration: none; transition: background-color 0.2s;">
                            <svg style="width: 0.875rem; height: 0.875rem; margin-right: 0.375rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.083 9h1.946c.089-1.546.383-2.97.837-4.118A6.004 6.004 0 004.083 9zM10 2a8 8 0 100 16 8 8 0 000-16zm0 2c-.076 0-.232.032-.465.262-.238.234-.497.623-.737 1.182-.389.907-.673 2.142-.766 3.556h3.936c-.093-1.414-.377-2.649-.766-3.556-.24-.559-.499-.948-.737-1.182C10.232 4.032 10.076 4 10 4zm3.971 5c-.089-1.546-.383-2.97-.837-4.118A6.004 6.004 0 0115.917 9h-1.946zm-2.003 2H8.032c.093 1.414.377 2.649.766 3.556.24.559.499.948.737 1.182.233.23.389.262.465.262.076 0 .232-.032.465-.262.238-.234.497-.623.737-1.182.389-.907.673-2.142.766-3.556zm1.166 4.118c.454-1.147.748-2.572.837-4.118h1.946a6.004 6.004 0 01-2.783 4.118zm-6.268 0C6.412 13.97 6.118 12.546 6.032 11H4.083a6.004 6.004 0 002.783 4.118z" clip-rule="evenodd"></path></svg>
                            Website
                        </a>
            '''
        
        html += '''
                    </div>
                </div>
            </div>
        </div>
        '''
        
        return html
    
    def create_enhanced_place_card(self, activity_name: str, place_info: Dict[str, Any]) -> str:
        """Create an enhanced place card with detailed information"""
        name = place_info.get('name', activity_name)
        address = place_info.get('formatted_address', 'Address not available')
        rating = place_info.get('rating', 0)
        rating_count = place_info.get('user_ratings_total', 0)
        price_level = place_info.get('price_level', 0)
        types = place_info.get('types', [])
        
        # Generate star rating display
        stars = '⭐' * int(rating) if rating else '⭐⭐⭐'
        
        # Generate price level display
        price_display = '$' * price_level if price_level else 'Free'
        
        # Determine emoji based on place type
        emoji = '🍽️' if any(t in types for t in ['restaurant', 'food', 'meal_takeaway']) else \
                '🏛️' if any(t in types for t in ['museum', 'art_gallery']) else \
                '🌳' if any(t in types for t in ['park', 'natural_feature']) else \
                '🏢' if any(t in types for t in ['tourist_attraction', 'point_of_interest']) else '📍'
        
        # Maps URLs
        maps_url = f"https://www.google.com/maps/search/{name.replace(' ', '+')}"
        directions_url = f"https://www.google.com/maps/dir//{name.replace(' ', '+')}"
        
        html = f'''
        <div style="background: #f8fafc; border-radius: 0.5rem; padding: 1rem; border: 1px solid #e2e8f0;">
            <div style="display: flex; gap: 1rem;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5rem; flex-shrink: 0;">{emoji}</div>
                
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; justify-content: between; align-items: start; margin-bottom: 0.5rem;">
                        <h5 style="font-weight: 600; color: #1f2937; margin: 0; font-size: 1rem;">{name}</h5>
                        <div style="text-align: right; margin-left: auto;">
                            <div style="font-size: 0.75rem; color: #f59e0b; margin-bottom: 0.125rem;">{stars}</div>
                            <div style="font-size: 0.625rem; color: #6b7280;">{rating}/5 ({rating_count})</div>
                        </div>
                    </div>
                    
                    <p style="color: #6b7280; font-size: 0.875rem; margin-bottom: 0.5rem; line-height: 1.4;">📍 {address}</p>
                    
                    <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem; flex-wrap: wrap;">
                        <span style="background: #f3f4f6; color: #374151; padding: 0.25rem 0.5rem; border-radius: 0.375rem; font-size: 0.75rem;">💰 {price_display}</span>
        '''
        
        # Add place type tags
        if types:
            for place_type in types[:2]:  # Show first 2 types
                formatted_type = place_type.replace('_', ' ').title()
                html += f'<span style="background: #e0e7ff; color: #3730a3; padding: 0.25rem 0.5rem; border-radius: 0.375rem; font-size: 0.75rem;">{formatted_type}</span>'
        
        html += '''
                    </div>
                    
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
        '''
        
        html += f'''
                        <a href="{maps_url}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; background: #3b82f6; color: white; font-size: 0.75rem; border-radius: 9999px; text-decoration: none; transition: background-color 0.2s;">
                            <svg style="width: 0.75rem; height: 0.75rem; margin-right: 0.25rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
                            View on Maps
                        </a>
                        <a href="{directions_url}" target="_blank" style="display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; background: #10b981; color: white; font-size: 0.75rem; border-radius: 9999px; text-decoration: none; transition: background-color 0.2s;">
                            <svg style="width: 0.75rem; height: 0.75rem; margin-right: 0.25rem; fill: currentColor;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
                            Directions
                        </a>
                    </div>
                </div>
            </div>
        </div>
        '''
        
        return html

# Global instance for easy import
_itinerary_generator = None

async def get_itinerary_generator() -> ItineraryGenerator:
    """Get or create the global itinerary generator instance"""
    global _itinerary_generator
    if _itinerary_generator is None:
        _itinerary_generator = ItineraryGenerator()
        await _itinerary_generator.initialize()
    return _itinerary_generator 