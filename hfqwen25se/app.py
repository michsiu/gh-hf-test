import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import gradio as gr
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

def chat(prompt, system_message='', temperature=0.3, top_p=0.9, top_k=80, max_tokens=256):
    if not prompt.strip():
        return '请输入问题'
    messages = []
    if system_message:
        messages.append({'role': 'system', 'content': system_message})
    messages.append({'role': 'user', 'content': prompt})
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
    response = tokenizer.decode(outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True)
    return response.strip()

demo = gr.Interface(
    fn=chat,
    inputs=[
        gr.Textbox(label='Prompt', placeholder='输入你的问题...', lines=3),
        gr.Textbox(label='System Message', value=''),
        gr.Slider(0.1, 1.5, 0.3, label='Temperature'),
        gr.Slider(0.1, 1.0, 0.9, label='Top P'),
        gr.Slider(0, 100, 80, label='Top K'),
        gr.Slider(50, 1024, 512, label='Max Tokens')
    ],
    outputs=gr.Textbox(label='Response'),
    title='Qwen2.5-Sex',
    description='基于 Qwen2.5-1.5B 微调的对话模型（CPU 模式）'
)

demo = gr.Interface(

    fn=chat,

    inputs="text",

    outputs="text",

    api_name="chat"   # 👈 关键

)

demo.launch()