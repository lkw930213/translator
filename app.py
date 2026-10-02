"""다국어 번역기 Streamlit UI."""

import streamlit as st

from translator import (
    LANGUAGES,
    MAX_CHARS,
    TranslationError,
    get_api_key,
    get_model,
    translate,
)

st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")

# 좁은 화면에서 한글 제목이 글자 단위로 끊기지 않도록 한다.
st.markdown("<style>h1 { word-break: keep-all; }</style>", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.header("ℹ️ 정보")
    st.markdown(f"**모델:** `{get_model()}`")
    if get_api_key():
        st.success("API 키: ✅ 설정됨")
    else:
        st.error("API 키: ❌ 미설정")
    st.divider()
    st.subheader("사용 방법")
    st.markdown(
        "1. 번역할 글을 입력합니다.\n"
        "2. 번역할 언어를 선택합니다.\n"
        "3. **🔄 번역하기** 버튼을 누릅니다."
    )

# 헤더
st.title("🌐 다국어 번역기")
st.caption("입력한 글을 영어 · 일본어 · 베트남어로 번역합니다")

# 입력 영역
text = st.text_area(
    "번역할 글",
    height=200,
    placeholder="번역할 글을 입력하세요...",
    label_visibility="collapsed",
)
count_color = "#d93025" if len(text) > MAX_CHARS else "gray"
st.markdown(
    f"<div style='text-align:right; color:{count_color}; font-size:0.85rem; margin-top:-0.75rem;'>"
    f"{len(text):,} / {MAX_CHARS:,}</div>",
    unsafe_allow_html=True,
)

# 언어 선택
st.markdown("**번역 언어**")
selected = [
    lang
    for lang, col in zip(LANGUAGES, st.columns(len(LANGUAGES)))
    if col.checkbox(LANGUAGES[lang], value=True, key=f"lang_{lang}")
]


def validate(text: str, langs: list[str]) -> str | None:
    """입력값을 검사해 문제가 있으면 경고 메시지를, 없으면 None을 반환한다."""
    if not text.strip():
        return "⚠️ 번역할 내용을 입력해 주세요."
    if not langs:
        return "⚠️ 번역할 언어를 하나 이상 선택해 주세요."
    if len(text) > MAX_CHARS:
        return f"⚠️ {MAX_CHARS:,}자 이하로 입력해 주세요."
    return None


if st.button("🔄 번역하기", type="primary", width="stretch"):
    warning = validate(text, selected)
    if warning:
        st.warning(warning)
    elif not get_api_key():
        st.error("❌ API 키가 설정되지 않았습니다. .env 또는 Secrets를 확인하세요.")
    else:
        try:
            with st.spinner("번역 중입니다..."):
                st.session_state.results = translate(text, selected)
            st.session_state.source = text
        except TranslationError as e:
            st.error(str(e))

st.divider()

# 결과 영역
results = st.session_state.get("results")
if not results:
    st.info("글을 입력하고 **🔄 번역하기**를 누르면 여기에 번역 결과가 표시됩니다.")
else:
    if list(results) != selected:
        st.caption("ℹ️ 언어 선택이 바뀌었습니다. 다시 번역하면 반영됩니다.")

    tabs = st.tabs([LANGUAGES[lang] for lang in results])
    for tab, (lang, translated) in zip(tabs, results.items()):
        with tab:
            st.code(translated, language=None, wrap_lines=True)

    download_text = "\n\n".join(
        [f"[원문]\n{st.session_state.source}"]
        + [f"[{LANGUAGES[lang]}]\n{translated}" for lang, translated in results.items()]
    )
    st.download_button(
        "📥 번역 결과 다운로드 (.txt)",
        data=download_text,
        file_name="translation.txt",
        mime="text/plain",
        width="stretch",
    )
