import os


def analysis_size(size_str):
    size_str = size_str.strip()
    avails = {
        'B': 1,
        'Byte': 1,
        'K': 1024,
        'KB': 1024,
        'M': 1024 * 1024,
        'MB': 1024 * 1024,
        'G': 1024 * 1024 * 1024,
        'GB': 1024 * 1024 * 1024,
        'T': 1024 * 1024 * 1024 * 1024,
        'TB': 1024 * 1024 * 1024 * 1024,
        'P': 1024 * 1024 * 1024 * 1024 * 1024,
        'PB': 1024 * 1024 * 1024 * 1024 * 1024,
    }
    for size_unit in avails:
        if size_str.endswith(size_unit):
            return int(size_str[: -len(size_unit)]) * avails[size_unit]
    return int(size_str)


def compare_results(check_method: str, model_answer: str, final_ans: str) -> bool:
    try:
        match check_method:
            case 'check/integer-match.py':
                return int(model_answer) == int(final_ans)
            case 'check/size-match.py':
                return analysis_size(model_answer) == analysis_size(final_ans)
        return (
            model_answer.replace('\r\n', '\n').replace('\r', '\n').strip()
            == final_ans.replace('\r\n', '\n').replace('\r', '\n').strip()
        )
    except Exception:
        return False


def create_sh_file(filename: str, cmds: str) -> None:
    with open(filename, 'w') as file:
        file.write(f'{cmds}\n')
    os.chmod(filename, 0o755)
