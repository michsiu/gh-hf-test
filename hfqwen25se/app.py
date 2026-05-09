import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from fastapi import FastAPI
import uvicorn

print("GRADIO VERSION:", gr.__version__)

model_name = 'ystemsrx/Qwen2.5-Sex'

print('正在加载模型（CPU 模式）...')
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    dtype=torch.float32,
    device_map="cpu",
    trust_remote_code=True
)
print('模型加载完成！')


# ================== 核心推理函数 ==================
def generate_reply(messages, temperature=0.3, top_p=0.9, top_k=80, max_tokens=256):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors='pt')

    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(
        outputs[0][len(inputs.input_ids[0]):],
        skip_special_tokens=True
    )
    return response.strip()


# ================== FastAPI（真正API） ==================
app = FastAPI()

@app.post("/v1/chat/completions")
def chat_api(req: dict):
    messages = req.get("messages", [])

    if not messages:
        return {"error": "messages 不能为空"}

    reply = generate_reply(messages)

    return {
        "choices": [
            {
                "message": {
                    "content": reply
                }
            }
        ]
    }


# ================== Gradio UI（可选） ==================
def chat_ui(prompt):
    messages = [{"role": "user", "content": prompt}]
    return generate_reply(messages)

demo = gr.Interface(
    fn=chat_ui,
    inputs="text",
    outputs="text",
    title="Qwen2.5-Sex"
)


# ================== 挂载 ==================
app = gr.mount_gradio_app(app, demo, path="/")

# HF Spaces 用这个启动