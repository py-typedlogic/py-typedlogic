import pytest
import shutil

# Check for external dependencies
has_prover9 = shutil.which("prover9") is not None
has_souffle = shutil.which("souffle") is not None

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "prover9: mark tests requiring prover9 executable")
    config.addinivalue_line("markers", "souffle: mark tests requiring souffle executable")
    
def pytest_collection_modifyitems(config, items):
    """Skip tests based on available executables."""
    for item in items:
        if "prover9" in item.keywords and not has_prover9:
            item.add_marker(pytest.mark.skip(reason="Prover9 executable not found"))
        if "souffle" in item.keywords and not has_souffle:
            item.add_marker(pytest.mark.skip(reason="Souffle executable not found"))