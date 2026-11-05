from evaluations.goal26_minimax_tokenizer import count_messages, load_manifest, load_tokenizer


def test_pinned_minimax_tokenizer_loads_locally_and_counts_unicode() -> None:
    manifest = load_manifest()
    assert manifest["serving_equivalence"] == "unverified"
    assert count_messages("system", "é中文") == len(
        load_tokenizer().apply_chat_template(
            [{"role": "system", "content": "system"}, {"role": "user", "content": "é中文"}],
            tokenize=True,
            add_generation_prompt=True,
        )
    )
