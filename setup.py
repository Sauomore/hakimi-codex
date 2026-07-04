"""setup.py - 支持 pip install -e ."""

from setuptools import setup, find_packages

setup(
    name="hakimi-cli",
    version="0.2.0",
    description="现代化 AI 代码助手 CLI 工具",
    author="Hakimi Team",
    packages=find_packages(),
    install_requires=[
        "textual>=0.52.0",
        "rich>=13.0.0",
        "httpx>=0.27.0",
        "toml>=0.10.2",
        "pydantic>=2.0.0",
        "aiohttp>=3.9.0",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "hakimi=codex.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
    ],
)
