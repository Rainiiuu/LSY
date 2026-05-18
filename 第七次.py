import os
import json
import time
import http.client
import urllib.parse
import re

# 加载环境变量
def load_env():
    """加载环境变量"""
    env = {}
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 查找.env文件的可能位置
    env_paths = [
        os.path.join(current_dir, '.env'),  # 当前目录
        os.path.join(os.path.dirname(current_dir), '.env'),  # 上级目录
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), '.env')  # 上上级目录（项目根目录）
    ]
    
    found_env = False
    for env_file in env_paths:
        print(f"查找环境变量文件: {env_file}")
        if os.path.exists(env_file):
            print(f"找到.env文件: {env_file}，正在加载...")
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            env[key.strip()] = value.strip().strip('"')
                print(f"已加载环境变量: {list(env.keys())}")
                found_env = True
                break
            except Exception as e:
                print(f"读取.env文件失败: {e}")
    
    if not found_env:
        print("未找到.env文件，使用默认值")
    
    # 默认值
    env.setdefault('BASE_URL', 'http://localhost:1234/v1')
    env.setdefault('MODEL', 'qwen/qwen3.5-9b')
    env.setdefault('API_KEY', '')
    env.setdefault('TEMPERATURE', '0.33')
    env.setdefault('MAX_TOKENS', '4096')
    env.setdefault('TOP_P', '0.2')
    
    print(f"最终环境变量:")
    print(f"  BASE_URL: {env['BASE_URL']}")
    print(f"  MODEL: {env['MODEL']}")
    print(f"  API_KEY: {'***' if env['API_KEY'] else '未设置'}")
    print(f"  TEMPERATURE: {env['TEMPERATURE']}")
    print(f"  MAX_TOKENS: {env['MAX_TOKENS']}")
    print(f"  TOP_P: {env['TOP_P']}")
    
    return env

# 加载环境变量
env = load_env()

# 转换类型
env['TEMPERATURE'] = float(env['TEMPERATURE'])
env['MAX_TOKENS'] = int(env['MAX_TOKENS'])
env['TOP_P'] = float(env['TOP_P'])

# 加载所有 SKILL.md
def load_skills():
    skills = []
    # 获取项目根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    skills_dir = os.path.join(project_root, '.agents', 'skills')
    
    print(f"读取技能目录: {skills_dir}")
    
    if os.path.exists(skills_dir):
        # 遍历一级子目录
        for skill_dir in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, skill_dir)
            if os.path.isdir(skill_path):
                # 读取SKILL.md文件
                skill_file = os.path.join(skill_path, 'SKILL.md')
                if os.path.exists(skill_file):
                    try:
                        with open(skill_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 提取YAML front matter
                        front_matter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
                        if front_matter_match:
                            front_matter = front_matter_match.group(1)
                            # 提取name和description字段
                            name_match = re.search(r'name:\s*["\'](.*?)["\']', front_matter)
                            description_match = re.search(r'description:\s*["\'](.*?)["\']', front_matter)
                            
                            if name_match and description_match:
                                # 提取正文内容
                                body = content[front_matter_match.end():].strip()
                                skill = {
                                    'name': name_match.group(1),
                                    'description': description_match.group(1),
                                    'content': body
                                }
                                skills.append(skill)
                                print(f"找到技能: {skill['name']} - {skill['description']}")
                    except Exception as e:
                        print(f"读取技能文件失败: {e}")
    else:
        print(f"技能目录不存在: {skills_dir}")
    
    return skills

def load_skill_content(skill_name):
    skills = load_skills()
    for s in skills:
        if s["name"] == skill_name:
            print(f"成功加载技能内容: {skill_name}")
            return s["content"]
    print(f"未找到技能: {skill_name}")
    return None

def call_llm_with_stream(history, env):
    start = time.time()
    try:
        # 解析URL
        url = urllib.parse.urlparse(env["BASE_URL"])
        # 根据协议选择连接类型
        if url.scheme == 'https':
            conn = http.client.HTTPSConnection(url.netloc)
        else:
            conn = http.client.HTTPConnection(url.netloc)
        
        # 构建请求路径
        path = url.path or '/'
        if url.query:
            path += '?' + url.query
        
        # 准备请求数据
        payload = {
            "model": env.get("MODEL", "gpt-3.5-turbo"),
            "messages": history,
            "temperature": env["TEMPERATURE"],
            "max_tokens": env["MAX_TOKENS"],
            "top_p": env["TOP_P"],
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {env['API_KEY']}",
            "Content-Type": "application/json"
        }
        
        # 发送请求
        conn.request("POST", path + ("/chat/completions" if not path.endswith("/chat/completions") else ""), 
                    json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers)
        
        # 获取响应
        resp = conn.getresponse()
        status_code = resp.status
        data = resp.read().decode("utf-8")
        
        print(f"API 响应状态码: {status_code}")
        print(f"API 响应内容: {data[:200]}..." if len(data) > 200 else f"API 响应内容: {data}")
        
        # 检查响应状态
        if status_code != 200:
            return f"API 调用失败，状态码: {status_code}, 响应: {data}", 0, time.time() - start
        
        # 解析响应
        result = json.loads(data)
        content = result["choices"][0]["message"]["content"].strip()
        tokens = result["usage"]["total_tokens"]
        cost = time.time() - start
        return content, tokens, cost
    except json.JSONDecodeError as e:
        return f"JSON 解析错误：{str(e)}，响应内容: {data}", 0, time.time() - start
    except Exception as e:
        return f"LLM 调用异常：{str(e)}", 0, time.time() - start

# ==================== 链式工具调用实现 ====================

class ChainedCallContext:
    """
    链式调用上下文管理器
    用于在多个工具调用之间传递数据和状态
    """
    
    def __init__(self, max_iterations=5):
        """
        初始化链式调用上下文
        
        Args:
            max_iterations: 最大迭代次数，防止无限循环
        """
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.steps = []  # 记录每一步的调用和结果
        self.variables = {}  # 存储中间变量供后续步骤使用
        self.final_result = None  # 最终结果
        self.is_complete = False  # 是否完成任务
    
    def add_step(self, action, tool_name=None, params=None, result=None, error=None):
        """
        添加一步调用记录
        
        Args:
            action: 动作类型 ('tool_call', 'analysis', 'complete')
            tool_name: 工具名称
            params: 调用参数
            result: 执行结果
            error: 错误信息
        """
        step = {
            'iteration': self.current_iteration,
            'action': action,
            'tool_name': tool_name,
            'params': params,
            'result': result,
            'error': error,
            'timestamp': time.time()
        }
        self.steps.append(step)
    
    def set_variable(self, name, value):
        """
        设置中间变量
        
        Args:
            name: 变量名
            value: 变量值
        """
        self.variables[name] = value
    
    def get_variable(self, name, default=None):
        """
        获取中间变量
        
        Args:
            name: 变量名
            default: 默认值
        
        Returns:
            变量值，如果不存在返回默认值
        """
        return self.variables.get(name, default)
    
    def increment_iteration(self):
        """增加迭代次数"""
        self.current_iteration += 1
    
    def is_max_iterations_reached(self):
        """检查是否达到最大迭代次数"""
        return self.current_iteration >= self.max_iterations
    
    def complete(self, result):
        """标记任务完成"""
        self.final_result = result
        self.is_complete = True
        self.add_step('complete', result=result)
    
    def get_steps_summary(self):
        """获取步骤摘要"""
        summary = []
        for step in self.steps:
            if step['action'] == 'tool_call':
                summary.append(f"步骤 {step['iteration']}: 调用工具 '{step['tool_name']}'，参数: {step['params']}")
            elif step['action'] == 'analysis':
                summary.append(f"步骤 {step['iteration']}: 分析决策")
            elif step['action'] == 'complete':
                summary.append(f"步骤 {step['iteration']}: 任务完成")
        return "\n".join(summary)
    
    def __repr__(self):
        return f"ChainedCallContext(iterations={self.current_iteration}/{self.max_iterations}, steps={len(self.steps)}, complete={self.is_complete})"

# 定义可用工具
def list_files(directory=None, path=None):
    """列出目录下的文件和文件夹"""
    try:
        # 支持directory和path两种参数名
        dir_path = directory if directory else path
        if not dir_path:
            dir_path = '.'
        
        files = []
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                files.append({"name": item, "type": "directory", "size": 0})
            else:
                files.append({"name": item, "type": "file", "size": os.path.getsize(item_path)})
        return json.dumps(files, ensure_ascii=False, indent=2)
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

def create_file(file_path, content):
    """创建文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"文件 {file_path} 创建成功"
    except Exception as e:
        return f"错误: {str(e)}"

def delete_file(file_path):
    """删除文件"""
    try:
        os.remove(file_path)
        return f"文件 {file_path} 删除成功"
    except Exception as e:
        return f"错误: {str(e)}"

def rename_file(old_path, new_name):
    """重命名文件"""
    try:
        directory = os.path.dirname(old_path)
        new_path = os.path.join(directory, new_name)
        os.rename(old_path, new_path)
        return f"文件已重命名为 {new_path}"
    except Exception as e:
        return f"错误: {str(e)}"

def curl_file(url):
    """通过HTTP访问网页并返回网页内容"""
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme == 'https':
            conn = http.client.HTTPSConnection(parsed_url.netloc)
        else:
            conn = http.client.HTTPConnection(parsed_url.netloc)
        
        path = parsed_url.path or '/'
        if parsed_url.query:
            path += '?' + parsed_url.query
        
        conn.request("GET", path)
        resp = conn.getresponse()
        content = resp.read().decode("utf-8", errors='ignore')
        return content
    except Exception as e:
        return f"错误: {str(e)}"

def summarize_content(content):
    """
    总结网页内容
    
    Args:
        content: 网页内容（HTML格式）
    
    Returns:
        str: 总结内容
    """
    # 去除HTML标签
    text = re.sub(r'<[^>]+>', '', content)
    # 去除多余空白字符
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 如果文本太长，截取前2000个字符
    if len(text) > 2000:
        text = text[:2000] + "..."
    
    # 尝试提取关键信息
    summary = "网页内容总结：\n\n"
    
    # 提取标题（通常在h1-h3标签中）
    title_match = re.search(r'<h[1-3][^>]*>([^<]+)</h[1-3]>', content)
    if title_match:
        summary += f"【标题】{title_match.group(1)}\n\n"
    
    # 提取段落内容
    paragraphs = re.findall(r'<p[^>]*>([^<]+)</p>', content)
    if paragraphs:
        summary += "【主要内容】\n"
        for i, p in enumerate(paragraphs[:5]):  # 最多取5个段落
            p_clean = re.sub(r'\s+', ' ', p).strip()
            if p_clean:
                summary += f"{i+1}. {p_clean}\n"
    
    # 如果没有找到段落，使用纯文本
    if not paragraphs or len(paragraphs) == 0:
        summary += f"【内容摘要】{text[:500]}\n"
    
    # 提取日期信息
    date_match = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)', content)
    if date_match:
        summary += f"\n【日期】{date_match.group(1)}\n"
    
    # 提取来源信息
    source_match = re.search(r'(来源|来源网站|作者)[：:]?\s*([^\s<>]+)', content)
    if source_match:
        summary += f"【来源】{source_match.group(2)}\n"
    
    return summary

# 工具映射
TOOL_MAP = {
    "list_files": list_files,
    "read_file": read_file,
    "create_file": create_file,
    "delete_file": delete_file,
    "rename_file": rename_file,
    "curl_file": curl_file
}

def execute_tool(tool_name, params):
    """
    执行工具调用
    
    Args:
        tool_name: 工具名称
        params: 工具参数（字典）
    
    Returns:
        工具执行结果
    """
    if tool_name not in TOOL_MAP:
        return f"未知工具: {tool_name}"
    
    try:
        # 清理参数，去除可能的反引号和多余空格
        cleaned_params = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 去除反引号、首尾空格、多余引号
                cleaned_value = value.strip().strip('`').strip('\'"')
                cleaned_params[key] = cleaned_value
            else:
                cleaned_params[key] = value
        
        tool_func = TOOL_MAP[tool_name]
        result = tool_func(**cleaned_params)
        return result
    except Exception as e:
        return f"工具执行失败: {str(e)}"

def build_analysis_prompt(user_request, context):
    """
    构建分析提示词
    
    Args:
        user_request: 用户原始请求
        context: 链式调用上下文
    
    Returns:
        str: 分析提示词
    """
    # 构建已执行的工具调用历史
    steps_history = []
    for step in context.steps:
        if step['action'] == 'tool_call':
            steps_history.append({
                "tool_name": step['tool_name'],
                "params": step['params'],
                "result": step['result'][:200] + "..." if len(str(step['result'])) > 200 else step['result']
            })
    
    # 决策规则说明
    decision_rules = """
## 决策规则：
1. **目标导向**：始终以完成用户原始请求为目标
2. **结果依赖**：根据前一步工具执行的结果决定下一步操作
3. **效率优先**：避免重复调用相同工具或执行无效操作
4. **状态跟踪**：利用上下文变量存储和传递中间结果
5. **终止条件**：当获得足够信息可以回答用户问题时，立即完成任务
"""
    
    # JSON输出格式要求
    format_requirements = """
## JSON 输出格式要求：

### 格式1：完成任务时
{"done": true, "answer": "最终回答内容"}

### 格式2：继续调用工具时
{"done": false, "tool_call": {"name": "工具名称", "arguments": {"参数名": "参数值"}}}
"""
    
    prompt = f"""
# 当前任务分析

## 用户原始请求：
{user_request}

## 已执行的工具调用历史：
{json.dumps(steps_history, ensure_ascii=False, indent=2) if steps_history else '暂无'}

## 当前中间变量：
{json.dumps(context.variables, ensure_ascii=False, indent=2) if context.variables else '暂无'}

## 当前步骤：{context.current_iteration}/{context.max_iterations}

{decision_rules}

{format_requirements}

请根据以上信息，分析当前状态并做出决策。
"""
    
    return prompt

def parse_tool_call(response):
    """
    解析LLM响应中的工具调用
    
    Args:
        response: LLM响应内容
    
    Returns:
        tuple: (tool_name, params, is_tool_call, is_complete, answer)
    """
    # 清理响应，去除多余的空白字符
    cleaned_response = response.strip()
    
    # 如果响应为空或只有空白，返回未完成状态
    if not cleaned_response:
        return None, None, False, False, ''
    
    # 尝试提取JSON部分（处理可能包含前后文的情况）
    json_start = cleaned_response.find('{')
    json_end = cleaned_response.rfind('}') + 1
    
    if json_start != -1 and json_end != 0:
        json_str = cleaned_response[json_start:json_end]
    else:
        json_str = cleaned_response
    
    # 尝试解析JSON格式
    try:
        data = json.loads(json_str)
        if 'done' in data:
            if data['done']:
                answer = data.get('answer', '')
                # 如果answer为空，尝试从response中提取文本内容
                if not answer:
                    # 尝试提取JSON外的文本
                    text_before = cleaned_response[:json_start].strip()
                    text_after = cleaned_response[json_end:].strip()
                    answer = text_before + text_after if text_before or text_after else '任务已完成'
                return None, None, False, True, answer
            else:
                tool_call = data.get('tool_call', {})
                tool_name = tool_call.get('name')
                params = tool_call.get('arguments', {})
                if tool_name:
                    return tool_name, params, True, False, ''
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        print(f"尝试解析的JSON字符串: {json_str[:200]}...")
    
    # 尝试使用正则提取工具调用信息
    # 格式: {"done": false, "tool_call": {"name": "...", "arguments": {...}}}
    done_true_match = re.search(r'"done"\s*:\s*true', cleaned_response, re.IGNORECASE)
    done_false_match = re.search(r'"done"\s*:\s*false', cleaned_response, re.IGNORECASE)
    
    if done_true_match:
        # 任务完成，提取answer
        answer_match = re.search(r'"answer"\s*:\s*["\']([^"\']+)["\']', cleaned_response)
        answer = answer_match.group(1) if answer_match else '任务已完成'
        return None, None, False, True, answer
    
    elif done_false_match:
        # 需要调用工具，提取工具名和参数
        tool_name_match = re.search(r'"name"\s*:\s*["\']([^"\']+)["\']', cleaned_response)
        if tool_name_match:
            tool_name = tool_name_match.group(1)
            # 尝试提取arguments
            args_match = re.search(r'"arguments"\s*:\s*(\{[^}]+\})', cleaned_response)
            try:
                params = json.loads(args_match.group(1)) if args_match else {}
            except:
                params = {}
            return tool_name, params, True, False, ''
    
    # 检查是否包含总结/完成相关的关键词
    complete_keywords = ['总结', '完成', '任务完成', '已完成', '报告如下', '结果如下', '答案是']
    if any(keyword in cleaned_response for keyword in complete_keywords):
        # 如果响应中包含这些关键词，且不是明显的工具调用格式，则认为是完成任务
        if '"tool_call"' not in cleaned_response.lower():
            return None, None, False, True, cleaned_response
    
    # 如果都无法解析，尝试直接解析工具名称
    tool_name_match = re.search(r'(list_files|read_file|create_file|delete_file|rename_file|curl_file)', cleaned_response)
    if tool_name_match:
        tool_name = tool_name_match.group(1)
        # 尝试提取参数
        params = {}
        # 尝试提取directory参数
        dir_match = re.search(r'(directory|path|file_path|url)\s*[=:]\s*["\']([^"\']+)["\']', cleaned_response)
        if dir_match:
            params[dir_match.group(1)] = dir_match.group(2)
        return tool_name, params, True, False, ''
    
    # 默认返回未完成状态，让LLM重新生成
    return None, None, False, False, ''

def execute_chained_tool_call(user_request, skills, env, max_iterations=5):
    """
    执行链式工具调用的完整流程
    
    Args:
        user_request: 用户请求
        skills: 可用技能列表
        env: 环境变量
        max_iterations: 最大迭代次数
    
    Returns:
        tuple: (final_result, total_tokens, total_time, context)
    """
    start_time = time.time()
    total_tokens = 0
    
    # 初始化上下文
    context = ChainedCallContext(max_iterations=max_iterations)
    
    # 构建工具列表描述
    tools_desc = []
    for tool_name, tool_func in TOOL_MAP.items():
        tools_desc.append(f"- {tool_name}: {tool_func.__doc__}")
    
    # 构建技能列表描述
    skills_desc = []
    for skill in skills:
        skills_desc.append(f"- {skill['name']}: {skill['description']}")
    
    # 初始化消息历史
    history = []
    
    # 更新后的系统提示词
    system_prompt = f"""
你是一个智能助手，可以执行链式工具调用来完成复杂任务。

## 可用工具：
{chr(10).join(tools_desc)}

## 可用技能：
{chr(10).join(skills_desc)}

## 链式调用规则：

### 1. 工具调用顺序依赖
- 后一个工具的输入可以基于前一个工具的输出
- 例如：先调用 list_files 获取文件列表，再调用 read_file 读取具体文件内容
- 再例如：先调用 read_file 读取数据，再调用 create_file 写入处理结果

### 2. 中间结果决策
- 每一步调用工具后，根据返回结果决定下一步操作
- 如果结果已足够回答用户问题，则完成任务
- 如果需要更多信息，则继续调用其他工具

### 3. 上下文变量使用
- 可以使用上下文变量存储中间结果
- 变量格式：{{{{variable_name}}}}
- 例如：将读取的文件内容存储到变量中供后续步骤使用

### 4. 链式调用示例

#### 示例1：文件搜索并读取
用户请求：查找目录下的文件并读取
1. 调用 list_files("directory") 获取文件列表
2. 分析结果，选择需要读取的文件
3. 调用 read_file("file_path") 读取文件内容
4. 总结内容，完成任务

#### 示例2：多文件操作
用户请求：读取两个文件并计算
1. 调用 read_file("file1.txt") 读取第一个文件
2. 调用 read_file("file2.txt") 读取第二个文件
3. 根据两个文件内容进行计算
4. 调用 create_file("result.txt", "计算结果") 保存结果
5. 完成任务

#### 示例3：网页处理
用户请求：访问网页并保存摘要
1. 调用 curl_file("https://example.com") 获取网页内容
2. 分析并总结网页内容
3. 调用 create_file("summary.txt", "摘要内容") 保存结果
4. 完成任务

## 响应格式要求：

### 格式1：完成任务时
{{
    "done": true,
    "answer": "最终回答内容"
}}

### 格式2：继续调用工具时
{{
    "done": false,
    "tool_call": {{
        "name": "工具名称",
        "arguments": {{
            "参数名": "参数值"
        }}
    }}
}}

## 注意事项：
- 必须严格按照JSON格式输出
- 不要输出任何额外的解释或说明文字
- 不要重复执行相同的操作
- 如果遇到错误，尝试其他方法
- 最多执行 {max_iterations} 步
- 每一步都要基于前一步的结果进行决策
"""
    
    history.append({"role": "system", "content": system_prompt})
    history.append({"role": "user", "content": user_request})
    
    print(f"\n=== 开始链式工具调用 ===")
    print(f"用户请求: {user_request}")
    print(f"最大迭代次数: {max_iterations}")
    
    while not context.is_complete and not context.is_max_iterations_reached():
        context.increment_iteration()
        print(f"\n--- 第 {context.current_iteration} 步 ---")
        
        # 使用分析提示词构建函数
        analysis_prompt = build_analysis_prompt(user_request, context)
        
        history.append({"role": "user", "content": analysis_prompt})
        
        # 调用LLM决定下一步操作
        response, tokens, cost = call_llm_with_stream(history, env)
        total_tokens += tokens
        
        # 检查LLM响应是否包含异常信息
        if "异常" in response or "error" in response.lower() or "Exception" in response:
            print(f"LLM调用异常: {response[:100]}...")
            # 如果LLM调用失败，尝试直接分析并决定下一步
            context.add_step('analysis', result=f"LLM调用异常，尝试继续处理")
            # 根据当前状态决定下一步
            if context.steps:
                # 如果已有工具执行结果，尝试总结
                last_step = context.steps[-1]
                if last_step['action'] == 'tool_call' and last_step['tool_name'] == 'curl_file':
                    # 已经获取了网页内容，下一步应该总结并保存
                    print("检测到已获取网页内容，自动进入总结步骤")
                    # 直接创建总结文件
                    page_content = last_step['result']
                    summary = summarize_content(page_content)
                    create_file("practice07/summary.txt", summary)
                    context.complete(f"已成功访问网页并总结内容，保存到 practice07/summary.txt\n\n总结内容:\n{summary}")
                    history.append({"role": "assistant", "content": f"已完成网页总结并保存"})
                    break
            # 默认继续下一步
            continue
        
        print(f"LLM响应: {response[:150]}..." if len(response) > 150 else f"LLM响应: {response}")
        
        # 解析LLM响应
        tool_name, params, is_tool_call, is_complete, answer = parse_tool_call(response)
        
        if is_complete:
            # 任务完成
            final_answer = answer if answer else response
            context.complete(final_answer)
            history.append({"role": "assistant", "content": final_answer})
            print(f"任务完成: {final_answer[:100]}..." if len(final_answer) > 100 else f"任务完成: {final_answer}")
            break
        
        elif is_tool_call and tool_name:
            # 需要调用工具
            print(f"调用工具: {tool_name}, 参数: {params}")
            
            # 执行工具
            result = execute_tool(tool_name, params)
            
            # 记录到上下文
            context.add_step('tool_call', tool_name=tool_name, params=params, result=result)
            
            # 保存中间变量（使用工具名作为变量名）
            context.set_variable(f"{tool_name}_result", result)
            context.set_variable(f"step_{context.current_iteration}_result", result)
            
            print(f"工具执行结果: {result[:100]}..." if len(str(result)) > 100 else f"工具执行结果: {result}")
            
            # 将结果添加到消息历史
            history.append({"role": "assistant", "content": f"工具调用结果:\n工具: {tool_name}\n参数: {params}\n结果: {result}"})
            
        else:
            # 不需要调用工具，直接回答
            context.complete(response)
            history.append({"role": "assistant", "content": response})
            print(f"直接回答用户")
            break
    
    total_time = time.time() - start_time
    
    # 如果达到最大迭代次数仍未完成
    if not context.is_complete:
        context.complete(f"已达到最大迭代次数 {max_iterations}，任务未完成。已执行的步骤：\n{context.get_steps_summary()}")
    
    print(f"\n=== 链式调用结束 ===")
    print(f"总步骤数: {len(context.steps)}")
    print(f"总Token数: {total_tokens}")
    print(f"总耗时: {total_time:.2f} 秒")
    
    return context.final_result, total_tokens, total_time, context

def main():
    skills = load_skills()
    
    print("\n=== 链式工具调用客户端已启动（输入 exit 退出）===\n")
    
    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("再见！")
            break
        
        print(f"\n用户请求: {user_input}")
        
        # 执行链式工具调用
        result, tokens, cost, context = execute_chained_tool_call(user_input, skills, env)
        
        print(f"\n助手: {result}")
        print(f"\n=== 统计信息 ===")
        print(f"响应时间: {cost:.2f} 秒")
        print(f"总Token数: {tokens}")
        print(f"Token速度: {tokens/cost:.2f} tokens/秒")
        print(f"执行步骤: {len(context.steps)}")

if __name__ == "__main__":
    main()
