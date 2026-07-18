"""LLM API 客户端."""

import json
import asyncio
from typing import AsyncIterator, Optional, Dict, Any, List

import httpx

from .models import ModelConfig, ProviderType
from ..utils.logger import debug as log_debug


class LLMClient:
    """通用 LLM API 客户端."""
    
    def __init__(self, model: ModelConfig, think_mode: bool = True):
        self.model = model
        self.think_mode = think_mode
        self.last_finish_reason: Optional[str] = None
        self.last_usage: Dict[str, int] = {}
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
            ProviderType.KIMI: "https://api.moonshot.cn/v1",
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
        
        # Kimi K2.x 系列对采样参数有严格限制，需要特殊处理
        model_id_lower = self.model.model_id.lower()
        is_kimi_k2 = (
            self.model.provider == ProviderType.KIMI
            and model_id_lower.startswith("kimi-k2")
        )
        # K2.7 Code 思考模式强制开启，无法关闭
        is_kimi_k2_7 = is_kimi_k2 and "k2.7" in model_id_lower

        payload = {
            "model": self.model.model_id,
            "messages": messages,
            "max_tokens": self.model.max_tokens,
            "stream": stream,
        }

        if is_kimi_k2:
            # K2.x 固定采样参数，传其他值会报错；通过 thinking 参数控制思考开关
            if is_kimi_k2_7:
                payload["thinking"] = {"type": "enabled"}
            else:
                payload["thinking"] = {"type": "enabled" if self.think_mode else "disabled"}
        else:
            payload["temperature"] = self.model.temperature

        if system_prompt and messages and messages[0].get("role") != "system":
            payload["messages"] = [{"role": "system", "content": system_prompt}] + messages

        log_debug(f"POST {url}")
        log_debug(f"payload: {json.dumps(payload, ensure_ascii=False)}")

        try:
            if stream:
                async with self.client.stream("POST", url, json=payload) as response:
                    log_debug(f"response status: {response.status_code}")
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        log_debug(f"raw line: {line[:500]}")
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                usage = chunk.get("usage")
                                if usage:
                                    self.last_usage = usage
                                    log_debug(f"usage: {usage}")
                                choice = chunk.get("choices", [{}])[0]
                                finish_reason = choice.get("finish_reason")
                                if finish_reason:
                                    self.last_finish_reason = finish_reason
                                    log_debug(f"finish_reason: {finish_reason}")
                                delta = choice.get("delta", {})
                                reasoning = delta.get("reasoning_content", "")
                                content = delta.get("content", "")
                                # 将思考内容包装成标签，便于上层统一提取
                                if reasoning:
                                    log_debug(f"reasoning chunk: {reasoning[:200]}")
                                    yield f"<thinking>{reasoning}</thinking>"
                                if content:
                                    log_debug(f"content chunk: {content[:200]}")
                                    yield content
                            except json.JSONDecodeError:
                                continue
            else:
                response = await self.client.post(url, json=payload)
                log_debug(f"response status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                log_debug(f"response body: {json.dumps(data, ensure_ascii=False)[:1000]}")
                usage = data.get("usage")
                if usage:
                    self.last_usage = usage
                    log_debug(f"usage: {usage}")
                choice = data.get("choices", [{}])[0]
                self.last_finish_reason = choice.get("finish_reason")
                if self.last_finish_reason:
                    log_debug(f"finish_reason: {self.last_finish_reason}")
                message = choice.get("message", {})
                reasoning = message.get("reasoning_content", "")
                content = message.get("content", "")
                if reasoning:
                    yield f"<thinking>{reasoning}</thinking>"
                if content:
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
                                usage = chunk.get("usage")
                                if usage:
                                    self.last_usage = usage
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
                usage = data.get("usage")
                if usage:
                    self.last_usage = usage
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
