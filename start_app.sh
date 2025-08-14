#!/bin/bash

# Travel Assistant Startup Script
echo "🌍 Travel Assistant - Startup Script"
echo "======================================"

# Check if we're in the right directory
if [ ! -d "backend" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Navigate to backend directory
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found. Please run:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please create a .env file with your API keys:"
    echo "   OPENAI_API_KEY=your_openai_api_key_here"
    echo "   GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here"
    exit 1
fi

# Check if API keys are set (not placeholders)
if grep -q "your_openai_api_key_here" .env || grep -q "your_google_maps_api_key_here" .env; then
    echo "⚠️  Warning: API keys appear to be placeholder values"
    echo "Please update your .env file with real API keys:"
    echo ""
    echo "1. Get OpenAI API key from: https://platform.openai.com/api-keys"
    echo "2. Get Google Maps API key from: https://console.cloud.google.com/apis/credentials"
    echo "   (Enable: Places API, Directions API, Geocoding API)"
    echo ""
    echo "Update the .env file and run this script again."
    exit 1
fi

# Test MCP server (optional)
echo "🧪 Testing MCP server startup..."
python test_mcp_debug.py

if [ $? -eq 0 ]; then
    echo "✅ MCP server test passed!"
else
    echo "❌ MCP server test failed. Check your API keys and internet connection."
    echo "The app may still work with limited functionality."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start the application
echo ""
echo "🚀 Starting Travel Assistant..."
echo "📍 Frontend will be available at: http://localhost:8000"
echo "🔧 API health check at: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the FastAPI server
python main.py 