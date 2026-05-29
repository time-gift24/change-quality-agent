from pathlib import Path

API_V1_DIR = Path(__file__).resolve().parents[1] / "app" / "api" / "v1"


def test_api_routes_do_not_depend_on_repositories_directly() -> None:
    violations: list[str] = []
    for route_file in sorted(API_V1_DIR.glob("*.py")):
        if route_file.name == "__init__.py":
            continue
        source = route_file.read_text()
        for forbidden in (
            "from app.repositories",
            "RepositoryDep",
            "SessionDep",
        ):
            if forbidden in source:
                violations.append(f"{route_file.name}: {forbidden}")

    assert violations == []
