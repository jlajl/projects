import configparser, os, subprocess
from openai import OpenAI

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "config.ini"), encoding="utf-8")
llm = config["llm"]

client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])

tools = [{
    "type": "function",
    "function": {
        "name": "getDate",
        "description": "获取当前电脑的日期和时间",
        "parameters": {"type": "object", "properties": {}},
    },
}]

messages = []
while True:
    messages.append({"role": "user", "content": input("请输入提示词: ")})
    while True:
        msg = client.chat.completions.create(
            model=llm["model_name"], messages=messages, tools=tools
        ).choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            print(msg.content)
            break
        for call in msg.tool_calls:
            now = subprocess.run(
                "date /t & time /t", shell=True, capture_output=True, text=True
            ).stdout.strip()
            messages.append({"role": "tool", "tool_call_id": call.id, "content": now})
