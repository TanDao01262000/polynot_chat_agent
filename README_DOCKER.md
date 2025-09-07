# Docker Setup for PolyNot Chat Agent

This guide explains how to run the PolyNot Chat Agent using Docker with automatic code synchronization for development.

## Prerequisites

- Docker and Docker Compose installed on your system
- A `.env` file with your environment variables (copy from `.env.example`)

## Quick Start

1. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

3. **Access the application:**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Development Features

### Automatic Code Synchronization

The Docker setup includes volume mounting for automatic code synchronization:

- **Source Code**: `./src` → `/app/src` (live reloading)
- **Documentation**: `./docs_and_tests` → `/app/docs_and_tests`
- **Requirements**: `./requirements.txt` → `/app/requirements.txt`
- **Environment**: `./.env` → `/app/.env`
- **Database**: SQLite checkpoint files are mounted for persistence

### Hot Reloading

The application runs with `--reload` flag, so any changes to your Python code will automatically restart the server.

## Docker Commands

### Build and Run
```bash
# Build and start services
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Development Commands
```bash
# Rebuild only the app service
docker-compose build polynot-chat-agent

# Restart the app service
docker-compose restart polynot-chat-agent

# Execute commands in the running container
docker-compose exec polynot-chat-agent bash

# Install new Python packages
docker-compose exec polynot-chat-agent pip install package_name
```

### Database Management
```bash
# Access the database
docker-compose exec polynot-chat-agent sqlite3 /app/checkpoint.sqlite

# Backup database
docker cp polynot-chat-agent:/app/checkpoint.sqlite ./backup_$(date +%Y%m%d_%H%M%S).sqlite
```

## Environment Variables

Copy `.env.example` to `.env` and configure the following required variables:

### Required
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Your Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key
- `OPENAI_API_KEY`: Your OpenAI API key

### Optional
- `LANGSMITH_API_KEY`: For LangSmith tracing
- `LANGSMITH_PROJECT`: LangSmith project name
- `JWT_SECRET_KEY`: For authentication
- `SESSION_SECRET`: For session management

## Troubleshooting

### Common Issues

1. **Port already in use:**
   ```bash
   # Change port in docker-compose.yml
   ports:
     - "8001:8000"  # Use port 8001 instead
   ```

2. **Permission issues with volumes:**
   ```bash
   # Fix file permissions
   sudo chown -R $USER:$USER .
   ```

3. **Container won't start:**
   ```bash
   # Check logs
   docker-compose logs polynot-chat-agent
   
   # Check if .env file exists and has required variables
   cat .env
   ```

4. **Database connection issues:**
   ```bash
   # Check if checkpoint files exist
   ls -la checkpoint.sqlite*
   
   # Remove and recreate if corrupted
   rm checkpoint.sqlite*
   docker-compose restart polynot-chat-agent
   ```

### Health Checks

The container includes health checks. You can monitor the health status:

```bash
# Check container health
docker-compose ps

# View health check logs
docker inspect polynot-chat-agent | grep -A 10 Health
```

## Production Deployment

For production deployment, consider:

1. **Remove `--reload` flag** from the Dockerfile CMD
2. **Use environment-specific .env files**
3. **Set up proper logging and monitoring**
4. **Use a reverse proxy (nginx)**
5. **Set up SSL/TLS certificates**
6. **Use a production database (PostgreSQL)**

## File Structure

```
polynot_chat_agent/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Multi-container setup
├── .dockerignore          # Files to exclude from build
├── .env.example           # Environment variables template
├── .env                   # Your environment variables (not in git)
├── requirements.txt       # Python dependencies
├── src/                   # Source code (mounted as volume)
├── docs_and_tests/        # Documentation (mounted as volume)
└── checkpoint.sqlite*     # Database files (mounted as volumes)
```

## Additional Services

The docker-compose.yml includes commented sections for additional services like PostgreSQL. Uncomment and configure as needed for your use case.

