import configparser, os, sys
from openai import OpenAI

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "config.ini"), encoding="utf-8")
llm = config["llm"]

client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])

while True:
    prompt = input("请输入提示词: ")
    stream = client.chat.completions.create(
        model=llm["model_name"],
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()
