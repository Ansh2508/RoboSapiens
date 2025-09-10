"""
LLM Interface Layer

Unified API abstraction supporting both OpenAI GPT-4 and Ollama local models
with automatic failover, cost optimization, and comprehensive error handling.

Features:
- Multi-provider support (OpenAI, Ollama)
- Automatic failover between cloud and local models
- Token usage optimization and cost management
- Comprehensive error handling and retry logic
- Secure API key management
- Performance monitoring and analytics
"""

import os
import time
import json
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not available. Install with: pip install openai")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("Requests library not available. Install with: pip install requests")

from utils.logger import get_logger

logger = get_logger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


@dataclass
class LLMConfig:
    """Configuration for LLM interface."""
    primary_provider: LLMProvider = LLMProvider.OPENAI
    fallback_provider: LLMProvider = LLMProvider.OLLAMA
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_base_url: Optional[str] = None
    
    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    
    # General Configuration
    max_tokens: int = 1000
    temperature: float = 0.1
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Cost Management
    cost_limit_monthly: float = 50.0
    cost_limit_daily: float = 5.0
    token_usage_tracking: bool = True
    
    def __post_init__(self):
        """Initialize configuration after creation."""
        # Load OpenAI API key from environment if not provided
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Validate configuration
        if self.primary_provider == LLMProvider.OPENAI and not self.openai_api_key:
            logger.warning("OpenAI API key not provided. Switching to Ollama as primary provider.")
            self.primary_provider = LLMProvider.OLLAMA


@dataclass
class LLMResponse:
    """Response from LLM interface."""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int
    cost_estimate: float
    response_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMInterface:
    """
    Unified interface for Large Language Model interactions supporting
    multiple providers with automatic failover and cost optimization.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize LLM interface.
        
        Args:
            config: LLM configuration
        """
        self.config = config or LLMConfig()
        
        # Usage tracking
        self.usage_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'daily_cost': 0.0,
            'monthly_cost': 0.0,
            'last_reset_date': datetime.now().date()
        }
        
        # Provider availability
        self.provider_status = {
            LLMProvider.OPENAI: False,
            LLMProvider.OLLAMA: False
        }
        
        # Initialize providers
        self._initialize_providers()
        
        logger.info(f"LLM Interface initialized with primary provider: {self.config.primary_provider.value}")
    
    def _initialize_providers(self) -> None:
        """Initialize and test provider connections."""
        # Initialize OpenAI
        if OPENAI_AVAILABLE and self.config.openai_api_key:
            try:
                openai.api_key = self.config.openai_api_key
                if self.config.openai_base_url:
                    openai.api_base = self.config.openai_base_url
                
                # Test connection with a minimal request
                self._test_openai_connection()
                self.provider_status[LLMProvider.OPENAI] = True
                logger.info("OpenAI provider initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider: {e}")
                self.provider_status[LLMProvider.OPENAI] = False
        
        # Initialize Ollama
        if REQUESTS_AVAILABLE:
            try:
                self._test_ollama_connection()
                self.provider_status[LLMProvider.OLLAMA] = True
                logger.info("Ollama provider initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize Ollama provider: {e}")
                self.provider_status[LLMProvider.OLLAMA] = False
    
    def _test_openai_connection(self) -> None:
        """Test OpenAI connection."""
        if not OPENAI_AVAILABLE:
            raise LLMError("OpenAI library not available")
        
        try:
            # Simple test request
            response = openai.ChatCompletion.create(
                model=self.config.openai_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
                timeout=5.0
            )
            logger.debug("OpenAI connection test successful")
            
        except Exception as e:
            raise LLMError(f"OpenAI connection test failed: {e}")
    
    def _test_ollama_connection(self) -> None:
        """Test Ollama connection."""
        if not REQUESTS_AVAILABLE:
            raise LLMError("Requests library not available")
        
        try:
            # Test Ollama API availability
            response = requests.get(f"{self.config.ollama_base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            logger.debug("Ollama connection test successful")
            
        except Exception as e:
            raise LLMError(f"Ollama connection test failed: {e}")
    
    def _reset_daily_usage(self) -> None:
        """Reset daily usage statistics if needed."""
        current_date = datetime.now().date()
        if current_date > self.usage_stats['last_reset_date']:
            self.usage_stats['daily_cost'] = 0.0
            self.usage_stats['last_reset_date'] = current_date
            logger.info("Daily usage statistics reset")
    
    def _check_cost_limits(self) -> bool:
        """Check if cost limits are exceeded."""
        self._reset_daily_usage()
        
        if self.usage_stats['daily_cost'] >= self.config.cost_limit_daily:
            logger.warning(f"Daily cost limit exceeded: ${self.usage_stats['daily_cost']:.2f}")
            return False
        
        if self.usage_stats['monthly_cost'] >= self.config.cost_limit_monthly:
            logger.warning(f"Monthly cost limit exceeded: ${self.usage_stats['monthly_cost']:.2f}")
            return False
        
        return True
    
    def _estimate_cost(self, tokens: int, provider: LLMProvider) -> float:
        """Estimate cost for token usage."""
        if provider == LLMProvider.OPENAI:
            # GPT-4 pricing (approximate)
            cost_per_1k_tokens = 0.03  # $0.03 per 1K tokens
            return (tokens / 1000) * cost_per_1k_tokens
        else:
            # Local models have no direct cost
            return 0.0
    
    def _update_usage_stats(self, response: LLMResponse) -> None:
        """Update usage statistics."""
        self.usage_stats['total_requests'] += 1
        self.usage_stats['successful_requests'] += 1
        self.usage_stats['total_tokens'] += response.tokens_used
        self.usage_stats['total_cost'] += response.cost_estimate
        self.usage_stats['daily_cost'] += response.cost_estimate
        self.usage_stats['monthly_cost'] += response.cost_estimate
    
    async def _call_openai(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call OpenAI API."""
        if not self.provider_status[LLMProvider.OPENAI]:
            raise LLMError("OpenAI provider not available")
        
        start_time = time.time()
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.config.openai_model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout=self.config.timeout,
                **kwargs
            )
            
            response_time = time.time() - start_time
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            cost_estimate = self._estimate_cost(tokens_used, LLMProvider.OPENAI)
            
            return LLMResponse(
                content=content,
                provider=LLMProvider.OPENAI,
                model=self.config.openai_model,
                tokens_used=tokens_used,
                cost_estimate=cost_estimate,
                response_time=response_time,
                metadata={'response_id': response.id}
            )
            
        except Exception as e:
            self.usage_stats['failed_requests'] += 1
            raise LLMError(f"OpenAI API call failed: {e}")
    
    async def _call_ollama(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call Ollama API."""
        if not self.provider_status[LLMProvider.OLLAMA]:
            raise LLMError("Ollama provider not available")
        
        start_time = time.time()
        
        try:
            # Convert messages to Ollama format
            prompt = self._convert_messages_to_prompt(messages)
            
            payload = {
                "model": self.config.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            
            response = requests.post(
                f"{self.config.ollama_base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            response_time = time.time() - start_time
            result = response.json()
            content = result.get('response', '')
            
            # Estimate tokens (rough approximation)
            tokens_used = len(content.split()) * 1.3  # Approximate token count
            cost_estimate = self._estimate_cost(int(tokens_used), LLMProvider.OLLAMA)
            
            return LLMResponse(
                content=content,
                provider=LLMProvider.OLLAMA,
                model=self.config.ollama_model,
                tokens_used=int(tokens_used),
                cost_estimate=cost_estimate,
                response_time=response_time,
                metadata={'model_info': result.get('model', {})}
            )
            
        except Exception as e:
            self.usage_stats['failed_requests'] += 1
            raise LLMError(f"Ollama API call failed: {e}")
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to a single prompt for Ollama."""
        prompt_parts = []
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n".join(prompt_parts) + "\nAssistant:"

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        Complete a conversation with automatic provider failover.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for the LLM

        Returns:
            LLM response

        Raises:
            LLMError: If all providers fail or cost limits exceeded
        """
        # Check cost limits
        if not self._check_cost_limits():
            raise LLMError("Cost limits exceeded")

        # Try primary provider first
        providers_to_try = [self.config.primary_provider]
        if self.config.fallback_provider != self.config.primary_provider:
            providers_to_try.append(self.config.fallback_provider)

        last_error = None

        for provider in providers_to_try:
            if not self.provider_status[provider]:
                logger.warning(f"Provider {provider.value} not available, skipping")
                continue

            try:
                logger.info(f"Attempting completion with provider: {provider.value}")

                if provider == LLMProvider.OPENAI:
                    response = await self._call_openai(messages, **kwargs)
                elif provider == LLMProvider.OLLAMA:
                    response = await self._call_ollama(messages, **kwargs)
                else:
                    raise LLMError(f"Unsupported provider: {provider}")

                # Update usage statistics
                self._update_usage_stats(response)

                logger.info(f"Completion successful with {provider.value} "
                           f"({response.tokens_used} tokens, ${response.cost_estimate:.4f})")

                return response

            except Exception as e:
                last_error = e
                logger.error(f"Provider {provider.value} failed: {e}")
                continue

        # All providers failed
        raise LLMError(f"All providers failed. Last error: {last_error}")

    def complete_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        Synchronous version of complete method.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for the LLM

        Returns:
            LLM response
        """
        return asyncio.run(self.complete(messages, **kwargs))

    def simple_completion(self, prompt: str, **kwargs) -> str:
        """
        Simple completion with just a prompt string.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Response content as string
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.complete_sync(messages, **kwargs)
        return response.content

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return self.usage_stats.copy()

    def get_provider_status(self) -> Dict[LLMProvider, bool]:
        """Get current provider status."""
        return self.provider_status.copy()

    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self.usage_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'daily_cost': 0.0,
            'monthly_cost': 0.0,
            'last_reset_date': datetime.now().date()
        }
        logger.info("Usage statistics reset")

    def test_providers(self) -> Dict[LLMProvider, bool]:
        """Test all provider connections."""
        results = {}

        # Test OpenAI
        try:
            self._test_openai_connection()
            results[LLMProvider.OPENAI] = True
            self.provider_status[LLMProvider.OPENAI] = True
        except Exception as e:
            logger.error(f"OpenAI test failed: {e}")
            results[LLMProvider.OPENAI] = False
            self.provider_status[LLMProvider.OPENAI] = False

        # Test Ollama
        try:
            self._test_ollama_connection()
            results[LLMProvider.OLLAMA] = True
            self.provider_status[LLMProvider.OLLAMA] = True
        except Exception as e:
            logger.error(f"Ollama test failed: {e}")
            results[LLMProvider.OLLAMA] = False
            self.provider_status[LLMProvider.OLLAMA] = False

        return results

    def switch_primary_provider(self, provider: LLMProvider) -> bool:
        """
        Switch primary provider.

        Args:
            provider: New primary provider

        Returns:
            True if switch successful
        """
        if not self.provider_status[provider]:
            logger.error(f"Cannot switch to unavailable provider: {provider.value}")
            return False

        old_provider = self.config.primary_provider
        self.config.primary_provider = provider

        logger.info(f"Primary provider switched from {old_provider.value} to {provider.value}")
        return True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Log final usage statistics
        logger.info(f"LLM Interface session complete. "
                   f"Total requests: {self.usage_stats['total_requests']}, "
                   f"Total cost: ${self.usage_stats['total_cost']:.4f}")


# Convenience functions for quick usage
def create_llm_interface(config: Optional[LLMConfig] = None) -> LLMInterface:
    """Create and initialize LLM interface."""
    return LLMInterface(config)


def quick_completion(prompt: str, provider: Optional[LLMProvider] = None) -> str:
    """Quick completion with minimal setup."""
    config = LLMConfig()
    if provider:
        config.primary_provider = provider

    with create_llm_interface(config) as llm:
        return llm.simple_completion(prompt)
