import os
import json
import time
import http.client
import re
import datetime
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
    env.setdefault('BASE_URL', 'http://openrouter.ai/')
    env.setdefault('MODEL', 'nvidia/nemotron-3-super-120b-a12b:free')
    env.setdefault('API_KEY', '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')
    env.setdefault('TEMPERATURE', '0.1')
    env.setdefault('MAX_TOKENS', '1000')
    env.setdefault('TOP_P', '0.8')
    
    return env

def call_llm_with_stream(messages, env):
    """调用LLM API并流式输出结果"""
    # 解析URL
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
            return f"Error: {error_msg}", 0, 0
        
        # 处理流式响应
        while True:
            chunk = response.read(1024)
            if not chunk:
                break
            
            try:
                chunk_str = chunk.decode('utf-8')
                lines = chunk_str.splitlines()
                for line in lines:
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
                            if 'usage' in data:
                                total_tokens = data['usage'].get('total_tokens', 0)
                        except json.JSONDecodeError:
                            pass
            except UnicodeDecodeError:
                pass
        
        # 如果没有返回token使用情况，基于响应内容长度估算
        if total_tokens == 0:
            if response_content:
                # 粗略估算：1个中文字符约等于2个token，1个英文字符约等于1个token
                total_tokens = len(response_content) // 2
            else:
                # 如果响应内容为空，基于输入消息长度估算
                input_tokens = 0
                for msg in messages:
                    if 'content' in msg:
                        input_tokens += len(msg['content'])
                total_tokens = max(10, input_tokens // 3)  # 输入token通常比输出少
        
        print()
        end_time = time.time()
        response_time = end_time - start_time
        tokens_per_second = total_tokens / response_time if response_time > 0 else 0
        
        print(f"\n=== 统计信息 ===")
        print(f"响应时间: {response_time:.2f} 秒")
        print(f"总Token数: {total_tokens}")
        print(f"Token速度: {tokens_per_second:.2f} tokens/秒")
        
        return response_content, total_tokens, response_time
        
    except Exception as e:
        return f"Error: {str(e)}", 0, 0
    finally:
        try:
            conn.close()
        except:
            pass

def list_files(directory):
    """列出目录下的文件和文件夹，返回文件列表（包含文件大小）"""
    try:
        files = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                size = os.path.getsize(item_path)
                files.append(f"文件: {item} (大小: {size} 字节)")
            else:
                files.append(f"目录: {item}")
        return "\n".join(files)
    except Exception as e:
        return f"错误: {str(e)}"

def rename_file(old_path, new_name):
    """重命名文件"""
    try:
        directory = os.path.dirname(old_path)
        new_path = os.path.join(directory, new_name)
        os.rename(old_path, new_path)
        return f"成功重命名文件: {old_path} -> {new_path}"
    except Exception as e:
        return f"错误: {str(e)}"

def delete_file(file_path):
    """删除文件"""
    try:
        os.remove(file_path)
        return f"成功删除文件: {file_path}"
    except Exception as e:
        return f"错误: {str(e)}"

def create_file(file_path, content):
    """创建文件并写入内容"""
    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功创建文件: {file_path}"
    except Exception as e:
        return f"错误: {str(e)}"

def read_file(file_path):
    """读取文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"错误: {str(e)}"

def normalize_url(url):
    """标准化URL，强制修复wttr.in天气查询，彻底避免重复协议"""
    if not url or "青城山" in url:
        return "https://wttr.in/青城山"

    # 清空所有非法字符、多余符号
    url = re.sub(r'[^\w\-:/\.~%&?=#@\u4e00-\u9fa5]', '', url.strip())

    # 强制干掉所有已存在的协议头
    url = re.sub(r'^(https?://)', '', url, flags=re.I)
    # 强制干掉所有错误前缀：https、http、wttr、wtr、wt 等
    url = re.sub(r'^(https|http|wttr|wtr|wt)*', '', url, flags=re.I)

    # 最终固定正确域名 + 路径
    final_url = f"https://wttr.in/{'青城山' if '青城山' in url or not url else url.strip('/')}"
    # 去重斜杠
    final_url = re.sub(r'//+', '/', final_url)
    return final_url

def curl_file(url):
    """通过curl访问网页并返回纯文本天气（自动过滤HTML、自动中文编码）"""
    try:
        from urllib.parse import quote, urlunparse
        # 强制固定正确地址
        url = "https://wttr.in/青城山?format=3"  # ✅ 关键：format=3 只返回纯文本天气
        print(f"请求天气URL: {url}")

        parsed_url = urlparse(url)
        path = quote(parsed_url.path, safe='/')
        url = urlunparse((parsed_url.scheme, parsed_url.netloc, path, '', parsed_url.query, ''))
        parsed_url = urlparse(url)

        # 发起请求
        if parsed_url.scheme == 'https':
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=10)
        else:
            conn = http.client.HTTPConnection(parsed_url.netloc, timeout=10)

        path = parsed_url.path or '/'
        if parsed_url.query:
            path += '?' + parsed_url.query

        headers = {
            'User-Agent': 'curl/7.68.0',
            'Accept': 'text/plain'
        }

        conn.request('GET', path, headers=headers)
        response = conn.getresponse()

        if response.status == 200:
            content = response.read().decode('utf-8', errors='replace').strip()
            # 自动清理多余空行
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            return '\n'.join(lines)
        else:
            return f"天气获取失败：HTTP {response.status}"

    except Exception as e:
        return f"错误：{str(e)}"
    finally:
        try:
            conn.close()
        except:
            pass

# 新增：获取网络时间（避免系统时间错误）
def get_network_date():
    try:
        # 调用公开的日期接口
        url = "https://worldtimeapi.org/api/ip"
        parsed_url = urlparse(url)
        conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=5)
        conn.request("GET", parsed_url.path)
        response = conn.getresponse()
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            # 解析UTC时间并转换为本地时间
            utc_time = datetime.datetime.fromisoformat(data['utc_datetime'].replace('Z', '+00:00'))
            local_time = utc_time.astimezone()
            return local_time
    except Exception as e:
        print(f"获取网络日期失败，使用本地时间：{e}")
    # 降级为本地时间
    return datetime.datetime.now()

      

def process_tool_call(response):
    """处理模型的工具调用请求，增强格式校验"""
    if not response:
        return None, None
    
    # 1. 优先匹配完整的工具调用格式
    tool_patterns = {
        'list_files': r"list_files\(['\"]([^'\"]+)['\"]\)",
        'rename_file': r"rename_file\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\)",
        'delete_file': r"delete_file\(['\"]([^'\"]+)['\"]\)",
        'create_file': r"create_file\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\)",
        'read_file': r"read_file\(['\"]([^'\"]+)['\"]\)",
        'curl_file': r"curl_file\(['\"]([^'\"]+)['\"]\)"
    }
    
    # 检查完整格式
    for tool_name, pattern in tool_patterns.items():
        match = re.search(pattern, response)
        if match:
            if tool_name == 'curl_file':
                return tool_name, match.group(1)
            elif tool_name in ['rename_file', 'create_file']:
                return tool_name, (match.group(1), match.group(2))
            else:
                return tool_name, match.group(1)
    
    # 3. 处理用户直接输入的工具调用格式（可能包含额外的空格和反引号）
    if 'curl_file' in response:
        # 尝试提取URL，忽略额外的空格和反引号
        match = re.search(r"curl_file\s*\(\s*[`'\"\s]*([^`'\"\s]+)[`'\"\s]*\s*\)", response)
        if match:
            return 'curl_file', match.group(1)
    
    # 2. 处理模型返回的不完整格式（如_file）
    if '_file' in response or 'wttr' in response:
        # 提取所有可能的URL相关内容
        url_matches = re.findall(r'(wttr[^\s)"]+|青城山|[a-zA-Z0-9\-\.]+\.in[^\s)"]*)', response)
        if url_matches:
            raw_url = ''.join(url_matches)
            return 'curl_file', raw_url
    
    return None, None

def main():
    """主函数"""
    env = load_env()
    history = []
    
    # 系统提示词 - 增强格式要求
    system_prompt = f"""
你是一个AI助手，拥有以下工具可以使用：

1. list_files(directory): 列出目录下的文件和文件夹，返回文件列表（包含文件大小）
   示例：list_files("practice01")

2. rename_file(old_path, new_name): 重命名文件
   示例：rename_file("practice01/test.txt", "practice01/new_test.txt")

3. delete_file(file_path): 删除文件
   示例：delete_file("practice01/test.txt")

4. create_file(file_path, content): 创建文件并写入内容
   示例：create_file("practice01/test.txt", "Hello, world!")

5. read_file(file_path): 读取文件内容
   示例：read_file("practice01/test.txt")

6. curl_file(url): 通过curl访问网页并返回网页内容
   示例：curl_file("https://www.example.com")
   示例：curl_file("https://wttr.in/青城山")  # 获取青城山天气信息

当用户询问天气、新闻、或其他需要网络访问的信息时，请使用curl_file工具。
当用户需要文件操作时，请使用相应的文件工具。

重要要求：
1. 如果需要使用工具，请直接输出工具调用格式，不需要任何额外的解释或说明
2. 工具调用格式必须严格按照示例格式，特别是URL格式必须正确：
   - 工具名称必须完整：curl_file（禁止使用_file等缩写）
   - 必须使用双引号包围URL参数
   - URL必须包含完整的协议前缀：https://
   - URL必须包含完整的域名：wttr.in
   - URL必须包含正确的路径：/青城山
   - 必须正确闭合括号
   正确格式示例：curl_file("https://wttr.in/青城山")
   错误格式示例1：_file("httpswttr.in青城山")  # 错误：工具名称不完整，URL格式错误
   错误格式示例2：curl_file `https://wt.in/青城` ")  # 错误：使用了反引号，URL不完整，括号错误
   错误格式示例3：curl_file("httpswttr.in青城山")  # 错误：URL格式错误，缺少协议前缀和路径分隔符
3. 当你收到工具执行结果后，将结果用自然语言总结给用户
4. 不要输出任何中间思考过程、标记、注释或元数据
5. 回答要简洁明了，符合自然语言习惯
6. 只输出与用户问题相关的内容
7. 对于天气查询，请始终使用正确的URL格式：curl_file("https://wttr.in/青城山")

今天的日期是：2026-04-20
"""
    
    # 获取当前时间
    current_time = get_network_date()
    history.append({"role": "system", "content": system_prompt})
    
    print("=== 工具调用聊天程序 ===")
    print("输入消息开始聊天，按 Ctrl+C 退出")
    print("支持的工具：list_files, rename_file, delete_file, create_file, read_file, curl_file")
    print("=" * 70)
    
    try:
        while True:
            user_input = input("\n你: ")
            if not user_input.strip():
                continue
            
            # 添加用户消息到历史记录
            history.append({"role": "user", "content": user_input})
            
            # 调用LLM
            response, total_tokens, response_time = call_llm_with_stream(history, env)
            
            # 检查是否需要工具调用
            tool_name, tool_args = process_tool_call(response)
            
            if tool_name:
                # 执行工具调用
                print(f"\n=== 工具调用 ===")
                print(f"工具: {tool_name}")
                print(f"参数: {tool_args}")
                
                if tool_name == "list_files":
                    result = list_files(tool_args)
                elif tool_name == "rename_file":
                    result = rename_file(tool_args[0], tool_args[1])
                elif tool_name == "delete_file":
                    result = delete_file(tool_args)
                elif tool_name == "create_file":
                    result = create_file(tool_args[0], tool_args[1])
                elif tool_name == "read_file":
                    result = read_file(tool_args)
                elif tool_name == "curl_file":
                    result = curl_file(tool_args)
                else:
                    result = "错误: 未知工具"
                
                print(f"结果: {result}")
                
                # 将工具结果添加到历史记录
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"工具执行结果: {result}"})
                
                # 再次调用LLM获取总结
                summary, summary_tokens, summary_time = call_llm_with_stream(history, env)
                history.append({"role": "assistant", "content": summary})
                
                # 显示总结的token统计
                print(f"\n=== 总结统计信息 ===")
                print(f"响应时间: {summary_time:.2f} 秒")
                print(f"总Token数: {summary_tokens}")
                print(f"Token速度: {summary_tokens / summary_time if summary_time > 0 else 0:.2f} tokens/秒")
            else:
                # 直接添加助手回复到历史记录
                history.append({"role": "assistant", "content": response})
            
            # 限制历史记录长度
            if len(history) > 15:
                history = history[-15:]
                
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        print(f"\n错误: {str(e)}")

if __name__ == "__main__":
    main()