import os
import json
import time
import http.client
from urllib.parse import urlparse

# 读取.env文件
def load_env():
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if not os.path.exists(env_file):
        print("Error: .env file not found. Please copy env.example to .env and fill in the parameters.")
        return None
    
    env_vars = {}
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"')
    
    return env_vars

# 调用LLM API
def call_llm(env_vars, prompt):
    base_url = env_vars.get('BASE_URL', 'http://localhost:1234/v1')
    model = env_vars.get('MODEL', 'your-model-name-here')
    api_key = env_vars.get('API_KEY', '')
    temperature = float(env_vars.get('TEMPERATURE', '0.7'))
    max_tokens = int(env_vars.get('MAX_TOKENS', '1000'))
    top_p = float(env_vars.get('TOP_P', '0.9'))
    
    # 解析URL
    parsed_url = urlparse(base_url)
    host = parsed_url.netloc
    path = parsed_url.path or '/v1'
    if not path.endswith('/'):
        path += '/'
    path += 'chat/completions'
    
    # 构建请求体
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p
    }
    
    # 构建请求头
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # 记录开始时间
    start_time = time.time()
    
    try:
        # 创建连接
        if parsed_url.scheme == 'https':
            conn = http.client.HTTPSConnection(host)
        else:
            conn = http.client.HTTPConnection(host)
        
        # 发送请求
        conn.request("POST", path, json.dumps(payload), headers)
        
        # 获取响应
        response = conn.getresponse()
        response_data = response.read().decode('utf-8')
        conn.close()
        
        # 计算响应时间
        end_time = time.time()
        response_time = end_time - start_time
        
        # 解析响应
        data = json.loads(response_data)
        
        if 'error' in data:
            print(f"Error: {data['error']}")
            return None, response_time, 0, 0
        
        # 提取token使用情况
        usage = data.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)
        
        # 如果没有返回token使用情况，基于响应内容长度估算
        if total_tokens == 0:
            # 提取回复内容用于估算
            response_content = ""
            if 'choices' in data and data['choices']:
                choice = data['choices'][0]
                if 'message' in choice:
                    response_content = choice['message'].get('content', '')
                    if not response_content and 'reasoning_content' in choice['message']:
                        response_content = choice['message']['reasoning_content']
            
            if response_content:
                # 粗略估算：1个中文字符约等于2个token，1个英文字符约等于1个token
                total_tokens = len(response_content) // 2
            else:
                # 如果响应内容为空，基于输入prompt长度估算
                total_tokens = max(10, len(prompt) // 3)
        
        # 计算token速度
        if response_time > 0:
            tokens_per_second = total_tokens / response_time
        else:
            tokens_per_second = 0
        
        # 提取回复内容
        try:
            if 'choices' in data and data['choices']:
                choice = data['choices'][0]
                if 'message' in choice:
                    message = choice['message'].get('content', '')
                    # 检查LMStudio特有的reasoning_content字段
                    if not message and 'reasoning_content' in choice['message']:
                        message = choice['message']['reasoning_content']
                else:
                    message = str(choice)
            else:
                message = str(data)
        except Exception as e:
            print(f"Error extracting message: {str(e)}")
            message = str(data)
        
        return message, response_time, total_tokens, tokens_per_second
        
    except Exception as e:
        print(f"Error calling LLM: {str(e)}")
        end_time = time.time()
        response_time = end_time - start_time
        return None, response_time, 0, 0

# 主函数
def main():
    # 加载环境变量
    env_vars = load_env()
    if not env_vars:
        return
    
    # 测试prompt
    prompt = "Tell me a short story about a robot learning to paint"
    
    # 调用LLM
    response, response_time, total_tokens, tokens_per_second = call_llm(env_vars, prompt)
    
    # 打印结果
    print("\n=== LLM Response ===")
    if response:
        print(response)
    else:
        print("No response received")
    
    print("\n=== Statistics ===")
    print(f"Response Time: {response_time:.2f} seconds")
    print(f"Total Tokens: {total_tokens}")
    print(f"Tokens per Second: {tokens_per_second:.2f}")

if __name__ == "__main__":
    main()