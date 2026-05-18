import os
import json
import time
import http.client
from urllib.parse import urlparse

def load_env():
    """加载环境变量"""
    env = {}
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env[key.strip()] = value.strip().strip('"')
    
    # 默认值
    env.setdefault('BASE_URL', 'http://localhost:1234/v1')
    env.setdefault('MODEL', 'qwen/qwen3.5-9b')
    env.setdefault('API_KEY', '')
    env.setdefault('TEMPERATURE', '0.1')
    env.setdefault('MAX_TOKENS', '1000')
    env.setdefault('TOP_P', '0.8')
    env.setdefault('ANYTHINGLLM_API_KEY', '')
    env.setdefault('ANYTHINGLLM_WORKSPACE_SLUG', '')
    
    return env

def call_llm_with_stream(messages, env):
    """调用 LLM API 并流式输出结果"""
    # 解析 URL
    url = urlparse(env['BASE_URL'])
    if url.scheme == 'https':
        conn = http.client.HTTPSConnection(url.netloc, timeout=30)
    else:
        conn = http.client.HTTPConnection(url.netloc, timeout=30)
    
    # 设置请求头
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    }
    if env['API_KEY']:
        headers['Authorization'] = f'Bearer {env["API_KEY"]}'
    
    # 构建请求数据
    data = {
        'model': env['MODEL'],
        'messages': messages,
        'temperature': float(env['TEMPERATURE']),
        'max_tokens': int(env['MAX_TOKENS']),
        'top_p': float(env['TOP_P']),
        'stream': True
    }
    
    # 记录开始时间
    start_time = time.time()
    response_content = ''
    total_tokens = 0
    
    try:
        # 发送请求
        conn.request('POST', url.path + '/chat/completions', json.dumps(data), headers)
        response = conn.getresponse()
        
        if response.status != 200:
            error_data = response.read().decode('utf-8')
            try:
                error_data = json.loads(error_data)
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            except:
                error_msg = error_data
            print(f"\n错误：HTTP {response.status} - {error_msg}")
            return f"Error: {error_msg}", 0, 0
        
        # 处理流式响应
        print("助手：", end='', flush=True)
        buffer = ""
        
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            
            buffer += chunk.decode('utf-8', errors='replace')
            
            # 处理缓冲区中的完整行
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                
                # 跳过 OpenRouter 处理消息
                if line.startswith(':') and 'OPENROUTER PROCESSING' in line:
                    continue
                
                if line.startswith('data: '):
                    chunk_data = line[6:]
                    if chunk_data == '[DONE]':
                        continue
                    try:
                        data = json.loads(chunk_data)
                        if 'choices' in data:
                            choice = data['choices'][0]
                            if 'delta' in choice:
                                delta = choice['delta']
                                if 'content' in delta:
                                    content = delta['content']
                                    print(content, end='', flush=True)
                                    response_content += content
                                elif 'reasoning_content' in delta:
                                    content = delta['reasoning_content']
                                    print(content, end='', flush=True)
                                    response_content += content
                        if 'usage' in data:
                            total_tokens = data['usage'].get('total_tokens', 0)
                    except json.JSONDecodeError:
                        pass
        
        if not response_content:
            print("(无响应内容)")
        
        # 如果没有返回 token 使用情况，基于响应内容长度估算
        if total_tokens == 0:
            if response_content:
                # 粗略估算：1 个中文字符约等于 2 个 token，1 个英文字符约等于 1 个 token
                total_tokens = len(response_content) // 2
            else:
                # 如果响应内容为空，基于输入消息长度估算
                input_tokens = 0
                for msg in messages:
                    if 'content' in msg:
                        input_tokens += len(msg['content'])
                total_tokens = max(10, input_tokens // 3)  # 输入 token 通常比输出少
        
        if not response_content:
            print("(无响应内容)")
        
        print()
        end_time = time.time()
        response_time = end_time - start_time
        tokens_per_second = total_tokens / response_time if response_time > 0 else 0
        
        print(f"\n=== 统计信息 ===")
        print(f"响应时间：{response_time:.2f} 秒")
        print(f"总 Token 数：{total_tokens}")
        print(f"Token 速度：{tokens_per_second:.2f} tokens/秒")
        
        return response_content, total_tokens, response_time
        
    except Exception as e:
        return f"Error: {str(e)}", 0, 0
    finally:
        try:
            conn.close()
        except:
            pass

def anythingllm_query(message, env):
    """获取文档仓库中的文档数量和列表（使用聊天接口）"""
    try:
        import subprocess
        import platform
        
        api_key = env.get('ANYTHINGLLM_API_KEY', '')
        workspace_slug = env.get('ANYTHINGLLM_WORKSPACE_SLUG', 'default')
        # 从环境获取 base_url，没有则用默认
        base_url = env.get('ANYTHINGLLM_BASE_URL', 'http://localhost:3001')
        
        if not api_key:
            return "错误：未设置 ANYTHINGLLM_API_KEY"
        if not workspace_slug:
            return "错误：未设置 ANYTHINGLLM_WORKSPACE_SLUG"
        
        # 使用聊天接口来获取文档信息
        url = f"{base_url}/api/v1/workspace/{workspace_slug}/chat"
        
        # 构建请求数据
        data = {
            "message": message
        }
        
        if platform.system() == 'Windows':
            # 使用 PowerShell 的 Invoke-WebRequest，只输出 Content 字段
            # 使用更好的方法来构建命令，避免引号问题
            json_body = json.dumps(data, ensure_ascii=False)
            ps_command = f'''
            $headers = @{{
                "Authorization" = "Bearer {api_key}"
                "Content-Type" = "application/json"
            }}
            $body = @'
{json_body}
'@
            $response = Invoke-WebRequest -Uri "{url}" -Method POST -Headers $headers -Body $body -UseBasicParsing
            $response.Content
            '''
            result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, timeout=30)
        else:
            curl_command = [
                "curl", "-s", "-X", "POST",
                "-H", f"Authorization: Bearer {api_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(data, ensure_ascii=False),
                url
            ]
            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30, encoding='utf-8')
        
        if result.returncode != 0:
            return f"调用失败：{result.stderr}"
        
        # 解析响应
        try:
            response_data = json.loads(result.stdout)
            if "textResponse" in response_data:
                return response_data["textResponse"]
            elif "message" in response_data:
                return response_data["message"]
            else:
                return f"响应：{result.stdout}"
        except json.JSONDecodeError as e:
            return f"无法解析响应：{result.stdout[:500]}"
    except subprocess.TimeoutExpired:
        return "错误：请求超时，请检查网络连接或 AnythingLLM 服务是否正常运行"
    except Exception as e:
        return f"异常：{str(e)}"

def process_tool_call(response):
    """处理模型的工具调用请求"""
    import re
    if "anythingllm_query" in response:
        match = re.search(r"anythingllm_query\(['\"]([^'\"]+)['\"]\)", response)
        if match:
            message = match.group(1)
            return "anythingllm_query", message
    return None, None

def main():
    """主函数"""
    env = load_env()
    history = []
    
    # 系统提示词
    system_prompt = """
你是一个 AI 助手，拥有以下工具可以使用：

1. anythingllm_query(message): 使用 subprocess 模块调用 curl 命令访问 AnythingLLM 的聊天 API 接口
   示例：anythingllm_query("你好，AnythingLLM")

当用户提到"文档仓库"、"文件仓库"、"仓库"时，必须使用 anythingllm_query 工具。

重要要求：
1. 如果需要使用工具，请直接输出工具调用格式，不需要任何额外的解释或说明
2. 工具调用格式必须严格按照示例格式，特别是 URL 格式必须正确：
   - 工具名称必须完整
   - 必须使用双引号包围参数
   - 必须正确闭合括号
3. 当你收到工具执行结果后，将结果用自然语言总结给用户
4. 不要输出任何中间思考过程、标记、注释或元数据
5. 回答要简洁明了，符合自然语言习惯
6. 只输出与用户问题相关的内容
"""
    
    history.append({"role": "system", "content": system_prompt})
    
    print("=== 交互式聊天程序 ===")
    print("输入消息开始聊天，按 Ctrl+C 退出")
    print("支持的工具：anythingllm_query")
    print("当提到'文档仓库'、'文件仓库'、'仓库'时会触发 anythingllm_query 工具")
    print("=" * 70)
    
    try:
        while True:
            user_input = input("\n你：")
            if not user_input.strip():
                continue
            
            # 检查是否包含文档仓库相关关键词
            doc_keywords = ["文档仓库", "文件仓库", "仓库", "文档"]
            if any(keyword in user_input for keyword in doc_keywords):
                # 直接调用 anythingllm_query 工具，使用英文查询
                print(f"\n=== 工具调用 ===")
                print(f"工具：anythingllm_query")
                print(f"参数：{user_input}")
                
                # 使用英文查询来获取文档列表
                result = anythingllm_query("List all documents in the document repository", env)
                print(f"结果：{result}")
                print(f"助手：{result}")
                
                # 将结果添加到历史记录
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": result})
                continue
            
            # 添加用户消息到历史记录
            history.append({"role": "user", "content": user_input})
            
            # 调用 LLM
            response, total_tokens, response_time = call_llm_with_stream(history, env)
            
            # 检查是否需要工具调用
            tool_name, tool_args = process_tool_call(response)
            
            if tool_name:
                # 执行工具调用
                print(f"\n=== 工具调用 ===")
                print(f"工具：{tool_name}")
                print(f"参数：{tool_args}")
                
                if tool_name == "anythingllm_query":
                    # 检查参数是否包含文档仓库相关关键词
                    doc_keywords = ["文档仓库", "文件仓库", "仓库", "文档"]
                    if any(keyword in tool_args for keyword in doc_keywords):
                        # 使用英文查询来获取文档列表
                        result = anythingllm_query("List all documents in the document repository", env)
                    else:
                        # 使用原始参数
                        result = anythingllm_query(tool_args, env)
                else:
                    result = "错误：未知工具"
                
                print(f"结果：{result}")
                
                # 将工具结果添加到历史记录
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"工具执行结果：{result}"})
                
                # 再次调用 LLM 获取总结
                summary, summary_tokens, summary_time = call_llm_with_stream(history, env)
                history.append({"role": "assistant", "content": summary})
                
                # 显示总结的 token 统计
                print(f"\n=== 总结统计信息 ===")
                print(f"响应时间：{summary_time:.2f} 秒")
                print(f"总 Token 数：{summary_tokens}")
                print(f"Token 速度：{summary_tokens / summary_time if summary_time > 0 else 0:.2f} tokens/秒")
            else:
                # 直接添加助手回复到历史记录
                history.append({"role": "assistant", "content": response})
            
            # 限制历史记录长度，避免 token 超限
            if len(history) > 10:
                history = history[-10:]
                
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        print(f"\n错误：{str(e)}")

if __name__ == "__main__":
    main()
