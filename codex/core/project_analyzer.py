"""项目分析器 - 自动检测项目类型和结构."""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ProjectInfo:
    """项目信息."""
    path: str
    name: str
    type: str = "unknown"
    language: str = ""
    framework: str = ""
    build_tool: str = ""
    package_manager: str = ""
    test_framework: str = ""
    files_count: int = 0
    key_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    has_git: bool = False
    has_docker: bool = False
    has_tests: bool = False
    has_ci: bool = False


class ProjectAnalyzer:
    """项目分析器."""
    
    # 项目类型检测规则
    PROJECT_TYPES = {
        "python": {
            "files": ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "poetry.lock", "uv.lock"],
            "extensions": [".py"],
            "frameworks": {
                "django": ["manage.py", "settings.py"],
                "flask": ["app.py", "wsgi.py"],
                "fastapi": ["main.py"],
                "pytest": ["pytest.ini", "conftest.py"],
            },
            "build_tools": ["setuptools", "poetry", "pipenv", "uv", "hatch"],
            "test_tools": ["pytest", "unittest", "tox"],
        },
        "node": {
            "files": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"],
            "extensions": [".js", ".ts", ".jsx", ".tsx", ".mjs"],
            "frameworks": {
                "react": ["src/App.jsx", "src/App.tsx", "vite.config.js"],
                "vue": ["src/App.vue", "vue.config.js"],
                "next": ["next.config.js", "next.config.ts"],
                "nuxt": ["nuxt.config.ts", "nuxt.config.js"],
                "express": ["app.js", "server.js"],
                "nest": ["nest-cli.json"],
            },
            "build_tools": ["npm", "yarn", "pnpm", "bun", "vite", "webpack"],
            "test_tools": ["jest", "vitest", "mocha", "cypress", "playwright"],
        },
        "rust": {
            "files": ["Cargo.toml", "Cargo.lock"],
            "extensions": [".rs"],
            "frameworks": {
                "actix-web": ["Cargo.toml"],
                "axum": ["Cargo.toml"],
                "tauri": ["tauri.conf.json"],
            },
            "build_tools": ["cargo"],
            "test_tools": ["cargo test"],
        },
        "go": {
            "files": ["go.mod", "go.sum"],
            "extensions": [".go"],
            "frameworks": {
                "gin": ["go.mod"],
                "echo": ["go.mod"],
                "fiber": ["go.mod"],
            },
            "build_tools": ["go build"],
            "test_tools": ["go test"],
        },
        "java": {
            "files": ["pom.xml", "build.gradle", "gradlew", "settings.gradle"],
            "extensions": [".java", ".kt"],
            "frameworks": {
                "spring": ["pom.xml", "build.gradle"],
                "spring-boot": ["application.properties", "application.yml"],
                "maven": ["pom.xml"],
                "gradle": ["build.gradle"],
            },
            "build_tools": ["maven", "gradle"],
            "test_tools": ["junit", "testng"],
        },
        "docker": {
            "files": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"],
        },
    }
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
    
    def analyze(self) -> ProjectInfo:
        """分析项目."""
        info = ProjectInfo(
            path=str(self.project_path),
            name=self.project_path.name,
            has_git=(self.project_path / ".git").exists(),
        )
        
        # 检测项目类型
        detected_types = self._detect_project_types()
        
        if detected_types:
            primary_type = detected_types[0]
            info.type = primary_type
            
            # 检测框架
            info.framework = self._detect_framework(primary_type)
            
            # 检测构建工具
            info.build_tool = self._detect_build_tool(primary_type)
            
            # 检测测试框架
            info.test_framework = self._detect_test_framework(primary_type)
            
            # 检测包管理器
            info.package_manager = self._detect_package_manager(primary_type)
        
        # 统计文件
        info.files_count = self._count_files()
        
        # 检测关键文件
        info.key_files = self._find_key_files()
        
        # 检测 Docker
        info.has_docker = any(
            (self.project_path / f).exists()
            for f in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
        )
        
        # 检测测试目录
        info.has_tests = any(
            (self.project_path / d).exists()
            for d in ["tests", "test", "__tests__", "spec", "e2e"]
        )
        
        # 检测 CI
        ci_dirs = [".github", ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml", "Jenkinsfile"]
        info.has_ci = any(
            (self.project_path / d).exists() for d in ci_dirs
        ) or (self.project_path / ".github" / "workflows").exists()
        
        # 读取依赖
        info.dependencies = self._get_dependencies(primary_type if detected_types else "")
        
        return info
    
    def _detect_project_types(self) -> List[str]:
        """检测项目类型（按优先级排序）."""
        detected = []
        
        for proj_type, rules in self.PROJECT_TYPES.items():
            if proj_type == "docker":
                continue
                
            score = 0
            # 检查特征文件
            for f in rules.get("files", []):
                if (self.project_path / f).exists():
                    score += 10
            
            # 检查文件扩展名
            for ext in rules.get("extensions", []):
                if list(self.project_path.rglob(f"*{ext}")):
                    score += 5
                    break  # 只要有就加分
            
            if score > 0:
                detected.append((proj_type, score))
        
        # 按分数排序
        detected.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in detected]
    
    def _detect_framework(self, proj_type: str) -> str:
        """检测框架."""
        rules = self.PROJECT_TYPES.get(proj_type, {})
        for framework, files in rules.get("frameworks", {}).items():
            for f in files:
                if (self.project_path / f).exists():
                    return framework
                # 检查内容
                try:
                    path = self.project_path / f.split("/")[0]
                    if path.exists() and path.is_dir():
                        for item in path.iterdir():
                            if item.name.lower() == f.split("/")[-1].lower():
                                return framework
                except:
                    pass
        return ""
    
    def _detect_build_tool(self, proj_type: str) -> str:
        """检测构建工具."""
        if proj_type == "python":
            if (self.project_path / "poetry.lock").exists():
                return "poetry"
            if (self.project_path / "Pipfile").exists():
                return "pipenv"
            if (self.project_path / "uv.lock").exists():
                return "uv"
            if (self.project_path / "pyproject.toml").exists():
                return "setuptools/hatch"
            return "pip"
        
        elif proj_type == "node":
            if (self.project_path / "bun.lockb").exists():
                return "bun"
            if (self.project_path / "pnpm-lock.yaml").exists():
                return "pnpm"
            if (self.project_path / "yarn.lock").exists():
                return "yarn"
            return "npm"
        
        elif proj_type == "rust":
            return "cargo"
        
        elif proj_type == "go":
            return "go"
        
        elif proj_type == "java":
            if (self.project_path / "pom.xml").exists():
                return "maven"
            if (self.project_path / "build.gradle").exists():
                return "gradle"
        
        return ""
    
    def _detect_test_framework(self, proj_type: str) -> str:
        """检测测试框架."""
        if proj_type == "python":
            if (self.project_path / "pytest.ini").exists() or \
               (self.project_path / "pyproject.toml").exists():
                return "pytest"
            return "unittest"
        
        elif proj_type == "node":
            pkg = self.project_path / "package.json"
            if pkg.exists():
                try:
                    import json
                    with open(pkg) as f:
                        data = json.load(f)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if "jest" in deps:
                        return "jest"
                    if "vitest" in deps:
                        return "vitest"
                    if "mocha" in deps:
                        return "mocha"
                except:
                    pass
            return ""
        
        elif proj_type == "rust":
            return "cargo test"
        
        elif proj_type == "go":
            return "go test"
        
        return ""
    
    def _detect_package_manager(self, proj_type: str) -> str:
        """检测包管理器."""
        return self._detect_build_tool(proj_type)
    
    def _count_files(self) -> int:
        """统计文件数（忽略常见目录）."""
        count = 0
        ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "target"}
        
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            count += len(files)
            if count > 10000:  # 限制计数
                return count
        
        return count
    
    def _find_key_files(self) -> List[str]:
        """查找关键文件."""
        key_files = []
        candidates = [
            "README.md", "README.rst", "README",
            "LICENSE", "LICENSE.md", "LICENSE.txt",
            "Dockerfile", "docker-compose.yml",
            ".env.example", ".env.template",
            "Makefile", "makefile",
            "CONTRIBUTING.md", "CHANGELOG.md",
        ]
        
        for f in candidates:
            if (self.project_path / f).exists():
                key_files.append(f)
        
        return key_files[:10]
    
    def _get_dependencies(self, proj_type: str) -> List[str]:
        """获取依赖列表."""
        deps = []
        
        if proj_type == "python":
            req_file = self.project_path / "requirements.txt"
            if req_file.exists():
                try:
                    with open(req_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                deps.append(line.split("==")[0].split(">=")[0].strip())
                except:
                    pass
            
            pyproject = self.project_path / "pyproject.toml"
            if pyproject.exists():
                try:
                    import tomllib
                    with open(pyproject, "rb") as f:
                        data = tomllib.load(f)
                    deps.extend(data.get("project", {}).get("dependencies", []))
                except:
                    pass
        
        elif proj_type == "node":
            pkg = self.project_path / "package.json"
            if pkg.exists():
                try:
                    with open(pkg) as f:
                        data = json.load(f)
                    deps.extend(data.get("dependencies", {}).keys())
                    deps.extend(data.get("devDependencies", {}).keys())
                except:
                    pass
        
        return deps[:20]
    
    def get_summary(self) -> str:
        """获取项目摘要文本."""
        info = self.analyze()
        
        lines = [
            f"[目录] 项目: {info.name}",
            f"[路径] 路径: {info.path}",
            f"[类型] 类型: {info.type or '未知'}",
        ]
        
        if info.language:
            lines.append(f"[语言] 语言: {info.language}")
        if info.framework:
            lines.append(f"[框架] 框架: {info.framework}")
        if info.build_tool:
            lines.append(f"[构建工具] 构建工具: {info.build_tool}")
        if info.test_framework:
            lines.append(f"[测试工具] 测试工具: {info.test_framework}")
        
        lines.extend([
            f"[文件数] 文件数: {info.files_count}",
            f"[Git] Git: {'[启用]' if info.has_git else '[禁用]'}",
            f"[Docker] Docker: {'[启用]' if info.has_docker else '[禁用]'}",
            f"[测试] 测试: {'[启用]' if info.has_tests else '[禁用]'}",
            f"[CI/CD] CI/CD: {'[启用]' if info.has_ci else '[禁用]'}",
        ])
        
        if info.key_files:
            lines.append(f"[文件] 关键文件: {', '.join(info.key_files[:5])}")
        
        if info.dependencies:
            lines.append(f"[依赖] 依赖: {', '.join(info.dependencies[:5])}")
        
        return "\n".join(lines)
    
    def get_system_context(self) -> str:
        """获取用于 AI 系统提示的项目上下文."""
        info = self.analyze()
        
        context = f"""项目信息:
- 名称: {info.name}
- 类型: {info.type}
- 路径: {info.path}
- 文件数: {info.files_count}
"""
        
        if info.framework:
            context += f"- 框架: {info.framework}\n"
        if info.build_tool:
            context += f"- 构建工具: {info.build_tool}\n"
        if info.test_framework:
            context += f"- 测试: {info.test_framework}\n"
        if info.has_git:
            context += "- Git: 已启用\n"
        if info.has_docker:
            context += "- Docker: 已配置\n"
        
        # 添加运行建议
        if info.type == "python":
            context += "\n运行建议:\n- 运行: python -m pytest (测试)\n- 运行: python -m pip install -e . (安装)\n"
        elif info.type == "node":
            context += f"\n运行建议:\n- 运行: {info.package_manager} install (安装依赖)\n- 运行: {info.package_manager} test (测试)\n- 运行: {info.package_manager} run build (构建)\n"
        elif info.type == "rust":
            context += "\n运行建议:\n- 运行: cargo build (构建)\n- 运行: cargo test (测试)\n"
        elif info.type == "go":
            context += "\n运行建议:\n- 运行: go build (构建)\n- 运行: go test ./... (测试)\n"
        
        return context
