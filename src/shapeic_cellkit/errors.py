"""Errors raised by the public ShapeIC CellKit catalog API."""

from __future__ import annotations


class CellKitError(Exception):
    """Base class for cellkit discovery and contract failures."""


class InvalidCellKitRootError(CellKitError):
    """The requested cellkit root does not contain a usable catalog."""


class InvalidPdkNameError(CellKitError):
    """A PDK selector is empty, unsafe, or not a single directory name."""


class PdkDirectoryNotFoundError(CellKitError):
    """The selected PDK is not installed below PDK_ROOT."""


class TechnologyNotFoundError(CellKitError):
    """The cellkit has no technology provider for the selected PDK."""


class TechnologyLoadError(CellKitError):
    """A technology provider could not be imported or violated its contract."""


class PrimitiveNotFoundError(CellKitError):
    """No primitive manifest has the requested catalog name."""


class MacroLayoutNotFoundError(CellKitError):
    """No physical macro layout has the requested name."""


class ProviderNotFoundError(CellKitError):
    """A catalog entry has no PCell provider for the selected PDK."""


class ManifestValidationError(CellKitError):
    """A primitive or macro layout manifest is structurally invalid."""


class ProviderContractError(CellKitError):
    """A dynamically loaded provider does not implement the public contract."""
