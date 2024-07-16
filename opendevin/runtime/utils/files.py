import os
from typing import List, Optional

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from scipy.spatial.distance import cosine
from sentence_transformers import SentenceTransformer

default_exclude = {
    '.git',
    '.DS_Store',
    '.svn',
    '.hg',
    '.idea',
    '.vscode',
    '.settings',
    '.pytest_cache',
    '__pycache__',
    'node_modules',
    'vendor',
    'build',
    'dist',
    'bin',
    'logs',
    'log',
    'tmp',
    'temp',
    'coverage',
    'venv',
    'env',
}


def list_files(full_path: str, entries: Optional[List[str]] = None) -> List[str]:
    # Check if .gitignore exists
    gitignore_path = os.path.join(full_path, '.gitignore')
    if os.path.exists(gitignore_path):
        # Use PathSpec to parse .gitignore
        with open(gitignore_path, 'r') as f:
            spec = PathSpec.from_lines(GitWildMatchPattern, f.readlines())
    else:
        # Fallback to default exclude list if .gitignore doesn't exist
        spec = PathSpec.from_lines(GitWildMatchPattern, default_exclude)

    if not entries:
        entries = os.listdir(full_path)

    # Filter entries using PathSpec
    filtered_entries = [
        entry
        for entry in entries
        if not spec.match_file(os.path.relpath(entry, str(full_path)))
    ]

    # Separate directories and files
    directories = []
    files = []
    for entry in filtered_entries:
        # Remove leading slash and any parent directory components
        entry_relative = entry.lstrip('/').split('/')[-1]

        # Construct the full path by joining the base path with the relative entry path
        full_entry_path = os.path.join(full_path, entry_relative)
        if os.path.exists(full_entry_path):
            is_dir = os.path.isdir(full_entry_path)
            if is_dir:
                directories.append(entry)
            else:
                files.append(entry)

    # Sort directories and files separately
    directories.sort(key=lambda s: s.lower())
    files.sort(key=lambda s: s.lower())

    # Combine sorted directories and files
    sorted_entries = directories + files
    return sorted_entries


def find_relevant_files(query: str, path: str, top_n: int = 5):
    if os.listdir(path) == []:
        print('Empty workspace')
        return []
    cwd = os.getcwd()
    os.chdir(path)
    model = SentenceTransformer('all-MiniLM-L6-v2')

    code_embeddings = {}
    for root, dirs, files in os.walk('.', topdown=True):
        dirs[:] = [d for d in dirs if d not in default_exclude]
        for file_name in files:
            full_path = os.path.join(root, file_name)
            try:
                with open(full_path, 'r') as file:
                    code_content = file.read()
                    print(f'Generating embedding for {full_path}')
                    embedding = model.encode(code_content)
                    code_embeddings[full_path] = embedding
            except Exception as e:
                print(f'Error reading {full_path}: {e}')
    os.chdir(cwd)
    query_embedding = model.encode(query)
    similarities = {}
    for file_name, embedding in code_embeddings.items():
        similarity = 1 - cosine(query_embedding, embedding)
        similarities[file_name] = similarity
    sorted_items = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
    sorted_files = [file for file, score in sorted_items[:top_n] if score > 0.2]
    if not sorted_files and sorted_items:
        return [sorted_items[0][0]]
    return sorted_files


if __name__ == '__main__':
    query = 'enhance chromadb'
    relevant_files = find_relevant_files(query, 'opendevin')
    print(f"Relevant files: {', '.join(relevant_files)}")
