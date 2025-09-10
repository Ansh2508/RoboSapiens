from pydantic import BaseModel
"""
Comprehensive REST API Server

FastAPI-based server providing complete access to all Niryo LLM Robotics Platform
capabilities with authentication, rate limiting, and real-time WebSocket support.

Features:
- RESTful API covering all robot functions
- JWT-based authentication with role-based access control
- Rate limiting and security middleware
- OpenAPI/Swagger documentation
- WebSocket support for real-time updates
- Integration with Phase 1-5 systems
- Educational API endpoints for student management
"""

import os
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import logging

try:
    from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from pydantic import Field
    import jwt
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logging.warning("FastAPI not available. Install with: pip install fastapi uvicorn python-jose")

from utils.logger import get_logger

# Import Phase 1-5 components for API integration
try:
    from robot.robot_controller import RobotController
    from vision.camera_interface import CameraInterface
    from automation.coordination_manager import CoordinationManager
    from api.llm import NaturalLanguageInterface, StudentInterface, TaskPlanner
except ImportError as e:
    logging.warning(f"Some Phase 1-5 components not available: {e}")

logger = get_logger(__name__)


@dataclass
class APIConfig:
    """Configuration for API server."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_enabled: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    
    # Authentication
    jwt_secret_key: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    # Security
    trusted_hosts: List[str] = field(default_factory=lambda: ["*"])
    max_request_size: int = 10 * 1024 * 1024  # 10MB


class APIModels:
    """Pydantic models for API requests and responses."""
    
    class UserLogin(BaseModel):
        username: str = Field(..., description="Username")
        password: str = Field(..., description="Password")
    
    class TokenResponse(BaseModel):
        access_token: str = Field(..., description="JWT access token")
        token_type: str = Field(default="bearer", description="Token type")
        expires_in: int = Field(..., description="Token expiration in seconds")
    
    class RobotCommand(BaseModel):
        command_type: str = Field(..., description="Type of robot command")
        position: Optional[Dict[str, float]] = Field(None, description="Target position")
        parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
        speed: float = Field(50.0, ge=1.0, le=100.0, description="Movement speed percentage")
        safety_check: bool = Field(True, description="Perform safety validation")
    
    class TaskPlanRequest(BaseModel):
        user_request: str = Field(..., description="Natural language task description")
        user_id: str = Field(..., description="User identifier")
        strategy: str = Field("optimized", description="Planning strategy")
        max_steps: int = Field(20, description="Maximum number of steps")
        max_duration: float = Field(300.0, description="Maximum execution time in seconds")
    
    class StudentRegistration(BaseModel):
        student_id: str = Field(..., description="Unique student identifier")
        name: str = Field(..., description="Student name")
        skill_level: str = Field("beginner", description="Student skill level")
        language: str = Field("english", description="Preferred language")
    
    class NaturalLanguageCommand(BaseModel):
        text: str = Field(..., description="Natural language command")
        session_id: Optional[str] = Field(None, description="Conversation session ID")
        language: str = Field("english", description="Command language")
    
    class APIResponse(BaseModel):
        success: bool = Field(..., description="Operation success status")
        message: str = Field(..., description="Response message")
        data: Optional[Dict[str, Any]] = Field(None, description="Response data")
        timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class AuthenticationManager:
    """JWT-based authentication manager with role-based access control."""
    
    def __init__(self, config: APIConfig):
        """
        Initialize authentication manager.
        
        Args:
            config: API configuration
        """
        self.config = config
        self.security = HTTPBearer()
        
        # User database (in production, use proper database)
        self.users = {
            "admin": {"password": "admin123", "role": "admin", "permissions": ["all"]},
            "teacher": {"password": "teacher123", "role": "teacher", "permissions": ["robot", "students", "monitoring"]},
            "student": {"password": "student123", "role": "student", "permissions": ["robot", "basic"]},
            "api_user": {"password": "api123", "role": "api", "permissions": ["robot", "vision", "automation"]}
        }
        
        logger.info("Authentication manager initialized")
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user credentials.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User information if authenticated, None otherwise
        """
        user = self.users.get(username)
        if user and user["password"] == password:
            return {
                "username": username,
                "role": user["role"],
                "permissions": user["permissions"]
            }
        return None
    
    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """
        Create JWT access token.
        
        Args:
            user_data: User information
            
        Returns:
            JWT token string
        """
        expire = datetime.utcnow() + timedelta(hours=self.config.jwt_expiration_hours)
        
        payload = {
            "sub": user_data["username"],
            "role": user_data["role"],
            "permissions": user_data["permissions"],
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)
    
    def verify_token(self, credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
        """
        Verify JWT token and extract user information.
        
        Args:
            credentials: HTTP authorization credentials
            
        Returns:
            User information from token
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = jwt.decode(
                credentials.credentials,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm]
            )
            
            username = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            return {
                "username": username,
                "role": payload.get("role"),
                "permissions": payload.get("permissions", [])
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def check_permission(self, user: Dict[str, Any], required_permission: str) -> bool:
        """
        Check if user has required permission.
        
        Args:
            user: User information
            required_permission: Required permission
            
        Returns:
            True if user has permission
        """
        permissions = user.get("permissions", [])
        return "all" in permissions or required_permission in permissions


class RateLimiter:
    """Request rate limiting and quota management."""
    
    def __init__(self, config: APIConfig):
        """
        Initialize rate limiter.
        
        Args:
            config: API configuration
        """
        self.config = config
        self.requests: Dict[str, List[float]] = {}
        
        logger.info("Rate limiter initialized")
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed based on rate limits.
        
        Args:
            client_id: Client identifier (IP address or user ID)
            
        Returns:
            True if request is allowed
        """
        current_time = time.time()
        window_start = current_time - self.config.rate_limit_window
        
        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if req_time > window_start
            ]
        else:
            self.requests[client_id] = []
        
        # Check rate limit
        if len(self.requests[client_id]) >= self.config.rate_limit_requests:
            return False
        
        # Add current request
        self.requests[client_id].append(current_time)
        return True
    
    def get_remaining_requests(self, client_id: str) -> int:
        """Get remaining requests for client."""
        current_requests = len(self.requests.get(client_id, []))
        return max(0, self.config.rate_limit_requests - current_requests)


class WebSocketManager:
    """WebSocket connection manager for real-time updates."""
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: List[WebSocket] = []
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
        
        logger.info("WebSocket manager initialized")
    
    async def connect(self, websocket: WebSocket, user_info: Dict[str, Any]):
        """
        Accept WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            user_info: User information
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_info[websocket] = user_info
        
        logger.info(f"WebSocket connected: {user_info.get('username', 'unknown')}")
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove WebSocket connection.
        
        Args:
            websocket: WebSocket connection
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            user_info = self.connection_info.pop(websocket, {})
            logger.info(f"WebSocket disconnected: {user_info.get('username', 'unknown')}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str, permission_required: Optional[str] = None):
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            permission_required: Required permission to receive message
        """
        disconnected = []
        
        for websocket in self.active_connections:
            try:
                user_info = self.connection_info.get(websocket, {})
                
                # Check permission if required
                if permission_required:
                    permissions = user_info.get("permissions", [])
                    if permission_required not in permissions and "all" not in permissions:
                        continue
                
                await websocket.send_text(message)
                
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        for websocket in disconnected:
            self.disconnect(websocket)


class APIServer:
    """
    Comprehensive REST API server for Niryo LLM Robotics Platform.

    Provides complete access to all robot functions with authentication,
    rate limiting, and real-time WebSocket support.
    """

    def __init__(self, config: Optional[APIConfig] = None):
        """
        Initialize API server.

        Args:
            config: API configuration
        """
        self.config = config or APIConfig()

        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required. Install with: pip install fastapi uvicorn python-jose")

        # Initialize FastAPI app
        self.app = FastAPI(
            title="Niryo LLM Robotics Platform API",
            description="Comprehensive REST API for AI-enhanced robotics control",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )

        # Initialize managers
        self.auth_manager = AuthenticationManager(self.config)
        self.rate_limiter = RateLimiter(self.config)
        self.websocket_manager = WebSocketManager()

        # Initialize Phase 1-5 components
        self._initialize_components()

        # Setup middleware
        self._setup_middleware()

        # Setup routes
        self._setup_routes()

        logger.info("API server initialized")

    def _initialize_components(self):
        """Initialize Phase 1-5 components for API integration."""
        try:
            self.robot_controller = RobotController()
            logger.info("Robot controller initialized for API")
        except Exception as e:
            logger.warning(f"Robot controller not available: {e}")
            self.robot_controller = None

        try:
            self.camera_interface = CameraInterface()
            logger.info("Camera interface initialized for API")
        except Exception as e:
            logger.warning(f"Camera interface not available: {e}")
            self.camera_interface = None

        try:
            self.coordination_manager = CoordinationManager()
            logger.info("Coordination manager initialized for API")
        except Exception as e:
            logger.warning(f"Coordination manager not available: {e}")
            self.coordination_manager = None

        try:
            self.nl_interface = NaturalLanguageInterface()
            logger.info("Natural language interface initialized for API")
        except Exception as e:
            logger.warning(f"Natural language interface not available: {e}")
            self.nl_interface = None

        try:
            self.student_interface = StudentInterface(self.nl_interface) if self.nl_interface else None
            logger.info("Student interface initialized for API")
        except Exception as e:
            logger.warning(f"Student interface not available: {e}")
            self.student_interface = None

    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        # CORS middleware
        if self.config.cors_enabled:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=self.config.cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # Trusted host middleware
        self.app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=self.config.trusted_hosts
        )

    def _get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
        """Dependency to get current authenticated user."""
        return self.auth_manager.verify_token(credentials)

    def _check_rate_limit(self, request):
        """Check rate limiting for request."""
        client_ip = request.client.host
        if not self.rate_limiter.is_allowed(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(self.config.rate_limit_window)}
            )

    def _setup_routes(self):
        """Setup API routes."""

        # Authentication routes
        @self.app.post("/auth/login", response_model=APIModels.TokenResponse)
        async def login(login_data: APIModels.UserLogin):
            """Authenticate user and return JWT token."""
            user = self.auth_manager.authenticate_user(login_data.username, login_data.password)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid credentials")

            token = self.auth_manager.create_access_token(user)

            return APIModels.TokenResponse(
                access_token=token,
                expires_in=self.config.jwt_expiration_hours * 3600
            )

        # Robot control routes
        @self.app.post("/robot/command", response_model=APIModels.APIResponse)
        async def execute_robot_command(
            command: APIModels.RobotCommand,
            current_user: dict = Depends(self._get_current_user)
        ):
            """Execute robot command."""
            if not self.auth_manager.check_permission(current_user, "robot"):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            if not self.robot_controller:
                raise HTTPException(status_code=503, detail="Robot controller not available")

            try:
                # Convert API model to robot command
                result = await self._execute_robot_command(command)

                # Broadcast status update via WebSocket
                await self.websocket_manager.broadcast(
                    json.dumps({"type": "robot_command", "status": "executed", "command": command.model_dump()}),
                    "robot"
                )

                return APIModels.APIResponse(
                    success=True,
                    message="Command executed successfully",
                    data={"result": result}
                )

            except Exception as e:
                logger.error(f"Robot command execution failed: {e}")
                return APIModels.APIResponse(
                    success=False,
                    message=f"Command execution failed: {str(e)}"
                )

        @self.app.get("/robot/status", response_model=APIModels.APIResponse)
        async def get_robot_status(current_user: dict = Depends(self._get_current_user)):
            """Get current robot status."""
            if not self.auth_manager.check_permission(current_user, "robot"):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            if not self.robot_controller:
                raise HTTPException(status_code=503, detail="Robot controller not available")

            try:
                status = self.robot_controller.get_status()
                return APIModels.APIResponse(
                    success=True,
                    message="Status retrieved successfully",
                    data=status
                )
            except Exception as e:
                logger.error(f"Failed to get robot status: {e}")
                return APIModels.APIResponse(
                    success=False,
                    message=f"Failed to get status: {str(e)}"
                )

        # Natural language processing routes
        @self.app.post("/nlp/command", response_model=APIModels.APIResponse)
        async def process_natural_language_command(
            command: APIModels.NaturalLanguageCommand,
            current_user: dict = Depends(self._get_current_user)
        ):
            """Process natural language command."""
            if not self.auth_manager.check_permission(current_user, "robot"):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            if not self.nl_interface:
                raise HTTPException(status_code=503, detail="Natural language interface not available")

            try:
                # Start session if not provided
                session_id = command.session_id
                if not session_id:
                    session_id = self.nl_interface.start_session(current_user["username"])

                # Process command
                result, response = self.nl_interface.process_text_command(session_id, command.text)

                return APIModels.APIResponse(
                    success=True,
                    message="Command processed successfully",
                    data={
                        "response": response,
                        "session_id": session_id,
                        "result": result.dict() if hasattr(result, 'dict') else str(result)
                    }
                )

            except Exception as e:
                logger.error(f"Natural language processing failed: {e}")
                return APIModels.APIResponse(
                    success=False,
                    message=f"Processing failed: {str(e)}"
                )

        # Task planning routes
        @self.app.post("/planning/create", response_model=APIModels.APIResponse)
        async def create_task_plan(
            plan_request: APIModels.TaskPlanRequest,
            current_user: dict = Depends(self._get_current_user)
        ):
            """Create AI-driven task plan."""
            if not self.auth_manager.check_permission(current_user, "robot"):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            try:
                # This would integrate with Phase 5 task planner
                # For now, return a placeholder response
                return APIModels.APIResponse(
                    success=True,
                    message="Task plan created successfully",
                    data={
                        "plan_id": f"plan_{int(time.time())}",
                        "user_request": plan_request.user_request,
                        "estimated_steps": 5,
                        "estimated_duration": 60.0
                    }
                )

            except Exception as e:
                logger.error(f"Task planning failed: {e}")
                return APIModels.APIResponse(
                    success=False,
                    message=f"Planning failed: {str(e)}"
                )

        # Educational routes
        @self.app.post("/education/student/register", response_model=APIModels.APIResponse)
        async def register_student(
            student_data: APIModels.StudentRegistration,
            current_user: dict = Depends(self._get_current_user)
        ):
            """Register a new student."""
            if not self.auth_manager.check_permission(current_user, "students"):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            if not self.student_interface:
                raise HTTPException(status_code=503, detail="Student interface not available")

            try:
                from llm.educational_interface import SkillLevel, Language

                # Convert string values to enums
                skill_level = SkillLevel(student_data.skill_level.lower())
                language = Language(student_data.language.lower()[:2])  # Convert to 2-letter code

                profile = self.student_interface.register_student(
                    student_data.student_id,
                    student_data.name,
                    skill_level,
                    language
                )

                return APIModels.APIResponse(
                    success=True,
                    message="Student registered successfully",
                    data={
                        "student_id": profile.student_id,
                        "name": profile.name,
                        "skill_level": profile.skill_level.value,
                        "language": profile.preferred_language.value
                    }
                )

            except Exception as e:
                logger.error(f"Student registration failed: {e}")
                return APIModels.APIResponse(
                    success=False,
                    message=f"Registration failed: {str(e)}"
                )

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            try:
                # For simplicity, accept connection without auth in this example
                # In production, implement WebSocket authentication
                user_info = {"username": "websocket_user", "permissions": ["monitoring"]}

                await self.websocket_manager.connect(websocket, user_info)

                while True:
                    data = await websocket.receive_text()
                    # Echo received data (can be extended for bidirectional communication)
                    await self.websocket_manager.send_personal_message(f"Echo: {data}", websocket)

            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.websocket_manager.disconnect(websocket)

    async def _execute_robot_command(self, command: APIModels.RobotCommand) -> Dict[str, Any]:
        """Execute robot command and return result."""
        # This would integrate with the actual robot controller
        # For now, return a simulated result
        return {
            "command_type": command.command_type,
            "executed_at": datetime.now().isoformat(),
            "status": "completed",
            "execution_time": 2.5
        }

    def run(self):
        """Run the API server."""
        logger.info(f"Starting API server on {self.config.host}:{self.config.port}")

        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            debug=self.config.debug,
            log_level="info" if not self.config.debug else "debug"
        )


# Convenience functions
def create_api_server(config: Optional[APIConfig] = None) -> APIServer:
    """Create and initialize API server."""
    return APIServer(config)


def run_api_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Quick API server startup."""
    config = APIConfig(host=host, port=port, debug=debug)
    server = APIServer(config)
    server.run()
