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
                                    # 不显示模型思考内容
                                    # elif 'reasoning_content' in delta:
                                    #     content = delta['reasoning_content']
                                    #     print(content, end='', flush=True)
                                    #     response_content += content
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

def curl_file(url):
    """通过curl访问网页并返回网页内容"""
    try:
        # 清理URL，移除可能的错误字符
        url = url.strip()
        # 修复URL格式，确保包含协议前缀
        if not url.startswith('http://') and not url.startswith('https://'):
            # 尝试添加https前缀
            url = 'https://' + url.lstrip(':')
        # 修复常见的域名错误
        if 'wttr/' in url:
            url = url.replace('wttr/', 'wttr.in/')
        elif 'tr.in/' in url:
            url = url.replace('tr.in/', 'wttr.in/')
        
        parsed_url = urlparse(url)
        if parsed_url.scheme == 'https':
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=10)
        else:
            conn = http.client.HTTPConnection(parsed_url.netloc, timeout=10)
        
        path = parsed_url.path or '/'
        if parsed_url.query:
            path += '?' + parsed_url.query
        
        # 添加User-Agent头，避免被某些网站拒绝
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        conn.request('GET', path, headers=headers)
        response = conn.getresponse()
        
        if response.status == 200:
            content = response.read().decode('utf-8', errors='replace')
            # 限制返回内容长度，避免token超限
            if len(content) > 2000:
                content = content[:2000] + '\n...（内容过长，已截断）'
            return content
        else:
            return f"错误: HTTP {response.status} - {response.reason}"
    except Exception as e:
        return f"错误: {str(e)}"
    finally:
        try:
            conn.close()
        except:
            pass

def process_tool_call(response):
    """处理模型的工具调用请求"""
    import re
    # 不依赖特定关键词，直接搜索工具调用格式
    if "list_files" in response:
        match = re.search(r"list_files\(['\"]([^'\"]+)['\"]\)", response)
        if match:
            directory = match.group(1)
            return "list_files", directory
    elif "rename_file" in response:
        match = re.search(r"rename_file\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\)", response)
        if match:
            old_path = match.group(1)
            new_name = match.group(2)
            return "rename_file", (old_path, new_name)
    elif "delete_file" in response:
        match = re.search(r"delete_file\(['\"]([^'\"]+)['\"]\)", response)
        if match:
            file_path = match.group(1)
            return "delete_file", file_path
    elif "create_file" in response:
        match = re.search(r"create_file\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\)", response)
        if match:
            file_path = match.group(1)
            content = match.group(2)
            return "create_file", (file_path, content)
    elif "read_file" in response:
        match = re.search(r"read_file\(['\"]([^'\"]+)['\"]\)", response)
        if match:
            file_path = match.group(1)
            return "read_file", file_path
    elif "curl_file" in response or "_file" in response:
        # 处理完整的curl_file和不完整的_file
        # 支持多种引号格式：单引号、双引号、反引号
        match = re.search(r"(?:curl_)?_file\s*[`'\"]([^`'\"]+)[`'\"]\s*\)?", response)
        if match:
            url = match.group(1)
            # 修复URL格式
            url = url.strip()
            # 修复协议前缀
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url.lstrip(':')
            # 修复域名
            if 'wt' in url and 'wttr.in' not in url:
                if 'wt.in' in url:
                    url = url.replace('wt.in', 'wttr.in')
                elif 'wtr.in' in url:
                    url = url.replace('wtr.in', 'wttr.in')
                elif 'wttr' in url:
                    url = url.replace('wttr', 'wttr.in')
                elif 'httpswttr' in url:
                    url = url.replace('httpswttr', 'https://wttr')
            # 修复路径
            if 'wttr.in' in url:
                if '青城山' not in url:
                    url += '/青城山'
                elif '/青城山' not in url:
                    url = url.replace('青城山', '/青城山')
            return "curl_file", url
    return None, None

def get_chat_context_length(history):
    """计算聊天上下文的长度"""
    length = 0
    for msg in history:
        if 'content' in msg:
            length += len(msg['content'])
    return length

def summarize_chat_history(history, env):
    """总结聊天记录"""
    # 提取除系统消息外的所有消息
    non_system_messages = [msg for msg in history if msg['role'] != 'system']
    
    # 计算分割点
    split_point = int(len(non_system_messages) * 0.7)
    
    # 前70%的消息需要总结
    messages_to_summarize = non_system_messages[:split_point]
    # 后30%的消息保留原文
    messages_to_keep = non_system_messages[split_point:]
    
    # 构建总结请求
    summary_prompt = f"请总结以下聊天记录，保持关键信息：\n\n"
    for msg in messages_to_summarize:
        role = "用户" if msg['role'] == 'user' else "助手"
        summary_prompt += f"{role}: {msg['content']}\n"
    
    summary_messages = [
        {"role": "system", "content": "你是一个聊天记录总结助手，请简洁地总结聊天内容，保留关键信息和对话主题。"},
        {"role": "user", "content": summary_prompt}
    ]
    
    print("\n=== 正在总结聊天记录 ===")
    summary, _, _ = call_llm_with_stream(summary_messages, env)
    print("=== 总结完成 ===")
    
    # 构建新的历史记录
    new_history = []
    
    # 添加系统消息
    for msg in history:
        if msg['role'] == 'system':
            new_history.append(msg)
            break
    
    # 添加总结消息
    new_history.append({"role": "assistant", "content": f"【聊天记录总结】{summary}"})
    
    # 添加保留的消息
    new_history.extend(messages_to_keep)
    
    return new_history

def main():
    """主函数"""
    env = load_env()
    history = []
    chat_rounds = 0
    
    # 系统提示词
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
   - 工具名称必须完整：curl_file
   - 必须使用双引号包围URL参数
   - URL必须包含完整的协议前缀：https://
   - URL必须包含完整的域名：wttr.in
   - URL必须包含正确的路径：/青城山
   - 必须正确闭合括号
   正确格式示例：curl_file("https://wttr.in/青城山")
   错误格式示例：_file("httpswttr.in青城山")  # 错误：工具名称不完整，URL格式错误
3. 当你收到工具执行结果后，将结果用自然语言总结给用户
4. 不要输出任何中间思考过程、标记、注释或元数据
5. 回答要简洁明了，符合自然语言习惯
6. 只输出与用户问题相关的内容

今天的日期是：2026-04-15
"""
    
    history.append({"role": "system", "content": system_prompt})
    
    print("=== 聊天记录总结程序 ===")
    print("输入消息开始聊天，按 Ctrl+C 退出")
    print("支持的工具：list_files, rename_file, delete_file, create_file, read_file, curl_file")
    print("当聊天超过5轮或上下文超过3k时，会自动总结聊天记录")
    print("=" * 70)
    
    try:
        while True:
            user_input = input("\n你: ")
            if not user_input.strip():
                continue
            
            # 添加用户消息到历史记录
            history.append({"role": "user", "content": user_input})
            chat_rounds += 1
            
            # 检查是否需要总结聊天记录
            context_length = get_chat_context_length(history)
            if chat_rounds > 5 or context_length > 3000:
                history = summarize_chat_history(history, env)
                chat_rounds = len([msg for msg in history if msg['role'] == 'user'])  # 重置聊天轮数
            
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
            
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        print(f"\n错误: {str(e)}")

if __name__ == "__main__":
    main()