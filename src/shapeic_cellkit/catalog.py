"""Filesystem-backed public catalog for ShapeIC physical cell providers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

from .contracts import MagicTechnology, MacroLayout, PrimitiveLayout
from .errors import (
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
from .validation import load_primitive_descriptor


class CellKitCatalog:
    """Selected-PDK view of one ShapeIC CellKit checkout."""

    def __init__(
        self,
        root: Path,
        pdk: str,
        pdk_root: Path,
        technology: MagicTechnology,
        technology_digest: str,
    ):
        self._root = root
        self._pdk = pdk
        self._pdk_root = pdk_root
        self._technology = technology
        self._technology_digest = technology_digest
        self._primitive_paths = self._index_manifests(root / "primitives", "primitive.json")
        self._macro_paths = self._index_manifests(root / "macros", "layout.json")

    @classmethod
    def open(
        cls,
        root: Path | str,
        pdk: str,
        pdk_root: Path | str,
    ) -> "CellKitCatalog":
        root_path = Path(root).resolve()
        if not root_path.is_dir() or not (root_path / "primitives").is_dir():
            raise InvalidCellKitRootError(
                f"cellkit root does not contain a primitives directory: {root_path}"
            )
        _validate_pdk_name(pdk)
        pdk_root_path = Path(pdk_root).resolve()
        installed = (pdk_root_path / pdk).resolve()
        if not pdk_root_path.is_dir() or not installed.is_dir():
            raise PdkDirectoryNotFoundError(
                f"PDK '{pdk}' was not found at '{installed}'"
            )
        technology_root = root_path / "technologies" / pdk
        metadata_path = technology_root / "technology.toml"
        adapter_path = technology_root / "adapter.py"
        if not metadata_path.is_file() or not adapter_path.is_file():
            raise TechnologyNotFoundError(
                f"cellkit has no complete technology provider for PDK '{pdk}'"
            )
        try:
            with metadata_path.open("rb") as handle:
                metadata = tomllib.load(handle)
            module = _load_module(adapter_path, f"technology_{pdk}")
            factory = getattr(module, "create_technology", None)
            if not callable(factory):
                raise ProviderContractError(
                    "technology adapter must export create_technology(pdk_root, metadata)"
                )
            technology = factory(installed, metadata)
            if not isinstance(technology, MagicTechnology):
                raise ProviderContractError(
                    "technology adapter does not implement the MagicTechnology contract"
                )
            if technology.name != pdk:
                raise ProviderContractError(
                    f"technology adapter name must be '{pdk}'"
                )
            if technology.pdk_root.resolve() != installed:
                raise ProviderContractError(
                    "technology adapter pdk_root must be the selected PDK directory"
                )
            if not technology.revision.strip():
                raise ProviderContractError(
                    "technology adapter revision must be non-empty"
                )
            if not technology.magic_rcfile.is_file():
                raise ProviderContractError(
                    f"Magic rcfile does not exist: {technology.magic_rcfile}"
                )
            if any(
                not isinstance(command, str) or not command.strip()
                for command in technology.magic_startup_commands
            ):
                raise ProviderContractError(
                    "Magic startup commands must be non-empty strings"
                )
        except Exception as error:
            if isinstance(error, ProviderContractError):
                cause = error
            else:
                cause = ProviderContractError(str(error))
            raise TechnologyLoadError(
                f"could not load technology provider '{adapter_path}': {cause}"
            ) from error
        return cls(
            root_path,
            pdk,
            installed,
            technology,
            _files_digest((metadata_path, adapter_path), root_path),
        )

    @property
    def root(self) -> Path:
        return self._root

    @property
    def pdk(self) -> str:
        return self._pdk

    @property
    def pdk_root(self) -> Path:
        """Return the effective ``PDK_ROOT/PDK`` directory."""

        return self._pdk_root

    def technology(self) -> MagicTechnology:
        return self._technology

    @property
    def technology_digest(self) -> str:
        return self._technology_digest

    def primitive_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._primitive_paths))

    def primitive_descriptor(self, name: str):
        """Return manifest-derived physical topology without importing a PCell."""

        try:
            manifest_path = self._primitive_paths[name]
        except KeyError as error:
            raise PrimitiveNotFoundError(f"unknown primitive '{name}'") from error
        return load_primitive_descriptor(manifest_path)

    def primitive_descriptor_for_lut(self, lut_primitive: str):
        """Resolve the unique catalog primitive that publishes a LUT name."""

        descriptors = (
            self.primitive_descriptor(name) for name in self.primitive_names()
        )
        matches = [
            descriptor
            for descriptor in descriptors
            if descriptor.lut_primitive == lut_primitive
        ]
        if not matches:
            raise PrimitiveNotFoundError(
                f"no catalog primitive publishes LUT '{lut_primitive}'"
            )
        if len(matches) != 1:
            names = ", ".join(sorted(match.catalog_name for match in matches))
            raise ManifestValidationError(
                f"LUT primitive '{lut_primitive}' is published by multiple "
                f"catalog primitives: {names}"
            )
        return matches[0]

    def primitive(self, name: str) -> PrimitiveLayout:
        descriptor = self.primitive_descriptor(name)
        manifest_path = self._primitive_paths[name]
        provider_path = manifest_path.parent / self._pdk / "pcell.py"
        if not provider_path.is_file():
            raise ProviderNotFoundError(
                f"primitive '{name}' has no PCell provider for PDK '{self._pdk}'"
            )
        provider = _load_provider(
            provider_path,
            f"primitive_{name}_{self._pdk}",
        )
        return PrimitiveLayout(
            catalog_name=descriptor.catalog_name,
            lut_primitive=descriptor.lut_primitive,
            polarity=descriptor.polarity,
            operating_point_branch=descriptor.operating_point_branch,
            port_order=descriptor.port_order,
            branches=descriptor.branches,
            provider=provider,
            implementation_digest=_provider_digest(
                provider_path, provider, self._root
            ),
        )

    def macro_layout(self, name: str) -> MacroLayout:
        try:
            manifest_path = self._macro_paths[name]
        except KeyError as error:
            raise MacroLayoutNotFoundError(f"unknown macro layout '{name}'") from error
        provider_path = manifest_path.parent / self._pdk / "pcell.py"
        if not provider_path.is_file():
            raise ProviderNotFoundError(
                f"macro '{name}' has no PCell provider for PDK '{self._pdk}'"
            )
        raw = _load_json_object(manifest_path)
        port_order = _string_list(raw, "port_order", manifest_path)
        raw_instances = raw.get("instances")
        if not isinstance(raw_instances, dict) or not raw_instances:
            raise ManifestValidationError(
                f"macro layout '{manifest_path}' requires non-empty object 'instances'"
            )
        instances = []
        for instance, primitive in raw_instances.items():
            if not isinstance(instance, str) or not instance or not isinstance(primitive, str) or not primitive:
                raise ManifestValidationError(
                    f"macro layout '{manifest_path}' instances must map names to primitive names"
                )
            if primitive not in self._primitive_paths:
                raise ManifestValidationError(
                    f"macro layout '{manifest_path}' references unknown primitive '{primitive}'"
                )
            instances.append((instance, primitive))
        provider = _load_provider(provider_path, f"macro_{name}_{self._pdk}")
        return MacroLayout(
            name=name,
            port_order=port_order,
            instances=tuple(instances),
            provider=provider,
            implementation_digest=_sha256(provider_path),
        )

    @staticmethod
    def _index_manifests(root: Path, filename: str) -> dict[str, Path]:
        if not root.is_dir():
            return {}
        output: dict[str, Path] = {}
        for path in sorted(root.glob(f"*/{filename}")):
            raw = _load_json_object(path)
            name = raw.get("name")
            if not isinstance(name, str) or not name:
                raise ManifestValidationError(
                    f"catalog manifest '{path}' requires non-empty string 'name'"
                )
            if name in output:
                raise ManifestValidationError(f"duplicate catalog entry '{name}'")
            output[name] = path
        return output


def _validate_pdk_name(name: str) -> None:
    path = Path(name)
    if (
        not name
        or name in {".", ".."}
        or path.is_absolute()
        or len(path.parts) != 1
        or "/" in name
        or "\\" in name
    ):
        raise InvalidPdkNameError("PDK must be a single directory name")


def _load_module(path: Path, context: str) -> ModuleType:
    module_name = "_shapeic_cellkit_" + hashlib.sha256(
        f"{context}:{path}".encode("utf-8")
    ).hexdigest()
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ProviderContractError(f"could not create an import spec for '{path}'")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(module_name) is module:
            del sys.modules[module_name]
        raise
    return module


def _validate_provider(provider: ModuleType, path: Path) -> None:
    if not callable(getattr(provider, "build", None)):
        raise ProviderContractError(f"PCell provider '{path}' must export build()")
    policy = getattr(provider, "LAYOUT_POLICY", None)
    if not isinstance(policy, str) or not policy.strip():
        raise ProviderContractError(
            f"PCell provider '{path}' must define a non-empty LAYOUT_POLICY"
        )


def _load_provider(path: Path, context: str) -> ModuleType:
    try:
        provider = _load_module(path, context)
        _validate_provider(provider, path)
        return provider
    except ProviderContractError:
        raise
    except Exception as error:
        raise ProviderContractError(
            f"could not import PCell provider '{path}': {error}"
        ) from error


def _provider_digest(path: Path, provider: ModuleType, root: Path) -> str:
    files = [path]
    additional = getattr(provider, "IMPLEMENTATION_FILES", ())
    if not isinstance(additional, tuple) or any(
        not isinstance(value, Path) for value in additional
    ):
        raise ProviderContractError(
            f"PCell provider '{path}' IMPLEMENTATION_FILES must be a tuple of Paths"
        )
    files.extend(additional)
    digest = hashlib.sha256()
    for implementation in files:
        if not implementation.is_file():
            raise ProviderContractError(
                f"PCell implementation file does not exist: '{implementation}'"
            )
        resolved = implementation.resolve()
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError as error:
            raise ProviderContractError(
                f"PCell implementation file escapes CellKit: '{implementation}'"
            ) from error
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(implementation.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _files_digest(files: tuple[Path, ...], root: Path) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.resolve().relative_to(root.resolve())
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestValidationError(f"could not load catalog manifest '{path}': {error}") from error
    if not isinstance(value, dict):
        raise ManifestValidationError(f"catalog manifest '{path}' must be an object")
    return value


def _string_list(values: dict[str, Any], name: str, path: Path) -> tuple[str, ...]:
    value = values.get(name)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ManifestValidationError(
            f"macro layout '{path}' {name} must be a non-empty list of unique names"
        )
    return tuple(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
