from hypothesis import given
from hypothesis import strategies as st

from legal_rag_router.normalise import (
    fold,
    split_title_year,
    title_key,
    title_words,
    tokenise,
)


def test_fold_basics() -> None:
    assert fold("Art\u00edculo 42").text == "articulo 42"
    assert fold("EMPLOYMENT  Rights\u00a0Act").text == "employment rights act"
    assert fold("ss.124\u2013126").text == "ss.124-126"
    assert fold("\u201cthe Act\u201d").text == '"the act"'
    assert fold("\uff53\uff0e\uff11\uff12\uff14").text == "s.124"  # full-width → ASCII (NFKC)


def test_lookalike_letters_are_folded() -> None:
    assert fold("Employment Rights \u0410ct 1996").text == "employment rights act 1996"


def test_offsets_point_into_original() -> None:
    query = "Under Art\u00edculo  42 \u2014 the CdC"
    for token in tokenise(query):
        original = query[token.start : token.end]
        assert fold(original).text == token.text


def test_tokenise_kinds() -> None:
    tokens = tokenise("s.124(1ZA)(a) of ERA 1996 \u00a75")
    assert [t.text for t in tokens] == [
        "s", ".", "124", "(", "1", "za", ")", "(", "a", ")", "of", "era", "1996", "\u00a7", "5",
    ]  # fmt: skip
    assert {t.kind for t in tokens} == {"word", "number", "punct"}


def test_expanding_characters_keep_valid_spans() -> None:
    query = "\ufb01nance Act"  # U+FB01 ligature folds to two characters
    tokens = tokenise(query)
    assert tokens[0].text == "finance"
    assert query[tokens[0].start : tokens[0].end] == "\ufb01nance"


@given(st.text(max_size=200))
def test_tokens_always_map_back(text: str) -> None:
    for token in tokenise(text):
        assert 0 <= token.start <= token.end <= len(text)


def test_title_words_and_keys() -> None:
    assert title_words("The Employment Rights (Increase of Limits) Order 2011") == (
        "employment", "rights", "increase", "limits", "order", "2011",
    )  # fmt: skip
    assert title_words("C\u00f3digo de Comercio") == ("codigo", "comercio")
    assert title_words("Codigo Comercio") == ("codigo", "comercio")
    assert title_words("Consolidated Fund (No. 2) Act 1996")[:4] == (
        "consolidated",
        "fund",
        "no",
        "2",
    )
    assert title_words("Workers' Statute") == ("workers", "statute")
    assert title_words("Sale & Supply of Goods Act") == ("sale", "supply", "goods", "act")
    assert title_key(("employment", "rights", "act"), 1996) == "employment rights act|1996"
    assert title_key(("employment", "rights", "act")) == "employment rights act"


def test_split_title_year() -> None:
    assert split_title_year("Employment Rights Act 1996") == ("Employment Rights Act", 1996)
    assert split_title_year("Employment Rights Act (1996)") == ("Employment Rights Act", 1996)
    assert split_title_year("Statute of Marlborough 1267") == ("Statute of Marlborough", 1267)
    assert split_title_year("Civil Procedure Rules") == ("Civil Procedure Rules", None)
    assert split_title_year("1996") == ("1996", None)
