from __future__ import annotations

import uuid
from typing import Any

from polaris_scanner.sca import Dependency


def export_cyclonedx_1_5(dependencies: list[Dependency], project_name: str = "polaris-project") -> dict[str, Any]:
    """Generate a CycloneDX 1.5 JSON SBOM from parsed dependencies."""
    components = []
    for dep in dependencies:
        eco = dep.ecosystem.lower()
        purl = f"pkg:{eco}/{dep.name}@{dep.version}"
        components.append(
            {
                "type": "library",
                "name": dep.name,
                "version": dep.version,
                "purl": purl,
                "bom-ref": purl,
            }
        )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": project_name,
            }
        },
        "components": components,
    }
