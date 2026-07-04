"""LLM API 客户端."""

import json
import asyncio
from typing import AsyncIterator, Optional, Dict, Any, List

import httpx

from .models import ModelConfig, ProviderType


class LLMClient:
    """通用 LLM API 客户端."""
    
    def __init__(self, model: ModelConfig):
        self.model = model
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            headers=self._get_headers()
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头."""
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.model.api_key:
            if self.model.provider == ProviderType.ANTHROPIC:
                headers["x-api-key"] = self.model.api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self.model.api_key}"
        
        return headers
    
    def _get_base_url(self) -> str:
        """获取 API 基础 URL."""
        if self.model.api_base:
            return self.model.api_base.rstrip("/")
        
        defaults = {
            ProviderType.OPENAI: "https://api.openai.com/v1",
            ProviderType.ANTHROPIC: "https://api.anthropic.com/v1",
            ProviderType.GOOGLE: "https://generativelanguage.googleapis.com/v1beta",
            ProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
            ProviderType.MISTRAL: "https://api.mistral.ai/v1",
            ProviderType.OLLAMA: "http://localhost:11434/v1",
            ProviderType.OPENROUTER: "https://openrouter.ai/api/v1",
        }
        
        return defaults.get(self.model.provider, "https://api.openai.com/v1")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """发送聊天请求."""
        
        if self.model.provider == ProviderType.ANTHROPIC:
            async for chunk in self._chat_anthropic(messages, system_prompt, stream):
                yield chunk
        elif self.model.provider == ProviderType.GOOGLE:
            async for chunk in self._chat_google(messages, system_prompt, stream):
                yield chunk
        else:
            # OpenAI 兼容格式
            async for chunk in self._chat_openai_compatible(messages, system_prompt, stream):
                yield chunk
    
    async def _chat_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        stream: bool
    ) -> AsyncIterator[str]:
        """OpenAI 兼容 API 调用."""
        
        url = f"{self._get_base_url()}/chat/completions"
        
        payload = {
            "model": self.model.model_id,
            "messages": messages,
            "temperature": self.model.temperature,
            "max_tokens": self.model.max_tokens,
            "stream": stream,
        }
        
        if system_prompt and messages[0].get("role") != "system":
            payload["messages"] = [{"role": "system", "content": system_prompt}] + messages
        
        try:
            if stream:
                async with self.client.stream("POST", url, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
            else:
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                yield content
                
        except httpx.HTTPStatusError as e:
            yield f"\n[错误] API 请求失败: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            yield f"\n[错误] 请求异常: {str(e)}"
    
    async def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        stream: bool
    ) -> AsyncIterator[str]:
        """Anthropic API 调用."""
        
        url = f"{self._get_base_url()}/messages"
        
        # 转换消息格式
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                continue
            anthropic_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        payload = {
            "model": self.model.model_id,
            "messages": anthropic_messages,
            "max_tokens": self.model.max_tokens,
            "stream": stream,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            if stream:
                async with self.client.stream("POST", url, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                chunk = json.loads(data)
                                if chunk.get("type") == "content_block_delta":
                                    content = chunk.get("delta", {}).get("text", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            else:
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("content", [{}])[0].get("text", "")
                yield content
                
        except httpx.HTTPStatusError as e:
            yield f"\n[错误] API 请求失败: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            yield f"\n[错误] 请求异常: {str(e)}"
    
    async def _chat_google(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        stream: bool
    ) -> AsyncIterator[str]:
        """Google Gemini API 调用."""
        
        # 构建内容
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                continue
            # Google 使用 model/user 角色
            google_role = "model" if role == "assistant" else "user"
            contents.append({
                "role": google_role,
                "parts": [{"text": msg["content"]}]
            })
        
        url = f"{self._get_base_url()}/models/{self.model.model_id}:streamGenerateContent"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.model.temperature,
                "maxOutputTokens": self.model.max_tokens,
            }
        }
        
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        
        try:
            async with self.client.stream("POST", url, json=payload, params={"key": self.model.api_key or ""}) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            candidates = chunk.get("candidates", [{}])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    text = part.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.HTTPStatusError as e:
            yield f"\n[错误] API 请求失败: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            yield f"\n[错误] 请求异常: {str(e)}"
    
    async def close(self):
        """关闭客户端."""
        await self.client.aclose()
