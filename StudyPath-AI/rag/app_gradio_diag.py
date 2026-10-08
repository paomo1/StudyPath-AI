"""
最小诊断界面：确认 Gradio 4.x 下 Textbox + Button 的渲染结构、样式能否命中。
不带任何自定义 CSS / JS。
"""
import sys, os, html
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import gradio as gr
    from agents import ask_multi
except Exception as e:
    print("[FATAL] imports failed:", e)
    sys.exit(1)

def consult(query, history):
    if not query or not query.strip():
        return "", history + [("⚠️ 请输入内容", "")]
    try:
        r = ask_multi(query)
        return "", history + [(query, r.get("answer", "(无回答)"))]
    except Exception as e:
        return "", history + [(query, f"❌ {type(e).__name__}: {e}")]

CUSTOM_CSS = """
/* 最简诊断 CSS —— 只命中 elem_id，不动其他 */
#spQBox textarea{
  background:#fefefe !important;
  border:1.5px solid #d0d0d0 !important;
  border-radius:10px !important;
  color:#111 !important;
  font-size:15px !important;
  min-height:46px !important;
}
#spQBox textarea:focus{
  background:#fff !important;
  border-color:#3b5bdb !important;
  outline:none !important;
  box-shadow:0 0 0 3px rgba(59,91,219,.18) !important;
}
"""

with gr.Blocks(title="StudyPath · 诊断版", css=CUSTOM_CSS) as demo:
    gr.Markdown(
        "## StudyPath · 诊断版\n"
        "这一版**只**有：1 个输入框 + 1 个按钮 + 1 个对话窗口\n"
        "**没有**背景层、没有 JS、没有渐变、没有 canvas——"
        "只测 Gradio 组件本身能不能交互、elem_id 锁样式能不能命中。"
    )
    chatbot = gr.Chatbot(label="对话", height=420, value=[], type="tuples")
    query_box = gr.Textbox(
        placeholder="试试输入：我想申请美国 CS 硕士，GPA 3.5 托福 100",
        lines=2,
        show_label=False,
        elem_id="spQBox",          # ← 锁样式用
        container=False,
    )
    submit_btn = gr.Button("发送 / Send", variant="primary")
    clear_btn = gr.Button("清空")
    # 事件绑定 —— 和驾驶舱版一模一样的写法
    submit_btn.click(consult, [query_box, chatbot], [query_box, chatbot])
    query_box.submit(consult, [query_box, chatbot], [query_box, chatbot])
    clear_btn.click(lambda: ("", []), None, [query_box, chatbot], queue=False)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7861)  # ← 7861 端口避开 v1/v2
    print("✅ 已启动 → http://127.0.0.1:7861")
