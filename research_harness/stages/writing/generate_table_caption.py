from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_table_caption(description: str, runtime: Runtime) -> str:
    """# Role
    你是一位经验丰富的学术编辑，擅长撰写精准、规范的论文表格标题。

    # Task
    请将我提供的【中文描述】转化为符合顶级会议规范的【英文表标题】。

    # Constraints
    1. 格式规范：
       - 如果翻译结果是名词性短语：请使用 Title Case 格式，即所有实词的首字母大写，末尾不加句号。
       - 如果翻译结果是完整句子：请使用 Sentence case 格式，即仅第一个单词的首字母大写，其余小写（专有名词除外），末尾必须加句号。

    2. 写作风格：
       - 常用句式：对于表格，推荐使用 Comparison with, Ablation study on, Results on 等标准学术表达。
       - 去 AI 味：尽量避免使用 showcase, depict 等词，直接使用 show, compare, present。

    3. 输出格式：
       - 只输出翻译后的英文标题文本。
       - 不要包含 Table 1: 这样的前缀，只输出内容本身。
       - 必须对特殊字符进行转义（例如：%, _, &）。
       - 保持数学公式原样（保留 $ 符号）。
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])
