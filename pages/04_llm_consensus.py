"""
多模型共识 AI 研判 — 多模型并行 + 融合结论
"""

import streamlit as st

st.set_page_config(page_title="AI 研判", page_icon="🤖", layout="wide")

st.title("🤖 多模型共识 AI 研判")

code = st.text_input("股票代码", "600519")
prompt_text = st.text_area(
    "输入分析指令",
    "请对该标的进行综合研判：技术面趋势、资金面动向、估值水平、短期风险",
    height=100,
)

c1, c2 = st.columns(2)
with c1: model_1 = st.selectbox("模型 A", ["deepseek-chat", "gpt-4o-mini", "doubao-seed-code"], index=0)
with c2: model_2 = st.selectbox("模型 B", ["deepseek-chat", "gpt-4o-mini", "doubao-seed-code"], index=1)

if st.button("🧠 多模型并行分析", type="primary"):
    try:
        from core.llm_engine import get_llm_engine

        engine = get_llm_engine()

        with st.spinner(f"调用 {model_1} + {model_2} 分析中..."):
            result_1 = engine.chat_structured(
                model_1,
                "你是专业量化分析师。请用JSON格式输出分析结果。",
                f"分析标的: {code}\n{prompt_text}",
            )

            result_2 = engine.chat_structured(
                model_2,
                "你是专业量化分析师。请用JSON格式输出分析结果。",
                f"分析标的: {code}\n{prompt_text}",
            )

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader(f"📊 {model_1}")
            if isinstance(result_1, dict) and "error" not in result_1:
                st.json(result_1)
            else:
                st.info(f"模型 A 返回: {result_1}")

        with col_b:
            st.subheader(f"📊 {model_2}")
            if isinstance(result_2, dict) and "error" not in result_2:
                st.json(result_2)
            else:
                st.info(f"模型 B 返回: {result_2}")

        st.subheader("🧬 共识融合")
        consensus = {
            "model_a_score": result_1.get("score", "N/A") if isinstance(result_1, dict) else "N/A",
            "model_b_score": result_2.get("score", "N/A") if isinstance(result_2, dict) else "N/A",
            "agreement": "一致看多" if (
                isinstance(result_1, dict) and isinstance(result_2, dict)
                and result_1.get("trend") == result_2.get("trend")
            ) else "存在分歧",
        }
        st.json(consensus)

        # LLM 统计
        stats = engine.get_stats()
        with st.expander("📈 LLM 调用统计"):
            st.json(stats)

    except Exception as e:
        st.error(f"AI 分析失败: {e}")
        st.info("请确保已配置 LLM API Key（DEEPSEEK_API_KEY / ARK_API_KEY）")
