"""
Process model for managing image processing operations
"""
import json
from typing import List, Dict, Any
from pathlib import Path


class Operation:
    """Base class for image processing operations"""

    def __init__(self, operation_type: str, parameters: Dict[str, Any]):
        self.type = operation_type
        self.parameters = parameters

    def to_dict(self) -> Dict[str, Any]:
        """Convert operation to dictionary for JSON serialization"""
        return {
            "type": self.type,
            "parameters": self.parameters
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Operation':
        """Create operation from dictionary"""
        return cls(data["type"], data["parameters"])

    def __repr__(self):
        return f"Operation(type={self.type}, parameters={self.parameters})"


class Process:
    """Container for a sequence of image processing operations"""

    def __init__(self, name: str = "Untitled Process"):
        self.name = name
        self.operations: List[Operation] = []

    def add_operation(self, operation: Operation):
        """Add an operation to the process"""
        self.operations.append(operation)

    def remove_operation(self, index: int):
        """Remove an operation at the given index"""
        if 0 <= index < len(self.operations):
            self.operations.pop(index)

    def move_operation(self, from_index: int, to_index: int):
        """Move an operation from one position to another"""
        if 0 <= from_index < len(self.operations) and 0 <= to_index < len(self.operations):
            operation = self.operations.pop(from_index)
            self.operations.insert(to_index, operation)

    def to_dict(self) -> Dict[str, Any]:
        """Convert process to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "operations": [op.to_dict() for op in self.operations]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Process':
        """Create process from dictionary"""
        process = cls(data.get("name", "Untitled Process"))
        for op_data in data.get("operations", []):
            process.add_operation(Operation.from_dict(op_data))
        return process

    def save(self, filepath: Path):
        """Save process to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> 'Process':
        """Load process from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def __repr__(self):
        return f"Process(name={self.name}, operations={len(self.operations)})"
