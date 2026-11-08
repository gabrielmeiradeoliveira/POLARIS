"""POLARIS Cross-File Contract Analysis module package."""

from polaris.contracts.engine import CrossFileContractEngine
from polaris.contracts.models import (
    ContractFinding,
    ContractKind,
    IncompatibilityEvidence,
    InferredContract,
    PropagationStep,
)

__all__ = [
    "CrossFileContractEngine",
    "ContractFinding",
    "ContractKind",
    "IncompatibilityEvidence",
    "InferredContract",
    "PropagationStep",
]
