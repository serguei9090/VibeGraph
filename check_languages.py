from tree_sitter_languages import get_language

languages = [
    "python",
    "javascript",
    "typescript",
    "tsx",
    "go",
    "rust",
    "java",
    "c",
    "cpp",
    "c_sharp",
    "ruby",
    "php",
    "bash",
    "json",
    "yaml",
    "html",
    "css",
]

supported = []
for lang in languages:
    try:
        get_language(lang)
        supported.append(lang)
    except Exception as e:
        print(f"{lang}: {e}")

print("\nSupported languages:")
for lang in supported:
    print(f"  - {lang}")
