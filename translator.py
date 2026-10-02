"""OpenAI를 사용한 번역 로직."""

import json
import os

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = "gpt-6-astra"
MAX_CHARS = 5000

LANGUAGES = {
    "en": "🇺🇸 영어",
    "ja": "🇯🇵 일본어",
    "vi": "🇻🇳 베트남어",
}

# 개별 호출(fallback) 프롬프트에 쓰는 영어 언어명
LANGUAGE_NAMES = {
    "en": "English",
    "ja": "Japanese",
    "vi": "Vietnamese",
}

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into the requested "
    "languages. Preserve meaning, tone, line breaks, and formatting. Do not add "
    "explanations. Respond ONLY with a JSON object whose keys are the language codes."
)

SINGLE_SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into {language}. "
    "Preserve meaning, tone, line breaks, and formatting. "
    "Output ONLY the translated text, with no explanations."
)


class TranslationError(Exception):
    """사용자에게 그대로 보여줄 한국어 메시지를 담은 번역 오류."""


def _get_setting(name: str) -> str | None:
    """st.secrets → 환경변수/.env 순서로 설정값을 찾는다. 없으면 None."""
    try:
        value = st.secrets[name]
        if value:
            return value
    except Exception:
        # 로컬 환경에서는 secrets.toml이 없어 예외가 발생한다.
        pass
    return os.getenv(name) or None


def get_api_key() -> str | None:
    """OpenAI API 키. 설정되지 않았으면 None."""
    return _get_setting("OPENAI_API_KEY")


def get_model() -> str:
    """사용할 모델명. OPENAI_MODEL이 없으면 기본값을 쓴다."""
    return _get_setting("OPENAI_MODEL") or DEFAULT_MODEL


def _chat(messages: list[dict], model: str, json_mode: bool) -> str:
    """Chat Completions를 호출하고 응답 본문을 반환한다. OpenAI 예외는 TranslationError로 바꾼다."""
    api_key = get_api_key()
    if not api_key:
        raise TranslationError("❌ API 키가 설정되지 않았습니다. .env 또는 Secrets를 확인하세요.")

    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    try:
        response = OpenAI(api_key=api_key).chat.completions.create(
            model=model, messages=messages, **kwargs
        )
    except openai.AuthenticationError as e:
        raise TranslationError("❌ API 키가 올바르지 않습니다.") from e
    except openai.NotFoundError as e:
        raise TranslationError(
            f"❌ 모델({model})을 사용할 수 없습니다. 모델명과 계정 권한을 확인하세요."
        ) from e
    except openai.RateLimitError as e:
        raise TranslationError("⏳ 요청이 많습니다. 잠시 후 다시 시도해 주세요.") from e
    except openai.APIConnectionError as e:
        raise TranslationError("🌐 서버에 연결할 수 없습니다.") from e
    except openai.APIError as e:
        raise TranslationError(f"❌ 번역 중 오류가 발생했습니다: {e.__class__.__name__}") from e

    return response.choices[0].message.content or ""


def _translate_all(text: str, target_langs: list[str], model: str) -> dict[str, str]:
    """한 번의 호출로 여러 언어를 번역한다. JSON이 깨졌으면 빈 dict, 빠진 언어는 결과에서 제외된다."""
    user_prompt = (
        f"Target languages: {json.dumps(target_langs)}\n"
        f'Text:\n"""\n{text}\n"""'
    )
    content = _chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model,
        json_mode=True,
    )
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        lang: data[lang]
        for lang in target_langs
        if isinstance(data.get(lang), str) and data[lang].strip()
    }


def _translate_one(text: str, lang: str, model: str) -> str:
    """한 언어만 번역한다 (fallback용)."""
    return _chat(
        [
            {"role": "system", "content": SINGLE_SYSTEM_PROMPT.format(language=LANGUAGE_NAMES[lang])},
            {"role": "user", "content": text},
        ],
        model,
        json_mode=False,
    ).strip()


@st.cache_data(show_spinner=False, max_entries=200)
def _translate_cached(text: str, target_langs: tuple[str, ...], model: str) -> dict[str, str]:
    """(원문, 언어 목록, 모델) 기준으로 캐싱되는 번역. API 키는 캐시 키에 포함하지 않는다."""
    langs = list(target_langs)
    results = _translate_all(text, langs, model)
    for lang in langs:
        if lang not in results:
            results[lang] = _translate_one(text, lang, model)
    return {lang: results[lang] for lang in langs}


def translate(text: str, target_langs: list[str]) -> dict[str, str]:
    """text를 target_langs 언어들로 번역해 {코드: 번역문}으로 반환한다.

    실패하면 사용자용 메시지를 담은 TranslationError를 던진다.
    """
    return _translate_cached(text, tuple(target_langs), get_model())
