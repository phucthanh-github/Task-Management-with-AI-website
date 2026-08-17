# ToDoList with AI

A modern, full-stack task management application powered by intelligent AI assistant. Manage your tasks efficiently through natural language conversation using advanced AI-driven tools and automated scheduling.

## Overview

**ToDoList with AI** is a sophisticated task management system that combines a responsive React frontend with a powerful FastAPI backend. The application features an intelligent AI chatbot agent that leverages **LangGraph** and **LlamaIndex** to understand your tasks through natural conversation, execute actions intelligently, and manage your workload seamlessly.

### Key Highlights
- 🤖 **AI-Powered Chatbot**: Manage tasks through natural language conversations
- ⚡ **Token-Optimized**: Calls LLM only once per interaction, reducing costs and latency
- 🔄 **Intelligent Scheduling**: Automatically schedules tool execution chains without redundant LLM calls
- 🌐 **Full-Stack Application**: Modern React frontend with FastAPI backend
- 🗄️ **MongoDB Integration**: Persistent data storage with cloud and local options
- 🔐 **Secure Authentication**: User authentication and authorization with JWT tokens

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | React 19 + Vite |
| **Backend** | FastAPI |
| **Database** | MongoDB |
| **AI/ML** | LangGraph, LlamaIndex, Hugging Face |
| **Authentication** | JWT (Python-jose) |
| **API** | RESTful API with CORS support |
| **Scheduling** | APScheduler |
| **Async Processing** | Motor (async MongoDB driver) |

---

## Features

- ✅ **User Authentication**: Secure registration and login system
- ✅ **Task Management**: Create, read, update, and delete tasks
- ✅ **AI Chat Interface**: Interact with tasks using natural language
- ✅ **Intelligent Task Scheduling**: Automatically schedule and manage task execution
- ✅ **Multi-Tool Integration**: Leverage multiple AI tools for enhanced capabilities
- ✅ **Real-time Updates**: Live task status updates
- ✅ **Responsive Design**: Works seamlessly on desktop and mobile devices

---


## Installation & Setup

### Prerequisites

- **Node.js** 16+ and npm/yarn
- **Python** 3.9+
- **MongoDB** (local or MongoDB Atlas)
- **Git**

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create a Python virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - **Windows:**
     ```bash
     venv\Scripts\activate
     ```
   - **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables:**
   Create a `.env` file in the `backend` directory:
   ```env
   # MongoDB Configuration
   MONGODB_URL=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   # or for local MongoDB:
   # MONGODB_URL=mongodb://localhost:27017

   # JWT Configuration
   SECRET_KEY=your_secret_key_here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30

   # Frontend URL
   FRONTEND_URL=http://localhost:5173

   # API Configuration
   API_HOST=0.0.0.0
   API_PORT=8000

   # LLM Configuration (if using external LLM)
   HUGGINGFACE_API_KEY=your_hf_api_key
   ```

6. **Run the backend server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Backend will be available at: `http://localhost:8000`

### MongoDB Setup

#### Option 1: MongoDB Atlas (Cloud - Recommended)

1. Visit [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) and create a free account
2. Create a new cluster (M0 Free tier recommended)
3. Set up database user credentials
4. Configure network access (allow from anywhere for development)
5. Copy the connection string and add it to your `.env` file

#### Option 2: Local MongoDB Installation

1. Download from [MongoDB Community Download](https://www.mongodb.com/try/download/community)
2. Install MongoDB following the official guide
3. For Windows, MongoDB runs as a service on port `27017`
4. Default connection string: `mongodb://localhost:27017`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure API endpoint (if needed):**
   Update the API URL in your React components to match your backend URL

4. **Run the development server:**
   ```bash
   npm run dev
   ```
   Frontend will be available at: `http://localhost:5173`

5. **Build for production:**
   ```bash
   npm run build
   ```

---

## Running the Application

1. **Start MongoDB** (if using local installation)
   ```bash
   # Windows: MongoDB runs as a service automatically
   # macOS/Linux:
   mongod
   ```

2. **Start Backend** (in `backend` directory):
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Start Frontend** (in `frontend` directory):
   ```bash
   npm run dev
   ```

4. **Access the application:**
   - Frontend: `http://localhost:5173`
   - Backend API: `http://localhost:8000`
   - API Documentation: `http://localhost:8000/docs` (Swagger UI)

---

## Security Configuration

### Environment Variables

Ensure you create `.env` files for both backend and frontend based on the `.env.example` templates provided. **Never commit `.env` files to source control.**

#### Backend (`backend/.env`)

- `APP_ENV`: Application environment (`development` | `test` | `production`). In `production`, the server fails fast if critical security settings are invalid.
- `SECRET_KEY`: High-entropy secret key for JWT signing. Must be at least 32 characters long in production.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for JWT access tokens (default: `60` minutes).
- `FRONTEND_URL`: Primary URL of the frontend application used for CORS origin allowlist.
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins. Wildcards (`*` or regex wildcard origins) are disabled.
- `GOOGLE_CLIENT_ID`: Google OAuth 2.0 Client ID for server-side ID token verification (aud, iss, exp, email_verified).
- `DEV_DEMO_ENABLED`: Set to `false` in production. Controls local development fallback features.
- `RATE_LIMIT_AUTH`: Rate limit for registration and login endpoints (e.g. `5/minute`).
- `RATE_LIMIT_CHAT`: Rate limit for AI chat message endpoints (e.g. `20/minute`).

#### Frontend (`frontend/.env`)

- `VITE_API_URL`: Backend API URL (e.g., `http://localhost:8000`).
- `VITE_GOOGLE_CLIENT_ID`: Google OAuth 2.0 Client ID for Google Sign-In button initialization.
- `VITE_DEV_DEMO_ENABLED`: Set to `false` in production. When `true`, enables the *"Development demo login"* button strictly for local development testing.

### Local Development Demo Login

The *"Development demo login"* button is strictly hidden in production environments. To enable it locally for rapid offline testing:

1. In `frontend/.env`, set `VITE_DEV_DEMO_ENABLED=true`.
2. In `backend/.env`, set `DEV_DEMO_ENABLED=true`.
3. Optionally set `VITE_DEV_DEMO_EMAIL` and `VITE_DEV_DEMO_PASSWORD` in your local `.env`.