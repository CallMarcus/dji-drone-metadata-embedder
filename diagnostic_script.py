#!/usr/bin/env python3
"""Diagnostic script to identify issues with DJI Metadata Embedder setup."""
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime


class DiagnosticTool:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
        self.project_root = Path.cwd()
        
    def log_issue(self, msg):
        self.issues.append(f"❌ {msg}")
        
    def log_warning(self, msg):
        self.warnings.append(f"⚠️  {msg}")
        
    def log_info(self, msg):
        self.info.append(f"ℹ️  {msg}")
        
    def check_project_structure(self):
        """Check if project structure is correct."""
        print("\n🔍 Checking project structure...")
        
        # Check for duplicate package locations
        if (self.project_root / "dji_metadata_embedder").exists() and \
           (self.project_root / "src" / "dji_metadata_embedder").exists():
            self.log_issue("Duplicate package locations found: /dji_metadata_embedder and /src/dji_metadata_embedder")
        
        # Check for correct package location
        if not (self.project_root / "src" / "dji_metadata_embedder").exists():
            self.log_issue("Package not found in expected location: /src/dji_metadata_embedder")
        
        # Check for required files
        required_files = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "src/dji_metadata_embedder/__init__.py",
            "src/dji_metadata_embedder/cli.py",
        ]
        
        for file in required_files:
            if not (self.project_root / file).exists():
                self.log_issue(f"Required file missing: {file}")
                
    def check_imports(self):
        """Check if package can be imported."""
        print("\n🔍 Checking imports...")
        
        # Try importing the package
        try:
            import dji_metadata_embedder
            self.log_info(f"Package imported successfully, version: {getattr(dji_metadata_embedder, '__version__', 'unknown')}")
            
            # Check for key components
            components = ['DJIMetadataEmbedder', 'main']
            for component in components:
                if not hasattr(dji_metadata_embedder, component):
                    self.log_warning(f"Component '{component}' not found in package")
                    
        except ImportError as e:
            self.log_issue(f"Cannot import package: {e}")
            
    def check_dependencies(self):
        """Check external dependencies."""
        print("\n🔍 Checking dependencies...")
        
        # Python dependencies
        try:
            import click
            self.log_info("click is installed")
        except ImportError:
            self.log_issue("click is not installed")
            
        try:
            import rich
            self.log_info("rich is installed")
        except ImportError:
            self.log_issue("rich is not installed")
            
        # External tools
        for tool in ['ffmpeg', 'exiftool']:
            result = subprocess.run([tool, '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_info(f"{tool} is available")
            else:
                self.log_warning(f"{tool} is not in PATH")
                
    def check_entry_points(self):
        """Check if CLI entry points work."""
        print("\n🔍 Checking entry points...")
        
        # Check if dji-embed command exists
        result = subprocess.run(['dji-embed', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            self.log_info(f"dji-embed command works: {result.stdout.strip()}")
        else:
            self.log_issue("dji-embed command not found or not working")
            
            # Try python -m approach
            result = subprocess.run([sys.executable, '-m', 'dji_metadata_embedder', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.log_info("Package works with 'python -m dji_metadata_embedder'")
            else:
                self.log_issue("Package doesn't work with python -m either")
                
    def check_tests(self):
        """Check if tests can run."""
        print("\n🔍 Checking tests...")
        
        if not (self.project_root / "tests").exists():
            self.log_issue("Tests directory not found")
            return
            
        # Try running pytest
        result = subprocess.run(['pytest', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            self.log_warning("pytest not installed")
        else:
            # Try running actual tests
            result = subprocess.run(['pytest', '-v', '--tb=short'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_info("All tests passed")
            else:
                self.log_issue(f"Tests failed: {result.stdout}")
                
    def check_git_status(self):
        """Check git repository status."""
        print("\n🔍 Checking git status...")
        
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if result.returncode == 0:
            if result.stdout:
                self.log_warning(f"Uncommitted changes: {len(result.stdout.splitlines())} files")
            else:
                self.log_info("Git working directory is clean")
        else:
            self.log_warning("Not a git repository or git not installed")
            
    def generate_report(self):
        """Generate diagnostic report."""
        print("\n" + "="*60)
        print("DIAGNOSTIC REPORT")
        print("="*60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python: {sys.version}")
        print(f"Platform: {sys.platform}")
        print(f"Working Directory: {self.project_root}")
        
        if self.issues:
            print(f"\n🚨 ISSUES FOUND ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  {issue}")
                
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  {warning}")
                
        if self.info:
            print(f"\nℹ️  INFORMATION ({len(self.info)}):")
            for info in self.info:
                print(f"  {info}")
                
        print("\n" + "="*60)
        
        # Save report to file
        report_file = f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "platform": sys.platform,
            "working_directory": str(self.project_root),
            "issues": self.issues,
            "warnings": self.warnings,
            "info": self.info
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
            
        print(f"\nReport saved to: {report_file}")
        
        # Return exit code based on issues
        return 1 if self.issues else 0


def main():
    """Run all diagnostics."""
    print("🔧 DJI Metadata Embedder Diagnostic Tool")
    print("="*40)
    
    tool = DiagnosticTool()
    
    # Run all checks
    tool.check_project_structure()
    tool.check_imports()
    tool.check_dependencies()
    tool.check_entry_points()
    tool.check_tests()
    tool.check_git_status()
    
    # Generate report
    exit_code = tool.generate_report()
    
    if exit_code == 0:
        print("\n✅ No critical issues found!")
    else:
        print(f"\n❌ Found {len(tool.issues)} critical issues that need fixing.")
        
    return exit_code


if __name__ == "__main__":
    sys.exit(main())