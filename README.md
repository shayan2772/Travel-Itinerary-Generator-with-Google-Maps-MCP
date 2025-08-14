# 🌍 Travel Itinerary Generator with Google Maps MCP

An AI-powered travel planning application that combines **OpenAI's language models** with **Google Maps** through the **Model Context Protocol (MCP)** to create personalized travel itineraries and provide intelligent travel assistance.

## ✨ Features

- **🗺️ Intelligent Itinerary Generation**: Create detailed, personalized travel plans for any destination
- **🤖 AI Travel Assistant**: Interactive chat interface powered by OpenAI's GPT models
- **📍 Real-time Place Information**: Live data from Google Maps API for restaurants, hotels, attractions
- **🧭 Route Planning**: Get directions, travel times, and distance calculations
- **📱 Modern UI**: Beautiful, responsive interface built with Tailwind CSS
- **⚡ Fast & Reliable**: Built with FastAPI and optimized for performance
- **🔒 Secure**: Environment-based configuration with proper API key management
- **🚀 Scalable**: Async architecture with proper error handling and logging

## 🏗️ Architecture

### Backend Stack
- **Framework**: FastAPI (async Python web framework)
- **AI/LLM**: OpenAI GPT-3.5-turbo with LangChain agents
- **Maps Integration**: Google Maps API via MCP (Model Context Protocol)
- **Async Support**: Full async/await support for high performance
- **Error Handling**: Comprehensive exception handling with detailed logging

### Frontend Stack
- **HTML5**: Semantic markup with accessibility features
- **CSS3**: Modern styling with Tailwind CSS framework
- **JavaScript**: Vanilla JS with modern ES6+ features
- **Responsive Design**: Mobile-first approach with progressive enhancement

### Integration Layer
- **MCP Server**: @cablate/mcp-google-map for Google Maps functionality
- **API Design**: RESTful endpoints with JSON request/response
- **CORS Support**: Cross-origin resource sharing enabled
- **Health Checks**: Built-in monitoring and status endpoints

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** (tested with Python 3.12)
- **Node.js 16+** for MCP server
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
- **Google Maps API Key** ([Get one here](https://console.cloud.google.com/apis/credentials))

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd google-maps-mcp-with-langchain
```

2. **Set up Python environment**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure API keys**
```bash
# Create .env file in the backend directory
cd backend
nano .env  # or use your preferred editor
```

Add your API keys to the `.env` file:
```env
# OpenAI API Key (Required)
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_actual_openai_api_key_here

# Google Maps API Key (Required)
# Get from: https://console.cloud.google.com/apis/credentials
# Enable: Places API, Directions API, Geocoding API
GOOGLE_MAPS_API_KEY=your_actual_google_maps_api_key_here

# MCP Server Configuration
MCP_SERVER_PATH=npx -y @cablate/mcp-google-map

# Server Configuration (Optional)
HOST=localhost
PORT=8000
DEBUG=true
```

4. **Start the Application**

**Option 1: Use the startup script (Recommended)**
```bash
# From project root
chmod +x start_app.sh
./start_app.sh
```

**Option 2: Manual startup**
```bash
cd backend
source venv/bin/activate
python main.py
```

The application will be available at: **http://localhost:8000**

## 🎨 Frontend Features

### Design Features
- **Gradient backgrounds** and smooth animations
- **Responsive chat interface** that works on all devices
- **Modern message bubbles** with proper spacing
- **Interactive suggestion buttons** for quick travel queries
- **Real-time status indicators** showing connection status
- **Smooth scrolling** and transition effects
- **Accessibility-focused** design with proper contrast

### Mobile-First Design
- Optimized for mobile, tablet, and desktop
- Touch-friendly interface elements
- Responsive typography and spacing
- Swipe-friendly chat interactions

### Key Improvements
- **Better Visual Hierarchy**: Clear distinction between user and AI messages
- **Enhanced Readability**: Improved typography and spacing
- **Modern Aesthetics**: Gradient backgrounds and subtle shadows
- **Interactive Elements**: Hover effects and smooth transitions
- **Status Feedback**: Clear visual indicators for connection status

## 🔧 Configuration

### Google Maps API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the following APIs:
   - Places API
   - Directions API
   - Geocoding API
   - Distance Matrix API (optional)
   - Elevation API (optional)
4. Create an API key in "APIs & Services" > "Credentials"
5. Add the API key to your `.env` file

### OpenAI API Setup

1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create an account or sign in
3. Generate a new API key
4. Add the API key to your `.env` file

### Environment Variables

The application uses the following environment variables:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key for AI functionality | None |
| `GOOGLE_MAPS_API_KEY` | ✅ | Google Maps API key for maps data | None |
| `MCP_SERVER_PATH` | ❌ | Path to MCP server executable | `npx -y @cablate/mcp-google-map` |
| `HOST` | ❌ | Server host address | `localhost` |
| `PORT` | ❌ | Server port number | `8000` |
| `DEBUG` | ❌ | Enable debug logging | `false` |

## 🚀 Usage

### Starting the Server

**Using the startup script (Recommended):**
```bash
./start_app.sh
```

**Manual startup:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Development mode with auto-reload:**
```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Using the Web Interface

1. **Open your browser** to `http://localhost:8000`
2. **Generate Itinerary**:
   - Enter your destination (e.g., "Paris, France")
   - Select trip duration (1-30 days)
   - Choose your interests (museums, food, nature, etc.)
   - Click "Generate Itinerary"
3. **Chat with Assistant**:
   - Use the chat interface to ask travel questions
   - Get recommendations for specific places
   - Ask for directions or place details

### API Endpoints

The backend provides RESTful API endpoints:

| Endpoint | Method | Description | Request Body |
|----------|--------|-------------|--------------|
| `/` | GET | Serve the web interface | None |
| `/health` | GET | Health check and configuration status | None |
| `/generate-itinerary` | POST | Generate travel itinerary | JSON with destination, duration, interests |
| `/chat` | POST | Chat with travel assistant | JSON with message |
| `/static/*` | GET | Serve static files | None |

#### Example API Usage

**Generate Itinerary:**
```bash
curl -X POST "http://localhost:8000/generate-itinerary" \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Tokyo, Japan",
    "duration": 5,
    "interests": ["museums", "restaurants", "culture"]
  }'
```

**Chat with Assistant:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the best sushi restaurants in Tokyo?"
  }'
```

**Health Check:**
```bash
curl http://localhost:8000/health
```

## 📁 Project Structure

```
google-maps-mcp-with-langchain/
├── backend/                    # Backend application
│   ├── venv/                  # Python virtual environment
│   ├── config.py              # Configuration management
│   ├── exceptions.py          # Custom exception classes
│   ├── itinerary_generator.py # LangChain AI agent
│   ├── main.py                # FastAPI server entry point
│   ├── mcp_client.py          # Google Maps MCP client
│   ├── requirements.txt       # Python dependencies
│   └── startup_debug.py      # Debug utilities
├── frontend/                   # Frontend application
│   ├── index.html             # Main web interface
│   ├── style.css              # Tailwind CSS styling
│   └── script.js              # Interactive functionality
├── .gitignore                 # Git ignore rules
├── start_app.sh               # Startup script
├── README.md                  # This file
└── ENHANCED_FEATURES.md      # Feature documentation
```

## 🐛 Troubleshooting

### Common Issues

**1. "Google Maps API Key is required" Error**
- Ensure `GOOGLE_MAPS_API_KEY` is set in your `.env` file
- Verify the API key is valid and has the required APIs enabled
- Check that the API key has proper restrictions and quotas

**2. "OpenAI API key not configured" Warning**
- Set `OPENAI_API_KEY` in your `.env` file
- Check that your OpenAI account has available credits
- Verify the API key format and permissions

**3. "MCP server not initialized" Error**
- Ensure Node.js is installed (`node --version`)
- Verify NPX is available (`npx --version`)
- Check internet connection for downloading MCP package
- Verify the MCP server path in your `.env` file

**4. Port Already in Use**
- Change the port in `.env`: `PORT=8001`
- Or kill the process using the port: `lsof -ti:8000 | xargs kill`
- Check for other services running on the same port

**5. Import Errors**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r backend/requirements.txt`
- Check Python version compatibility

**6. CORS Issues**
- Verify the frontend is being served from the correct origin
- Check that CORS middleware is properly configured
- Ensure proper headers are set in responses

### Development Mode

For development, use the reload flag:
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Logging

Enable debug logging by setting `DEBUG=true` in your `.env` file. Logs will show:
- API requests and responses
- LangChain agent reasoning
- MCP server communication
- Error details and stack traces
- Performance metrics

## 🔒 Security Considerations

- **API Key Management**: Never commit API keys to version control
- **Environment Variables**: Use `.env` files for local development
- **CORS Configuration**: Properly configured for production use
- **Input Validation**: All user inputs are validated and sanitized
- **Rate Limiting**: Consider implementing rate limiting for production

## 🚀 Deployment

### Production Considerations

1. **Environment Variables**: Set production API keys securely
2. **HTTPS**: Use HTTPS in production with proper SSL certificates
3. **Reverse Proxy**: Consider using Nginx or Apache as a reverse proxy
4. **Process Management**: Use systemd, PM2, or similar for process management
5. **Monitoring**: Implement proper logging and monitoring
6. **Backup**: Regular backups of configuration and data

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY frontend/ ./frontend/

EXPOSE 8000
CMD ["python", "main.py"]
```

## 📚 Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **LangChain**: Framework for developing applications with LLMs
- **OpenAI**: GPT-3.5-turbo for natural language processing
- **Pydantic**: Data validation using Python type annotations
- **Uvicorn**: Lightning-fast ASGI server

### Frontend
- **HTML5**: Semantic markup and modern web standards
- **Tailwind CSS**: Utility-first CSS framework
- **Vanilla JavaScript**: Modern ES6+ JavaScript without frameworks
- **Responsive Design**: Mobile-first responsive design approach

### Integration
- **MCP**: Model Context Protocol for external tool integration
- **Google Maps API**: Comprehensive maps and location services
- **RESTful API**: Standard HTTP API design patterns

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** following the existing code style
4. **Test your changes** thoroughly
5. **Commit your changes** (`git commit -m 'Add amazing feature'`)
6. **Push to the branch** (`git push origin feature/amazing-feature`)
7. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 for Python code
- Use meaningful commit messages
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass before submitting

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Google Maps API Documentation](https://developers.google.com/maps/documentation)
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [MCP Google Maps Server](https://github.com/cablate/mcp-google-map)

## ✨ Acknowledgments

- [MCP Google Maps Server](https://github.com/cablate/mcp-google-map) by @cablate
- [LangChain](https://github.com/hwchase17/langchain) for AI agent framework
- [FastAPI](https://github.com/tiangolo/fastapi) for the excellent web framework
- [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) for the beautiful UI framework

## 📊 Project Status

- **Current Version**: 1.0.0
- **Python Support**: 3.8+
- **Node.js Support**: 16+
- **License**: MIT
- **Maintenance**: Active development

---

**Happy Traveling! 🌍✈️** 