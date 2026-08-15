import fitz

pdf_path = r"F:/xwechat_files/wxid_rdu88nq0dj7222_fe9b/msg/file/2026-08/大模型开发学员毕设项目布置说明文档（final）.pdf"
out_path = r"C:/Users/13656/WorkBuddy/2026-07-22-12-49-13/毕设说明文档_提取.txt"

doc = fitz.open(pdf_path)
print(f"页数: {doc.page_count}")
full = []
for i, page in enumerate(doc):
    text = page.get_text()
    full.append(f"\n===== 第 {i+1} 页 =====\n{text}")
all_text = "\n".join(full)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(all_text)
print(f"已写入: {out_path}")
print("字符数:", len(all_text))
doc.close()
