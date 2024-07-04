import os
import logging

def handle_browser_task(runtime):
    if runtime.browser and runtime.browser.eval_dir:
        logging.info(f'Evaluation directory: {runtime.browser.eval_dir}')
        with open(
            os.path.join(runtime.browser.eval_dir, 'goal.txt'), 'r', encoding='utf-8'
        ) as f:
            task = f.read()
            logging.info(f'Dynamic Eval task: {task}')
            return task
    return None

