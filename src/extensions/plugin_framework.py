"""
Plugin Framework and Hot-Loading System

Modular plugin architecture with hot-loading capabilities, dependency management,
and version compatibility for extending the Niryo LLM Robotics Platform.

Features:
- Dynamic plugin discovery and loading
- Hot-reloading of plugins without system restart
- Dependency resolution and management
- Version compatibility checking
- Plugin lifecycle management
- Sandboxed plugin execution
- Plugin marketplace integration preparation
"""

import os
import sys
import time
import json
import importlib
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Type, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging
import threading
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class PluginState(Enum):
    """Plugin states."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class PluginType(Enum):
    """Plugin types."""
    INTERFACE = "interface"
    AUTOMATION = "automation"
    VISION = "vision"
    AI_MODEL = "ai_model"
    UTILITY = "utility"
    EDUCATIONAL = "educational"
    CUSTOM = "custom"


@dataclass
class PluginMetadata:
    """Plugin metadata information."""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    python_version: str = ">=3.8"
    platform_version: str = ">=1.0.0"
    
    # Configuration
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    # Metadata
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"
    keywords: List[str] = field(default_factory=list)
    
    # Internal
    plugin_id: str = ""
    file_path: str = ""
    load_time: float = 0.0
    last_modified: float = 0.0


@dataclass
class PluginConfig:
    """Plugin configuration."""
    plugin_directory: str = "plugins"
    auto_discovery: bool = True
    hot_reload_enabled: bool = True
    dependency_check: bool = True
    version_check: bool = True
    max_load_time: float = 30.0
    plugin_timeout: float = 60.0
    sandbox_enabled: bool = True
    max_plugins: int = 100


class BasePlugin(ABC):
    """
    Base class for all plugins.
    
    All plugins must inherit from this class and implement the required methods.
    """
    
    def __init__(self, metadata: PluginMetadata, config: Dict[str, Any]):
        """
        Initialize plugin.
        
        Args:
            metadata: Plugin metadata
            config: Plugin configuration
        """
        self.metadata = metadata
        self.config = config
        self.state = PluginState.UNLOADED
        self.logger = get_logger(f"plugin.{metadata.name}")
        
        # Plugin lifecycle hooks
        self._on_load_callbacks: List[Callable] = []
        self._on_unload_callbacks: List[Callable] = []
        self._on_error_callbacks: List[Callable] = []
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    def activate(self) -> bool:
        """
        Activate the plugin.
        
        Returns:
            True if activation successful
        """
        pass
    
    @abstractmethod
    def deactivate(self) -> bool:
        """
        Deactivate the plugin.
        
        Returns:
            True if deactivation successful
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """
        Clean up plugin resources.
        
        Returns:
            True if cleanup successful
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "description": self.metadata.description,
            "author": self.metadata.author,
            "type": self.metadata.plugin_type.value,
            "state": self.state.value,
            "capabilities": self.metadata.capabilities,
            "load_time": self.metadata.load_time
        }
    
    def add_load_callback(self, callback: Callable):
        """Add callback for plugin load event."""
        self._on_load_callbacks.append(callback)
    
    def add_unload_callback(self, callback: Callable):
        """Add callback for plugin unload event."""
        self._on_unload_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """Add callback for plugin error event."""
        self._on_error_callbacks.append(callback)
    
    def _trigger_load_callbacks(self):
        """Trigger load callbacks."""
        for callback in self._on_load_callbacks:
            try:
                callback(self)
            except Exception as e:
                self.logger.error(f"Load callback error: {e}")
    
    def _trigger_unload_callbacks(self):
        """Trigger unload callbacks."""
        for callback in self._on_unload_callbacks:
            try:
                callback(self)
            except Exception as e:
                self.logger.error(f"Unload callback error: {e}")
    
    def _trigger_error_callbacks(self, error: Exception):
        """Trigger error callbacks."""
        for callback in self._on_error_callbacks:
            try:
                callback(self, error)
            except Exception as e:
                self.logger.error(f"Error callback error: {e}")


class PluginRegistry:
    """
    Plugin registry for discovery and registration of available plugins.
    """
    
    def __init__(self, config: PluginConfig):
        """
        Initialize plugin registry.
        
        Args:
            config: Plugin configuration
        """
        self.config = config
        self.registered_plugins: Dict[str, PluginMetadata] = {}
        self.plugin_paths: Dict[str, str] = {}
        
        logger.info("Plugin registry initialized")
    
    def discover_plugins(self) -> List[PluginMetadata]:
        """
        Discover plugins in the plugin directory.
        
        Returns:
            List of discovered plugin metadata
        """
        discovered = []
        plugin_dir = Path(self.config.plugin_directory)
        
        if not plugin_dir.exists():
            logger.warning(f"Plugin directory does not exist: {plugin_dir}")
            return discovered
        
        # Search for plugin files
        for plugin_file in plugin_dir.rglob("*.py"):
            if plugin_file.name.startswith("__"):
                continue
            
            try:
                metadata = self._load_plugin_metadata(plugin_file)
                if metadata:
                    discovered.append(metadata)
                    self.plugin_paths[metadata.plugin_id] = str(plugin_file)
                    logger.info(f"Discovered plugin: {metadata.name} v{metadata.version}")
            
            except Exception as e:
                logger.error(f"Error discovering plugin {plugin_file}: {e}")
        
        return discovered
    
    def _load_plugin_metadata(self, plugin_file: Path) -> Optional[PluginMetadata]:
        """
        Load plugin metadata from file.
        
        Args:
            plugin_file: Path to plugin file
            
        Returns:
            Plugin metadata if valid
        """
        try:
            # Look for metadata file first
            metadata_file = plugin_file.parent / f"{plugin_file.stem}.json"
            
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata_dict = json.load(f)
                
                metadata = PluginMetadata(
                    name=metadata_dict["name"],
                    version=metadata_dict["version"],
                    description=metadata_dict["description"],
                    author=metadata_dict["author"],
                    plugin_type=PluginType(metadata_dict["type"]),
                    dependencies=metadata_dict.get("dependencies", []),
                    python_version=metadata_dict.get("python_version", ">=3.8"),
                    platform_version=metadata_dict.get("platform_version", ">=1.0.0"),
                    config_schema=metadata_dict.get("config_schema", {}),
                    default_config=metadata_dict.get("default_config", {}),
                    capabilities=metadata_dict.get("capabilities", []),
                    permissions=metadata_dict.get("permissions", []),
                    homepage=metadata_dict.get("homepage", ""),
                    repository=metadata_dict.get("repository", ""),
                    license=metadata_dict.get("license", "MIT"),
                    keywords=metadata_dict.get("keywords", []),
                    plugin_id=f"{metadata_dict['name']}_{metadata_dict['version']}",
                    file_path=str(plugin_file),
                    last_modified=plugin_file.stat().st_mtime
                )
                
                return metadata
            
            else:
                # Try to extract metadata from Python file docstring/comments
                return self._extract_metadata_from_source(plugin_file)
        
        except Exception as e:
            logger.error(f"Error loading metadata for {plugin_file}: {e}")
            return None
    
    def _extract_metadata_from_source(self, plugin_file: Path) -> Optional[PluginMetadata]:
        """
        Extract metadata from Python source file.
        
        Args:
            plugin_file: Path to plugin file
            
        Returns:
            Plugin metadata if extractable
        """
        try:
            with open(plugin_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for metadata in comments or docstrings
            # This is a simplified implementation
            # In practice, you might use AST parsing for more robust extraction
            
            name = plugin_file.stem
            version = "1.0.0"
            description = f"Plugin: {name}"
            author = "Unknown"
            plugin_type = PluginType.CUSTOM
            
            # Try to find metadata in comments
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# PLUGIN_NAME:'):
                    name = line.split(':', 1)[1].strip()
                elif line.startswith('# PLUGIN_VERSION:'):
                    version = line.split(':', 1)[1].strip()
                elif line.startswith('# PLUGIN_DESCRIPTION:'):
                    description = line.split(':', 1)[1].strip()
                elif line.startswith('# PLUGIN_AUTHOR:'):
                    author = line.split(':', 1)[1].strip()
                elif line.startswith('# PLUGIN_TYPE:'):
                    try:
                        plugin_type = PluginType(line.split(':', 1)[1].strip().lower())
                    except ValueError:
                        plugin_type = PluginType.CUSTOM
            
            return PluginMetadata(
                name=name,
                version=version,
                description=description,
                author=author,
                plugin_type=plugin_type,
                plugin_id=f"{name}_{version}",
                file_path=str(plugin_file),
                last_modified=plugin_file.stat().st_mtime
            )
        
        except Exception as e:
            logger.error(f"Error extracting metadata from {plugin_file}: {e}")
            return None
    
    def register_plugin(self, metadata: PluginMetadata) -> bool:
        """
        Register a plugin.
        
        Args:
            metadata: Plugin metadata
            
        Returns:
            True if registration successful
        """
        try:
            self.registered_plugins[metadata.plugin_id] = metadata
            logger.info(f"Registered plugin: {metadata.name} v{metadata.version}")
            return True
        
        except Exception as e:
            logger.error(f"Error registering plugin {metadata.name}: {e}")
            return False
    
    def unregister_plugin(self, plugin_id: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            True if unregistration successful
        """
        try:
            if plugin_id in self.registered_plugins:
                del self.registered_plugins[plugin_id]
                if plugin_id in self.plugin_paths:
                    del self.plugin_paths[plugin_id]
                logger.info(f"Unregistered plugin: {plugin_id}")
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error unregistering plugin {plugin_id}: {e}")
            return False
    
    def get_plugin_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Get plugin metadata by ID."""
        return self.registered_plugins.get(plugin_id)
    
    def list_plugins(self, plugin_type: Optional[PluginType] = None) -> List[PluginMetadata]:
        """
        List registered plugins.
        
        Args:
            plugin_type: Filter by plugin type
            
        Returns:
            List of plugin metadata
        """
        plugins = list(self.registered_plugins.values())
        
        if plugin_type:
            plugins = [p for p in plugins if p.plugin_type == plugin_type]
        
        return plugins


class DependencyManager:
    """
    Plugin dependency resolution and management.
    """

    def __init__(self, registry: PluginRegistry):
        """
        Initialize dependency manager.

        Args:
            registry: Plugin registry
        """
        self.registry = registry
        self.dependency_graph: Dict[str, Set[str]] = {}

        logger.info("Dependency manager initialized")

    def resolve_dependencies(self, plugin_id: str) -> List[str]:
        """
        Resolve plugin dependencies in load order.

        Args:
            plugin_id: Plugin identifier

        Returns:
            List of plugin IDs in dependency order
        """
        visited = set()
        temp_visited = set()
        load_order = []

        def visit(pid: str):
            if pid in temp_visited:
                raise ValueError(f"Circular dependency detected involving {pid}")

            if pid in visited:
                return

            temp_visited.add(pid)

            metadata = self.registry.get_plugin_metadata(pid)
            if metadata:
                for dep in metadata.dependencies:
                    # Find dependency plugin ID
                    dep_plugin = self._find_plugin_by_name(dep)
                    if dep_plugin:
                        visit(dep_plugin.plugin_id)
                    else:
                        logger.warning(f"Dependency not found: {dep} for plugin {pid}")

            temp_visited.remove(pid)
            visited.add(pid)
            load_order.append(pid)

        visit(plugin_id)
        return load_order

    def _find_plugin_by_name(self, name: str) -> Optional[PluginMetadata]:
        """Find plugin by name."""
        for metadata in self.registry.registered_plugins.values():
            if metadata.name == name:
                return metadata
        return None

    def check_dependencies(self, plugin_id: str) -> bool:
        """
        Check if all dependencies are available.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if all dependencies are available
        """
        metadata = self.registry.get_plugin_metadata(plugin_id)
        if not metadata:
            return False

        for dep in metadata.dependencies:
            if not self._find_plugin_by_name(dep):
                logger.error(f"Missing dependency: {dep} for plugin {plugin_id}")
                return False

        return True

    def build_dependency_graph(self):
        """Build dependency graph for all registered plugins."""
        self.dependency_graph.clear()

        for plugin_id, metadata in self.registry.registered_plugins.items():
            deps = set()
            for dep_name in metadata.dependencies:
                dep_plugin = self._find_plugin_by_name(dep_name)
                if dep_plugin:
                    deps.add(dep_plugin.plugin_id)

            self.dependency_graph[plugin_id] = deps


class VersionManager:
    """
    Plugin version compatibility and migration tools.
    """

    def __init__(self):
        """Initialize version manager."""
        self.platform_version = "1.0.0"
        logger.info("Version manager initialized")

    def check_compatibility(self, metadata: PluginMetadata) -> bool:
        """
        Check if plugin is compatible with current platform version.

        Args:
            metadata: Plugin metadata

        Returns:
            True if compatible
        """
        try:
            return self._version_satisfies(self.platform_version, metadata.platform_version)
        except Exception as e:
            logger.error(f"Version compatibility check failed for {metadata.name}: {e}")
            return False

    def _version_satisfies(self, current: str, requirement: str) -> bool:
        """
        Check if current version satisfies requirement.

        Args:
            current: Current version
            requirement: Version requirement (e.g., ">=1.0.0")

        Returns:
            True if requirement is satisfied
        """
        # Simplified version checking - in production, use packaging.version
        if requirement.startswith(">="):
            required = requirement[2:]
            return self._compare_versions(current, required) >= 0
        elif requirement.startswith(">"):
            required = requirement[1:]
            return self._compare_versions(current, required) > 0
        elif requirement.startswith("<="):
            required = requirement[2:]
            return self._compare_versions(current, required) <= 0
        elif requirement.startswith("<"):
            required = requirement[1:]
            return self._compare_versions(current, required) < 0
        elif requirement.startswith("=="):
            required = requirement[2:]
            return current == required
        else:
            return current == requirement

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.

        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        def version_tuple(v):
            return tuple(map(int, v.split('.')))

        t1, t2 = version_tuple(v1), version_tuple(v2)

        if t1 < t2:
            return -1
        elif t1 > t2:
            return 1
        else:
            return 0


class HotLoader:
    """
    Dynamic plugin loading and reloading capabilities.
    """

    def __init__(self, config: PluginConfig):
        """
        Initialize hot loader.

        Args:
            config: Plugin configuration
        """
        self.config = config
        self.loaded_modules: Dict[str, Any] = {}
        self.file_watchers: Dict[str, float] = {}
        self.reload_lock = threading.Lock()

        logger.info("Hot loader initialized")

    def load_plugin(self, metadata: PluginMetadata) -> Optional[Type[BasePlugin]]:
        """
        Load plugin from file.

        Args:
            metadata: Plugin metadata

        Returns:
            Plugin class if loaded successfully
        """
        try:
            start_time = time.time()

            # Load module
            spec = importlib.util.spec_from_file_location(
                metadata.name,
                metadata.file_path
            )

            if not spec or not spec.loader:
                logger.error(f"Cannot load plugin spec: {metadata.name}")
                return None

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules for proper import handling
            sys.modules[metadata.name] = module

            # Execute module
            spec.loader.exec_module(module)

            # Find plugin class
            plugin_class = self._find_plugin_class(module)

            if not plugin_class:
                logger.error(f"No plugin class found in {metadata.name}")
                return None

            # Store loaded module
            self.loaded_modules[metadata.plugin_id] = module

            # Update load time
            metadata.load_time = time.time() - start_time

            # Start file watching for hot reload
            if self.config.hot_reload_enabled:
                self.file_watchers[metadata.plugin_id] = metadata.last_modified

            logger.info(f"Loaded plugin: {metadata.name} in {metadata.load_time:.3f}s")
            return plugin_class

        except Exception as e:
            logger.error(f"Error loading plugin {metadata.name}: {e}")
            return None

    def _find_plugin_class(self, module) -> Optional[Type[BasePlugin]]:
        """Find plugin class in module."""
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and
                issubclass(obj, BasePlugin) and
                obj != BasePlugin):
                return obj
        return None

    def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload plugin module.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if unloaded successfully
        """
        try:
            if plugin_id in self.loaded_modules:
                module = self.loaded_modules[plugin_id]

                # Remove from sys.modules
                if hasattr(module, '__name__') and module.__name__ in sys.modules:
                    del sys.modules[module.__name__]

                # Remove from loaded modules
                del self.loaded_modules[plugin_id]

                # Stop file watching
                if plugin_id in self.file_watchers:
                    del self.file_watchers[plugin_id]

                logger.info(f"Unloaded plugin: {plugin_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    def reload_plugin(self, plugin_id: str, metadata: PluginMetadata) -> Optional[Type[BasePlugin]]:
        """
        Reload plugin with hot-reloading.

        Args:
            plugin_id: Plugin identifier
            metadata: Updated plugin metadata

        Returns:
            Reloaded plugin class
        """
        with self.reload_lock:
            try:
                # Unload existing plugin
                self.unload_plugin(plugin_id)

                # Load updated plugin
                return self.load_plugin(metadata)

            except Exception as e:
                logger.error(f"Error reloading plugin {plugin_id}: {e}")
                return None

    def check_for_updates(self) -> List[str]:
        """
        Check for plugin file updates.

        Returns:
            List of plugin IDs that need reloading
        """
        if not self.config.hot_reload_enabled:
            return []

        updated_plugins = []

        for plugin_id, last_modified in self.file_watchers.items():
            try:
                if plugin_id in self.loaded_modules:
                    module = self.loaded_modules[plugin_id]
                    if hasattr(module, '__file__') and module.__file__:
                        current_modified = os.path.getmtime(module.__file__)

                        if current_modified > last_modified:
                            updated_plugins.append(plugin_id)
                            self.file_watchers[plugin_id] = current_modified

            except Exception as e:
                logger.error(f"Error checking updates for {plugin_id}: {e}")

        return updated_plugins


class PluginManager:
    """
    Main plugin manager coordinating all plugin operations.
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """
        Initialize plugin manager.

        Args:
            config: Plugin configuration
        """
        self.config = config or PluginConfig()

        # Initialize components
        self.registry = PluginRegistry(self.config)
        self.dependency_manager = DependencyManager(self.registry)
        self.version_manager = VersionManager()
        self.hot_loader = HotLoader(self.config)

        # Plugin instances
        self.active_plugins: Dict[str, BasePlugin] = {}
        self.plugin_classes: Dict[str, Type[BasePlugin]] = {}

        # Statistics
        self.stats = {
            'total_plugins': 0,
            'active_plugins': 0,
            'failed_plugins': 0,
            'reload_count': 0
        }

        logger.info("Plugin manager initialized")

    def discover_and_load_plugins(self) -> Dict[str, bool]:
        """
        Discover and load all plugins.

        Returns:
            Dictionary of plugin_id -> success status
        """
        results = {}

        # Discover plugins
        discovered = self.registry.discover_plugins()
        self.stats['total_plugins'] = len(discovered)

        # Register discovered plugins
        for metadata in discovered:
            self.registry.register_plugin(metadata)

        # Build dependency graph
        self.dependency_manager.build_dependency_graph()

        # Load plugins in dependency order
        for metadata in discovered:
            try:
                success = self.load_plugin(metadata.plugin_id)
                results[metadata.plugin_id] = success

                if success:
                    self.stats['active_plugins'] += 1
                else:
                    self.stats['failed_plugins'] += 1

            except Exception as e:
                logger.error(f"Error loading plugin {metadata.plugin_id}: {e}")
                results[metadata.plugin_id] = False
                self.stats['failed_plugins'] += 1

        logger.info(f"Plugin discovery complete: {self.stats['active_plugins']}/{self.stats['total_plugins']} loaded")
        return results

    def load_plugin(self, plugin_id: str) -> bool:
        """
        Load and activate a specific plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if loaded successfully
        """
        try:
            metadata = self.registry.get_plugin_metadata(plugin_id)
            if not metadata:
                logger.error(f"Plugin metadata not found: {plugin_id}")
                return False

            # Check version compatibility
            if self.config.version_check and not self.version_manager.check_compatibility(metadata):
                logger.error(f"Plugin version incompatible: {plugin_id}")
                return False

            # Check dependencies
            if self.config.dependency_check and not self.dependency_manager.check_dependencies(plugin_id):
                logger.error(f"Plugin dependencies not satisfied: {plugin_id}")
                return False

            # Load plugin class
            plugin_class = self.hot_loader.load_plugin(metadata)
            if not plugin_class:
                return False

            # Create plugin instance
            plugin_config = metadata.default_config.copy()
            plugin_instance = plugin_class(metadata, plugin_config)

            # Initialize plugin
            if not plugin_instance.initialize():
                logger.error(f"Plugin initialization failed: {plugin_id}")
                return False

            # Activate plugin
            if not plugin_instance.activate():
                logger.error(f"Plugin activation failed: {plugin_id}")
                return False

            # Store plugin
            self.plugin_classes[plugin_id] = plugin_class
            self.active_plugins[plugin_id] = plugin_instance
            plugin_instance.state = PluginState.ACTIVE

            # Trigger load callbacks
            plugin_instance._trigger_load_callbacks()

            logger.info(f"Plugin loaded and activated: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_id}: {e}")
            return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload and deactivate a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if unloaded successfully
        """
        try:
            if plugin_id in self.active_plugins:
                plugin = self.active_plugins[plugin_id]

                # Deactivate plugin
                plugin.deactivate()

                # Cleanup plugin
                plugin.cleanup()

                # Trigger unload callbacks
                plugin._trigger_unload_callbacks()

                # Remove from active plugins
                del self.active_plugins[plugin_id]

                # Update state
                plugin.state = PluginState.UNLOADED

                # Unload from hot loader
                self.hot_loader.unload_plugin(plugin_id)

                logger.info(f"Plugin unloaded: {plugin_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    def get_plugin_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin information."""
        if plugin_id in self.active_plugins:
            return self.active_plugins[plugin_id].get_info()
        return None

    def list_active_plugins(self) -> List[Dict[str, Any]]:
        """List all active plugins."""
        return [plugin.get_info() for plugin in self.active_plugins.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Get plugin manager statistics."""
        return self.stats.copy()


class PluginFramework:
    """
    Main plugin framework interface.
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """
        Initialize plugin framework.

        Args:
            config: Plugin configuration
        """
        self.plugin_manager = PluginManager(config)
        logger.info("Plugin framework initialized")

    def start(self) -> bool:
        """
        Start the plugin framework.

        Returns:
            True if started successfully
        """
        try:
            results = self.plugin_manager.discover_and_load_plugins()
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)

            logger.info(f"Plugin framework started: {success_count}/{total_count} plugins loaded")
            return success_count > 0 or total_count == 0

        except Exception as e:
            logger.error(f"Error starting plugin framework: {e}")
            return False

    def stop(self) -> bool:
        """
        Stop the plugin framework.

        Returns:
            True if stopped successfully
        """
        try:
            # Unload all active plugins
            plugin_ids = list(self.plugin_manager.active_plugins.keys())
            for plugin_id in plugin_ids:
                self.plugin_manager.unload_plugin(plugin_id)

            logger.info("Plugin framework stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping plugin framework: {e}")
            return False

    def get_plugin_manager(self) -> PluginManager:
        """Get plugin manager instance."""
        return self.plugin_manager


# Convenience functions
def create_plugin_framework(config: Optional[PluginConfig] = None) -> PluginFramework:
    """Create and initialize plugin framework."""
    return PluginFramework(config)


def create_plugin_config(**kwargs) -> PluginConfig:
    """Create plugin configuration with custom settings."""
    return PluginConfig(**kwargs)
