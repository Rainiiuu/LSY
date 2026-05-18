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

def main():
    skills = load_skills()
    skills_json = json.dumps(skills, ensure_ascii=False, indent=2)
    history = []

    system_prompt = f"""
你是一个专业的AI助手，严格按照规则执行任务。

可用技能：
{skills_json}

============================================
【通知撰写助手 · 强制规则】
当用户需要：撰写通知、修改通知、润色通知时，必须遵守：
1. 通知标题 绝对不能以“通知”二字开头
2. 必须以部门名称开头，例如：采购部、宣传部、行政部
3. 如果用户没有说明部门，统一使用：XX部
4. 输出完整、正式、规范的通知格式
5. 对于五一放假通知，必须包含放假时间、调休安排、注意事项等关键信息
============================================

回复要求：
1. 只输出最终结果，不输出思考、注释、多余解释
2. 工具调用按格式输出
3. 回答简洁、专业、合规
4. 当用户要求撰写通知时，直接生成完整的通知内容
"""
    history.append({"role": "system", "content": system_prompt})
    print("=== 工具客户端已启动（输入 exit 退出）===\n")

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("再见！")
            break

        history.append({"role": "user", "content": user_input})

        # ============== 触发通知技能 ==============
        user_msg = user_input.lower()
        notice_keywords = [
            "写通知", "通知", "撰写通知", "帮我写通知",
            "改通知", "修改通知", "润色通知", "优化通知",
            "放假通知", "五一通知"
        ]
        trigger = any(kw in user_msg for kw in notice_keywords)

        if trigger:
            print("\n=== 使用技能：通知撰写助手 ===")
            skill_content = load_skill_content("通知撰写助手")
            temp_hist = history.copy()
            temp_hist.append({"role": "system", "content": skill_content})
            resp, t, c = call_llm_with_stream(temp_hist, env)
            history.append({"role": "assistant", "content": resp})

            print(f"助手: {resp}")
            print(f"\n=== 统计信息 ===")
            print(f"响应时间: {c:.2f} 秒 | 总Token数: {t} | Token速度: {t/c:.2f} tokens/秒")
            continue

        # ============== 普通回答 ==============
        response, tokens, cost = call_llm_with_stream(history, env)
        print(f"助手: {response}")
        print(f"\n=== 统计信息 ===")
        print(f"响应时间: {cost:.2f} 秒 | 总Token数: {tokens} | Token速度: {tokens/cost:.2f} tokens/秒")
        history.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()