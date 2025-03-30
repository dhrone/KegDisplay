"""
Tests for factory interfaces and the dependency container.

These tests demonstrate how to:
1. Create mock factories for testing
2. Inject mock factories into the dependency container
3. Verify that the correct factory methods are called
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from PIL import Image

from KegDisplay.dependency_container import DependencyContainer
from KegDisplay.factories import (
    DisplayFactoryInterface,
    RendererFactoryInterface, 
    DataManagerFactoryInterface,
    DatasetFactoryInterface
)


class MockDisplayFactory(DisplayFactoryInterface):
    """Mock implementation of DisplayFactoryInterface for testing."""
    
    def __init__(self):
        self.create_display_called = False
        self.last_config = None
        self.mock_display = Mock()
        
    def create_display(self, config):
        """Record that this method was called and return a mock display."""
        self.create_display_called = True
        self.last_config = config
        return self.mock_display


class MockRendererFactory(RendererFactoryInterface):
    """Mock implementation of RendererFactoryInterface for testing."""
    
    def __init__(self):
        self.create_renderer_called = False
        self.last_display = None
        self.last_dataset = None
        self.last_config = None
        self.mock_renderer = Mock()
        
    def create_renderer(self, display, dataset_obj, config):
        """Record that this method was called and return a mock renderer."""
        self.create_renderer_called = True
        self.last_display = display
        self.last_dataset = dataset_obj
        self.last_config = config
        return self.mock_renderer


class MockDataManagerFactory(DataManagerFactoryInterface):
    """Mock implementation of DataManagerFactoryInterface for testing."""
    
    def __init__(self):
        self.create_data_manager_called = False
        self.last_db_path = None
        self.last_renderer = None
        self.mock_data_manager = Mock()
        
    def create_data_manager(self, db_path, renderer):
        """Record that this method was called and return a mock data manager."""
        self.create_data_manager_called = True
        self.last_db_path = db_path
        self.last_renderer = renderer
        return self.mock_data_manager


class MockDatasetFactory(DatasetFactoryInterface):
    """Mock implementation of DatasetFactoryInterface for testing."""
    
    def __init__(self):
        self.create_dataset_called = False
        self.last_config = None
        self.mock_dataset = Mock()
        
    def create_dataset(self, config):
        """Record that this method was called and return a mock dataset."""
        self.create_dataset_called = True
        self.last_config = config
        return self.mock_dataset


class TestDependencyContainerWithFactories(unittest.TestCase):
    """Test the DependencyContainer using mock factories."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Create mock factories
        self.mock_display_factory = MockDisplayFactory()
        self.mock_renderer_factory = MockRendererFactory()
        self.mock_data_manager_factory = MockDataManagerFactory()
        self.mock_dataset_factory = MockDatasetFactory()
        
        # Create mock config manager
        self.mock_config_manager = Mock()
        self.mock_config_manager.validate_config = MagicMock(return_value=True)
        self.mock_config_manager.get_config = MagicMock(return_value={
            'display': 'ws0010',
            'interface': 'bitbang',
            'RS': 7,
            'E': 8,
            'PINS': [25, 5, 6, 12],
            'tap': 1,
            'page': 'test_page.yaml',
            'db': 'test_db.db',
            'log_level': 'INFO'
        })
        
        # Create dependency container with mock factories
        self.container = DependencyContainer(
            display_factory=self.mock_display_factory,
            renderer_factory=self.mock_renderer_factory,
            data_manager_factory=self.mock_data_manager_factory,
            dataset_factory=self.mock_dataset_factory
        )
        
        # Replace get_config_manager with a mock
        self.container.get_config_manager = MagicMock(return_value=self.mock_config_manager)
    
    def test_create_application_components_calls_factories(self):
        """Test that create_application_components calls all factory methods."""
        # When
        config_manager, display, renderer, data_manager = self.container.create_application_components()
        
        # Then
        self.assertTrue(self.mock_display_factory.create_display_called)
        self.assertTrue(self.mock_renderer_factory.create_renderer_called)
        self.assertTrue(self.mock_data_manager_factory.create_data_manager_called)
        self.assertTrue(self.mock_dataset_factory.create_dataset_called)
    
    def test_factories_receive_correct_parameters(self):
        """Test that factories receive the correct parameters."""
        # When
        config_manager, display, renderer, data_manager = self.container.create_application_components()
        
        # Then
        # Check that display factory received config
        self.assertEqual(self.mock_display_factory.last_config['display'], 'ws0010')
        
        # Check that renderer factory received display and dataset
        self.assertEqual(self.mock_renderer_factory.last_display, self.mock_display_factory.mock_display)
        self.assertEqual(self.mock_renderer_factory.last_dataset, self.mock_dataset_factory.mock_dataset)
        
        # Check that data manager factory received db_path and renderer
        self.assertEqual(self.mock_data_manager_factory.last_db_path, 'test_db.db')
        self.assertEqual(self.mock_data_manager_factory.last_renderer, self.mock_renderer_factory.mock_renderer)
    
    def test_create_application_components_returns_factory_products(self):
        """Test that create_application_components returns factory products."""
        # When
        config_manager, display, renderer, data_manager = self.container.create_application_components()
        
        # Then
        self.assertEqual(config_manager, self.mock_config_manager)
        self.assertEqual(display, self.mock_display_factory.mock_display)
        self.assertEqual(renderer, self.mock_renderer_factory.mock_renderer)
        self.assertEqual(data_manager, self.mock_data_manager_factory.mock_data_manager)
    
    def test_dependency_container_can_be_created_without_factories(self):
        """Test that DependencyContainer can be created without factory arguments."""
        # When
        container = DependencyContainer()
        
        # Then - just verify it can be created without exceptions
        self.assertIsNotNone(container)
        self.assertIsNotNone(container.display_factory)
        self.assertIsNotNone(container.renderer_factory)
        self.assertIsNotNone(container.data_manager_factory)
        self.assertIsNotNone(container.dataset_factory)


if __name__ == '__main__':
    unittest.main() 