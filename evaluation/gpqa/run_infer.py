"""Overview:
This code implements the evaluation of agents on the GPQA Benchmark with Open Book setting.
- The benchmark consists of 448 high-quality and extremely difficult multiple-choice questions in the domains of biology, physics, and chemistry. The questions are intentionally designed to be "Google-proof," meaning that even highly skilled non-expert validators achieve only 34% accuracy despite unrestricted access to the web.
- Even experts in the corresponding domains achieve only 65% accuracy.
- State-of-the-art AI systems achieve only 39% accuracy on this challenging dataset.

Accurate solving of above graduate level questions would require both tool use (e.g., python for calculations) and web-search for finding related facts as information required for the questions might not be part of the LLM knowledge / training data.

Further references:
- https://arxiv.org/pdf/2311.12022
- https://paperswithcode.com/dataset/gpqa
- https://github.com/idavidrein/gpqa

TODOs:
- Add evaluation on other Agent classes
- Batch inference and evaluation of agents on the GPQA Benchmark.
"""

import asyncio
import logging
import os
import pathlib
import random
import re
from typing import Callable

import pandas as pd
from datasets import load_dataset

from evaluation.utils.shared import (
    EvalMetadata,
    codeact_user_response,
    make_metadata,
    prepare_dataset,
    run_evaluation,
)
from opendevin.controller.agent import Agent
from opendevin.controller.state.state import State
from opendevin.core.config import get_llm_config_arg, get_parser, load_app_config
from opendevin.core.logger import get_console_handler
from opendevin.core.logger import opendevin_logger as logger
from opendevin.core.main import run_agent_controller
from opendevin.events.action import Action, AgentFinishAction, MessageAction
from opendevin.events.observation import Observation
from opendevin.llm.llm import LLM

config = load_app_config()

ACTION_FORMAT = """
<<FINAL_ANSWER||
<insert correct answer here, must be one of A, B, C, D> (Please dont use any additional characters. Just the letter of the correct answer (A/B/C/D).)
||FINAL_ANSWER>>
""".strip()


def gpqa_codeact_user_response(
    state: State,
    encapsulate_solution: bool = False,
    try_parse: Callable[[Action], str] | None = None,
) -> str:
    msg = (
        'Please continue working on the task on whatever approach you think is suitable.\n'
        'Feel free to use all tools for calculations and solving the problem, and web-search for finding relevant facts during the process if needed\n'
        'If you have finished reporting the answer in the expected format, (and only once that is done), please run the following command to submit: <execute_bash> exit </execute_bash>.\n'
        'Again you are being told a million times to first report the answer in the requested format (see again below for reference) before exiting. DO NOT EXIT WITHOUT REPORTING THE ANSWER FIRST.\n'
        'That is, when you have decided on the answer report in the following format:\n'
        f'{ACTION_FORMAT}\n'
        '<execute_bash> exit </execute_bash>\n'
        'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP TO SOLVE THIS TASK.\n'
    )

    return msg


AGENT_CLS_TO_FAKE_USER_RESPONSE_FN = {'CodeActAgent': codeact_user_response}

AGENT_CLS_TO_INST_SUFFIX = {
    'CodeActAgent': '\n\n SUPER IMPORTANT: When you think you have solved the question, first report it back to the user in the requested format. Only once that is done, in the next turn, please run the following command: <execute_bash> exit </execute_bash>.\n'
}


def parse_final_answer(final_answer: str | None) -> str | None:
    """Parse the final answer from the final message generated by the agent
    to extract the final answer. The final answer is usually enclosed in the format:
    <<FINAL_ANSWER||
    <insert correct answer here>
    ||FINAL_ANSWER>>
    """
    # to do this first extract the part enclosed in the format <<FINAL_ANSWER|| ... ||FINAL_ANSWER>>
    pattern = re.compile(r'<<FINAL_ANSWER\|\|(.*?)\|\|FINAL_ANSWER>>', re.DOTALL)
    match = pattern.search(final_answer)

    # and then strip it, remove any leading/trailing spaces line breaks etc.
    answer = match.group(1).strip()
    # finally capitalize it
    answer = answer.upper()
    # and then return A, B, C, D depending on whether the answer A, B, C, D is found in the final answer
    for letter in ['A', 'B', 'C', 'D']:
        if letter in answer:
            return letter


def compare_answers(model_output: str | None, ground_truth: str):
    """Compare the predicted answer with the ground truth answer"""
    try:
        # parse the final answer from model output
        predicted_answer = parse_final_answer(model_output)
    except Exception as e:
        # Log the exception
        logger.error(f'An error occurred: {e}\n defaulting to random guess ...')
        # choose a random answer if the model output is not in the correct format
        predicted_answer = random.choice(['A', 'B', 'C', 'D'])

    logger.info('#############################################')
    logger.info(f'Predicted answer: {predicted_answer}')
    logger.info(f'Ground truth answer: {ground_truth}')
    logger.info('#############################################')
    return predicted_answer == ground_truth


def convert_instance_dict(instance):
    """Used for preprocessing the hf dataset into a format that can be used by the agent.
    Reads and extracts relevant information from the dataset instance.
    """
    out_instance_dict = {}
    out_instance_dict['question'] = instance['Question']
    correct_answer = instance['Correct Answer']
    out_instance_dict['choices'] = [
        correct_answer,
        instance['Incorrect Answer 1'],
        instance['Incorrect Answer 2'],
        instance['Incorrect Answer 3'],
    ]

    # Randomize the order of choices
    random.shuffle(out_instance_dict['choices'])

    # Find the index of the correct answer after shuffling and store it as a letter (A/B/C/D)
    correct_index = out_instance_dict['choices'].index(correct_answer)
    correct_letter = chr(
        65 + correct_index
    )  # Convert index (0-3) to corresponding letter (A-D)

    out_instance_dict['correct_solution'] = correct_letter

    return out_instance_dict


def process_instance(
    instance: pd.Series,
    metadata: EvalMetadata,
    reset_logger: bool = True,
):
    # Create the agent
    agent = Agent.get_cls(metadata.agent_class)(llm=LLM(config=metadata.llm_config))
    old_workspace_mount_path = config.workspace_mount_path
    old_workspace_base = config.workspace_base
    try:
        workspace_mount_path = os.path.join(
            config.workspace_mount_path, '_eval_workspace'
        )
        # create process-specific workspace dir
        workspace_mount_path = os.path.join(workspace_mount_path, str(os.getpid()))
        pathlib.Path(workspace_mount_path).mkdir(parents=True, exist_ok=True)

        # reset workspace to config
        config.workspace_base = workspace_mount_path
        config.workspace_mount_path = workspace_mount_path

        # Setup the logger properly, so you can run multi-processing to parallelize the evaluation
        if reset_logger:
            # Set up logger
            log_file = os.path.join(
                metadata.eval_output_dir, 'logs', f'instance_{instance.instance_id}.log'
            )
            # Remove all existing handlers from logger
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            # add back the console handler to print ONE line
            logger.addHandler(get_console_handler())
            logger.info(
                f'Starting evaluation for instance {instance.instance_id}.\nHint: run "tail -f {log_file}" to see live logs in a separate shell'
            )
            # Remove all existing handlers from logger
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            logger.addHandler(file_handler)
        else:
            logger.info(f'Starting evaluation for instance {instance.instance_id}.')

        logger.info(f'Process-specific workspace mounted at {workspace_mount_path}')

        # ======= Run the agent on the instance =======
        # Prepare instruction for the agent using suggested format in gpqa codebase
        instruction = f"""
What is the correct answer to this question:\n
{instance['question']}\n

Choices:\n
(A) {instance['choices'][0]}\n
(B) {instance['choices'][1]}\n
(C) {instance['choices'][2]}\n
(D) {instance['choices'][3]}\n
\n\n

MOST IMPORTANT: Format your response as follows:
{ACTION_FORMAT}

Additional Instructions:
- Do not try to solve the question in a single step. Break it down into smaller steps.
- You should ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.

- SUPER IMPORTANT: When you have reported the answer to the user in the requested format, (and only once that is done) in the next turn, please run the following command: <execute_bash> exit </execute_bash>.
- Again you are being told a million times to first report the answer in the requested format (see again below for reference) before exiting. DO NOT EXIT WITHOUT REPORTING THE ANSWER FIRST.
    That is, when you have decided on the answer report in the following format:

{ACTION_FORMAT}
<execute_bash> exit </execute_bash>

Again do not quit without reporting the answer first.
Ok now its time to start solving the question. Good luck!
"""

        # Here's how you can run the agent (similar to the `main` function) and get the final task state
        state: State | None = asyncio.run(
            run_agent_controller(
                agent,
                instruction,
                max_iterations=metadata.max_iterations,
                max_budget_per_task=config.max_budget_per_task,
                fake_user_response_fn=AGENT_CLS_TO_FAKE_USER_RESPONSE_FN.get(
                    agent.__class__.__name__
                ),
                sid=f'gptq_{str(instance.instance_id)}',
            )
        )
        assert state is not None, 'State should not be None.'

        # ======= Attempt to evaluate the agent's edits =======

        question_choices = {
            'A': instance['choices'][0],
            'B': instance['choices'][1],
            'C': instance['choices'][2],
            'D': instance['choices'][3],
        }
        # get the final message from the state history (default to empty if not found)
        found_answers = {
            'A': False,
            'B': False,
            'C': False,
            'D': False,
        }
        for event in state.history.get_events(reverse=True):
            if (
                isinstance(event, AgentFinishAction)
                and event.source != 'user'
                and '<<FINAL_ANSWER||' in event.thought
            ):
                final_message = event.thought
                break
            elif (
                isinstance(event, MessageAction)
                and event.source != 'user'
                and '<<FINAL_ANSWER||' in event.content
            ):
                final_message = event.content
                break
            elif isinstance(event, Observation):
                for option, option_text in question_choices.items():
                    if option_text in event.content:
                        found_answers[option] = True
            else:
                final_message = None

        found_options = [option for option, found in found_answers.items() if found]
        logger.info('#############################################')
        logger.info(f'Final message generated by the agent: {final_message}')
        logger.info('#############################################')

        # check if the model output matches the ground truth
        test_result = compare_answers(final_message, instance.correct_solution)
        if final_message is None and len(found_options) > 0:
            _selected = random.choice(found_options)
            # if the final message is None, then the agent did not report the answer in the correct format
            # so we randomly select one of the found options and compare it with the correct solution
            test_result = _selected == instance.correct_solution
            logger.info('#############################################')
            logger.info('Agent did not report the answer in the correct format.')
            logger.info(f'Found options: {found_options}')
            logger.info(f'Selected option: {_selected}')
            logger.info('#############################################')

        logger.info('#############################################')
        logger.info(f'Test result: {test_result}')
        logger.info('#############################################')

        # If you are working on some simpler benchmark that only evaluates the final model output (e.g., in a MessageAction)
        # You can simply get the LAST `MessageAction` from the returned `state.history` and parse it for evaluation.
        if state is None:
            raise ValueError('State should not be None.')

        metrics = state.metrics.get() if state.metrics else None

        # Save the output
        output = {
            'task_id': instance.task_id,
            'instance_id': instance.instance_id,
            'instruction': instruction,
            'metadata': metadata.model_dump(),
            'history': state.history.compatibility_for_eval_history_pairs(),
            'metrics': metrics,
            'error': state.last_error if state and state.last_error else None,
            'test_result': {
                'result': test_result,
                'found_answers': found_answers,
                'last_message': final_message,
            },
        }

    except Exception:
        logger.error('Process instance failed')
        raise
    finally:
        config.workspace_mount_path = old_workspace_mount_path
        config.workspace_base = old_workspace_base
    return output


if __name__ == '__main__':
    parser = get_parser()
    # data split must be one of 'gpqa_main', 'gqpa_diamond', 'gpqa_experts', 'gpqa_extended'
    parser.add_argument(
        '--data-split',
        type=str,
        choices=['gpqa_main', 'gpqa_diamond', 'gpqa_experts', 'gpqa_extended'],
        default='gpqa_diamond',
        help='data split to evaluate, eg. gpqa_diamond',
    )
    args, _ = parser.parse_known_args()

    llm_config = get_llm_config_arg(args.llm_config) if args.llm_config else config.llm
    logger.info(f'Config for evaluation: {config}')

    # NOTE: It is preferable to load datasets from huggingface datasets and perform post-processing
    # so we don't need to manage file uploading to OpenDevin's repo
    dataset = load_dataset('Idavidrein/gpqa', args.data_split)
    gpqa_dataset = dataset['train']
    # preprocess the dataset
    gpqa_dataset = gpqa_dataset.map(convert_instance_dict)
    gpqa_dataset = gpqa_dataset.to_pandas()
    # Add a new column 'instance_id' with the index
    gpqa_dataset['instance_id'] = gpqa_dataset.index
    gpqa_dataset['task_id'] = gpqa_dataset.index
    # gpqa_dataset = dataset['train'].to_pandas().sort_values(by='id').reset_index(drop=True)

    if args.agent_cls != 'CodeActAgent':
        raise ValueError(
            f'Agent class {args.agent_cls} not supported for GPQA evaluation.'
        )

    metadata = make_metadata(
        llm_config=llm_config,
        dataset_name=args.data_split,
        agent_class=args.agent_cls,
        max_iterations=args.max_iterations,
        eval_note=args.eval_note,
        eval_output_dir=args.eval_output_dir,
        data_split=args.data_split,
    )

    output_file = os.path.join(metadata.eval_output_dir, 'output.jsonl')
    prepared_dataset = prepare_dataset(
        gpqa_dataset, output_file, args.eval_n_limit, 'task_id'
    )

    run_evaluation(
        dataset=prepared_dataset,
        metadata=metadata,
        output_file=output_file,
        num_workers=args.eval_num_workers,
        process_instance_func=process_instance,
        id_column='task_id',
    )
