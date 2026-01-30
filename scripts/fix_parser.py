from pathlib import Path

file_path = Path(r'i:\01-Master_Code\Test-Labs\VibeGraph\src\vibegraph\indexer\parser.py')
with open(file_path, encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences of module node ID generation that lack the kind="module" argument
# but ONLY if they use module_name (which means they were already updated to use canonical names)
target = 'file_module_id = self._get_id(file_path, module_name)'
replacement = 'file_module_id = self._get_id(file_path, module_name, kind="module")'

new_content = content.replace(target, replacement)

if new_content == content:
    print("No changes made. Pattern not found.")
else:
    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print("Successfully updated parser.py")
