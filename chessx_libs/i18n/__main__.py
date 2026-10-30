from .selftest import run, EXPECTED_KEYS

if __name__ == "__main__":
    run()
    print(f"i18n selftest OK: {EXPECTED_KEYS} keys x en/pt/ja, set_lang, fallback")
