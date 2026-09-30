"""Public API for ShapeIC logical and physical cell catalogs."""

from .catalog import CellKitCatalog
from .drc import DrcResult, run_drc
from .lvs import LvsResult, run_lvs
from .contracts import (
    GeometryLimits,
    MacroLayout,
    MacroNet,
    MagicTechnology,
    MosPolarity,
    PhysicalMosBranch,
    PrimitiveGeometry,
    PrimitiveLayout,
    RenderedCell,
)
from .errors import (
    CellKitError,
    GeometryConstraintError,
    InvalidCellKitRootError,
    InvalidPdkNameError,
    MacroLayoutNotFoundError,
    ManifestValidationError,
    PdkDirectoryNotFoundError,
    PrimitiveNotFoundError,
    ProviderContractError,
    ProviderNotFoundError,
    TechnologyLoadError,
    TechnologyNotFoundError,
)
from .validation import PrimitiveDescriptor, load_primitive_descriptor

__all__ = [
    "CellKitCatalog",
    "CellKitError",
    "GeometryConstraintError",
    "GeometryLimits",
    "InvalidCellKitRootError",
    "InvalidPdkNameError",
    "LvsResult",
    "MacroLayout",
    "MacroNet",
    "MacroLayoutNotFoundError",
    "MagicTechnology",
    "ManifestValidationError",
    "MosPolarity",
    "PdkDirectoryNotFoundError",
    "PhysicalMosBranch",
    "PrimitiveDescriptor",
    "PrimitiveGeometry",
    "PrimitiveLayout",
    "PrimitiveNotFoundError",
    "ProviderContractError",
    "ProviderNotFoundError",
    "RenderedCell",
    "TechnologyLoadError",
    "TechnologyNotFoundError",
    "load_primitive_descriptor",
    "run_drc",
    "run_lvs",
]
