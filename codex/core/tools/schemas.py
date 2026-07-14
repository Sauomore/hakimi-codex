"""工具 JSON Schema 定义."""


def get_tools_description() -> list:
    """获取所有可用工具的 JSON Schema 描述（用于 AI 工具调用）."""
    return [
        {
            "name": "execute_command",
            "description": "执行 shell 命令，获取命令输出。使用此工具来运行测试、构建项目、安装依赖等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "执行命令的工作目录（相对项目根目录）"
                    }
                },
                "required": ["command"]
            }
        },
        {
            "name": "read_file",
            "description": "读取文件内容。使用此工具来查看代码、配置文件、日志等。大文件建议先用 list_directory 查看大小，再用 limit 参数读取片段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径（相对项目根目录或绝对路径）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多读取的字符数，0 表示读取全部（受 1MB 限制）"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "write_file",
            "description": "写入或覆盖文件内容。使用此工具来创建新文件或修改现有文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径（相对项目根目录）"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文件内容"
                    }
                },
                "required": ["file_path", "content"]
            }
        },
        {
            "name": "list_directory",
            "description": "列出目录内容。使用此工具来查看项目结构、列出文件等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "目录路径（相对项目根目录，默认当前目录）"
                    }
                }
            }
        },
        {
            "name": "search_files",
            "description": "在文件中搜索文本内容。使用此工具来查找代码片段、变量定义等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "要搜索的文本内容"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索路径（相对项目根目录，默认项目根目录）"
                    }
                },
                "required": ["pattern"]
            }
        },
        {
            "name": "execute_code",
            "description": "执行 Python 代码片段并返回结果。用于快速计算、数据处理、算法验证等。沙箱环境，部分系统模块受限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python 代码字符串"
                    }
                },
                "required": ["code"]
            }
        },
        {
            "name": "analyze_project",
            "description": "分析当前项目结构，检测项目类型、框架、依赖等。用于了解项目概况。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "web_search",
            "description": "使用搜索引擎搜索网络信息。用于获取最新文档、技术资料、错误解决方案等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量（默认 5）"
                    }
                },
                "required": ["query"]
            }
        }
    ]
