"""
Setup file for AI Lead-Lag Scalper
"""

from setuptools import setup, find_packages

setup(
    name="ai_lead_scalper",
    version="1.0.0",
    description="AI-powered lead-lag scalper for Polymarket",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        line.strip()
        for line in open("requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
)
