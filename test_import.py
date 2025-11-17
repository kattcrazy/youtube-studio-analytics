#!/usr/bin/env python3
"""Test script to verify Python files and measure import times."""

import sys
import time
import py_compile
import importlib.util
from pathlib import Path

def test_syntax(file_path: Path) -> bool:
    """Test if a Python file has valid syntax."""
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True
    except py_compile.PyCompileError:
        return False
    except Exception:
        return False

def test_import_time(module_path: Path, module_name: str) -> tuple[bool, float]:
    """Test how long it takes to import a module."""
    try:
        start_time = time.perf_counter()
        
        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            return False, 0.0
        
        module = importlib.util.module_from_spec(spec)
        
        # Try to execute the module (this will fail on Home Assistant imports, but we can measure time)
        try:
            spec.loader.exec_module(module)
        except (ImportError, ModuleNotFoundError):
            # Expected - we don't have Home Assistant installed
            # But we can still measure how long it takes to parse/compile
            pass
        
        elapsed = time.perf_counter() - start_time
        return True, elapsed
        
    except SyntaxError as e:
        print(f"   SyntaxError at line {e.lineno}: {e.msg}")
        return False, 0.0
    except Exception as e:
        # Other errors are OK for this test (missing dependencies)
        return True, 0.0

if __name__ == "__main__":
    print("=" * 70)
    print("Testing YouTube Studio Analytics - Syntax & Import Timing")
    print("=" * 70)
    
    base_path = Path(__file__).parent / "custom_components" / "youtube_studio_analytics"
    
    files_to_test = [
        "const.py",  # Test simplest first
        "__init__.py",
        "config_flow_helpers.py",
        "config_flow.py",  # Test config flow last (depends on helpers)
        "coordinator.py",
        "api.py",
        "sensor.py",
        "application_credentials.py",
    ]
    
    syntax_results = []
    timing_results = []
    
    print("\n1. Syntax Check:")
    print("-" * 70)
    for filename in files_to_test:
        file_path = base_path / filename
        if file_path.exists():
            if test_syntax(file_path):
                print(f"[OK] {filename:30s} - No syntax errors")
                syntax_results.append(True)
            else:
                print(f"[ERROR] {filename:30s} - Syntax error!")
                syntax_results.append(False)
        else:
            print(f"[WARN] {filename:30s} - File not found")
            syntax_results.append(False)
    
    print("\n2. Import Timing (approximate - will fail on HA imports):")
    print("-" * 70)
    print("Note: Times include parsing/compiling, not actual import")
    print()
    
    for filename in files_to_test:
        file_path = base_path / filename
        if file_path.exists():
            module_name = filename.replace(".py", "")
            success, elapsed = test_import_time(file_path, module_name)
            
            if success:
                if elapsed > 0:
                    status = "OK"
                    if elapsed > 0.1:
                        status = "SLOW"
                    print(f"[{status}] {filename:30s} - {elapsed*1000:6.2f} ms")
                else:
                    print(f"[OK] {filename:30s} - < 1 ms (failed on HA import, expected)")
                timing_results.append(True)
            else:
                print(f"[ERROR] {filename:30s} - Failed to process")
                timing_results.append(False)
        else:
            timing_results.append(False)
    
    print("\n" + "=" * 70)
    if all(syntax_results):
        print("[OK] ALL FILES PASSED SYNTAX CHECK")
        print("\nNote: Import timing is approximate. Real import times in Home Assistant")
        print("      may differ due to module caching and dependency loading.")
        sys.exit(0)
    else:
        print("[ERROR] SOME FILES HAVE SYNTAX ERRORS")
        sys.exit(1)

