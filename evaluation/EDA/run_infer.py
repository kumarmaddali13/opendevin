import asyncio
import json
import logging
import multiprocessing as mp
import os
import pathlib
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor

# import huggingface_hub
from datasets import load_dataset
from tqdm import tqdm
from transformers import AutoTokenizer

from evaluation.EDA.game import Q20Game, Q20GameCelebrity

# from evaluation.EDA.scorer import question_scorer
from opendevin.controller.state.state import State
from opendevin.core.config import config, get_llm_config_arg, get_parser
from opendevin.core.logger import get_console_handler
from opendevin.core.logger import opendevin_logger as logger
from opendevin.core.main import main
from opendevin.events.action import MessageAction
from opendevin.events.serialization.event import event_to_dict
from opendevin.runtime.docker.ssh_box import DockerSSHBox

DATASET_CACHE_DIR = '~/.cache/open-devin/evals/eda'
DATASET_CACHE_DIR = os.path.expanduser(DATASET_CACHE_DIR)


def cleanup():
    print('Cleaning up child processes...')
    for process in mp.active_children():
        print(f'Terminating child process: {process.name}')
        process.terminate()
        process.join()


def codeact_user_response(state: State) -> str:
    msg = (
        'Please continue working on the task on whatever approach you think is suitable.\n'
        'If you think you have solved the task, please run the following command: <execute_bash> exit </execute_bash>.\n'
        'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP OR USE THE INTERNET TO SOLVE THIS TASK.\n'
    )
    if state.history:
        user_msgs = [
            action
            for action, _ in state.history
            if isinstance(action, MessageAction) and action.source == 'user'
        ]
        if len(user_msgs) >= 2:
            # let the agent know that it can give up when it has tried 3 times
            return (
                msg
                + 'If you want to give up, run: <execute_bash> exit </execute_bash>.\n'
            )
    return msg


def monologue_user_response(state: State) -> str:
    raise NotImplementedError('MonologueAgent should never ask for user responses.')


AGENT_CLS_TO_FAKE_USER_RESPONSE_FN = {
    'CodeActAgent': codeact_user_response,
    'MonologueAgent': monologue_user_response,
}

AGENT_CLS_TO_INST_SUFFIX = {
    'CodeActAgent': 'When you think you have solved the question, please first send your answer to user through message and then exit.\n'
}


def process_instance(
    instance, agent_class, metadata, skip_workspace_mount, reset_logger: bool = True
):
    workspace_mount_path = os.path.join(config.workspace_mount_path, '_eval_workspace')
    # create process-specific workspace dir
    # if `not skip_workspace_mount` - we will create a workspace directory for EACH process
    # so that different agent don't interfere with each other.
    if not skip_workspace_mount:
        workspace_mount_path = os.path.join(workspace_mount_path, str(os.getpid()))
        pathlib.Path(workspace_mount_path).mkdir(parents=True, exist_ok=True)

    # Setup the logger properly, so you can run multi-processing to parallize the evaluation
    eval_output_dir = metadata['eval_output_dir']
    if reset_logger:
        # Set up logger
        log_file = os.path.join(
            eval_output_dir, 'logs', f'instance_{instance["text"]}.log'
        )
        # Remove all existing handlers from logger
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        # add back the console handler to print ONE line
        logger.addHandler(get_console_handler())
        logger.info(
            f'Starting evaluation for instance {instance["text"]}.\nLOG:   tail -f {log_file}'
        )
        # Remove all existing handlers from logger
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(file_handler)

    if not skip_workspace_mount:
        logger.info(f'Process-specific workspace mounted at {workspace_mount_path}')

    sandbox = DockerSSHBox()

    # Prepare instruction
    _game_class = {'things': Q20Game, 'celebs': Q20GameCelebrity}

    guesser_kargs = {
        'max_new_tokens': 64,
        'temperature': 0.8,
        'repetition_penalty': 1.0,
        'do_sample': True,
    }  # no penalty

    # TODO: use codeactagent as guesser_model, and set up openai_api
    guesser_model = 'gpt-3.5-turbo'
    openai_api = config.config['OPENAI_API_KEY']
    game = _game_class[metadata['dataset']](
        item=instance['text'],
        answerer_model=metadata['answerer_model'],
        guesser_model=guesser_model,
        guesser_tokenizer=AutoTokenizer.from_pretrained(guesser_model, use_fast=False),
        num_turns=metadata['max_iterations'],
        openai_api=openai_api,
        guesser_kargs=guesser_kargs,
    )

    instruction = f'{game.first_user_utterance}'
    logger.info(f'Instruction: {instruction}')
    instruction += 'IMPORTANT: You should ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.\n'
    # NOTE: You can actually set slightly different instruction for different agents
    instruction += AGENT_CLS_TO_INST_SUFFIX.get(agent_class, '')

    # Here's how you can run the agent (similar to the `main` function) and get the final task state
    # TODO: convert Q20 game logic into codeactagent
    state: State = asyncio.run(
        main(
            instruction,
            fake_user_response_fn=AGENT_CLS_TO_FAKE_USER_RESPONSE_FN.get(agent_class),
            sandbox=sandbox,
        )
    )
    # ======= Attempt to evaluate the agent's edits =======
    # If you are working on simplier benchmark that only evaluates the final model output (e.g., in a MessageAction)
    # You can simply get the LAST `MessageAction` from the returned `state.history` and parse it for evaluation.

    if state is None:
        raise ValueError('State should not be None.')

    final_message = ''
    for act in reversed(state.history):
        if isinstance(act, MessageAction):
            final_message = act.content
            break
    logger.info(
        f'Final message: {final_message} | Ground truth: {instance["Final answer"]}'
    )
    test_result = game.reward()

    # Save the output
    output = {
        'instance_id': instance['text'],
        'instance': instance,
        'instruction': instruction,
        'metadata': metadata,
        'history': [
            (event_to_dict(action), event_to_dict(obs)) for action, obs in state.history
        ],
        'error': state.error if state and state.error else None,
        'test_result': test_result,
    }

    # Close the sandbox
    sandbox.close()
    return output


if __name__ == '__main__':
    parser = get_parser()
    parser.add_argument(
        '--answerer_model', '-a', default='gpt-3.5-turbo', help='answerer model'
    )
    # parser.add_argument(
    #     "--turns", type=int, default=20, help="Set the maximum number of turns for the game"
    # )
    parser.add_argument(
        '--dataset',
        default='things',
        choices=['things', 'celebs'],
        type=str,
        help='dataset to be used',
    )
    parser.add_argument(
        '--data-split',
        default='test',
        type=str,
        help='data split, eg, test',
    )
    args, _ = parser.parse_known_args()
    if args.directory:
        config.workspace_base = os.path.abspath(args.directory)
        print(f'Setting workspace base to {config.workspace_base}')
    # NOTE: It is preferable to load datasets from huggingface datasets and perform post-processing
    # so we don't need to manage file uploading to OpenDevin's repo
    eda_dataset = load_dataset(
        'yizheapple/entity-deduction-arena', name=args.dataset, split=args.data_split
    )
    logger.info(
        f'Evaluating Entity Deduction Arena {args.dataset} {args.data_split} split'
    )

    # Check https://github.com/OpenDevin/OpenDevin/blob/main/evaluation/swe_bench/README.md#configure-opendevin-and-your-llm
    # for details of how to set `llm_config`
    if args.llm_config:
        specified_llm_config = get_llm_config_arg(args.llm_config)
        if specified_llm_config:
            config.llm = specified_llm_config
    logger.info(f'Config for evaluation: {config}')

    # TEST METADATA
    agent_class = args.agent_cls
    assert (
        agent_class in AGENT_CLS_TO_FAKE_USER_RESPONSE_FN
    ), f'Unsupported agent class: {agent_class}'
    model_name = config.llm.model.split('/')[-1]
    max_iterations = args.max_iterations
    eval_note = ''
    if args.eval_note is not None:
        eval_note += '_N_' + args.eval_note
    eval_output_dir = os.path.join(
        args.eval_output_dir,
        'eda',
        agent_class,
        model_name + '_maxiter_' + str(max_iterations) + eval_note,
    )

    pathlib.Path(eval_output_dir).mkdir(parents=True, exist_ok=True)
    pathlib.Path(os.path.join(eval_output_dir, 'logs')).mkdir(
        parents=True, exist_ok=True
    )
    logger.info(f'Using evaluation output directory: {eval_output_dir}')

    metadata = {
        'dataset': args.dataset,
        'data_split': args.data_split,
        'answerer_model': args.answerer_model,
        'agent_class': agent_class,
        'model_name': model_name,
        'max_iterations': max_iterations,
        'eval_output_dir': eval_output_dir,
        'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        # get the commit id of current repo for reproduciblity
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'])
        .decode('utf-8')
        .strip(),
    }
    logger.info(f'Metadata: {metadata}')
    with open(os.path.join(eval_output_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f)

    # LIMIT EVALUATION
    eval_n_limit = args.eval_n_limit
    if eval_n_limit:
        eda_dataset = eda_dataset.select(list(range(eval_n_limit)))
        logger.info(f'Limiting evaluation to first {eval_n_limit} instances.')

    # OUTPUT FILE
    output_file = os.path.join(eval_output_dir, 'output.jsonl')
    logger.info(f'Writing evaluation output to {output_file}')
    finished_items = set()
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in f:
                data = json.loads(line)
                finished_items.add(data['text'])
        logger.warning(
            f'Output file {output_file} already exists. Loaded {len(finished_items)} finished instances.'
        )
    output_fp = open(output_file, 'a')

    logger.info(
        f'Evaluation started with Agent {agent_class}, model {model_name}, max iterations {max_iterations}.'
    )

    # =============================================
    # filter out finished instances
    new_eda_dataset = []
    for instance in eda_dataset:
        if instance['text'] in finished_items:
            logger.info(
                f'Skipping instance {instance["text"]} as it is already finished.'
            )
            continue
        new_eda_dataset.append(instance)

    eda_dataset = new_eda_dataset
    logger.info(
        f'Finished instances: {len(finished_items)}, Remaining instances: {len(eda_dataset)}'
    )
    # =============================================

    pbar = tqdm(total=len(eda_dataset))

    # This function tracks the progress AND write the output to a JSONL file
    def update_progress(future):
        pbar.update(1)
        output = future.result()
        pbar.set_description(f'Instance {output["instance_id"]}')
        pbar.set_postfix_str(f'Test Result: {output["test_result"]["result"]}')
        logger.info(
            f'Finished evaluation for instance {output["instance_id"]}: {output["test_result"]["result"]}'
        )
        output_fp.write(json.dumps(output) + '\n')
        output_fp.flush()

    # This sets the multi-processing
    num_workers = args.eval_num_workers
    logger.info(f'Using {num_workers} workers for evaluation.')

    # This is SWE-Bench specific - CodeActAgent don't requires mounted workspace to work
    skip_workspace_mount = False
    logger.info(f'Skipping workspace mount: {skip_workspace_mount}')

    try:
        with ProcessPoolExecutor(num_workers) as executor:
            futures = []
            # This is how we perform multi-processing
            for instance in eda_dataset:
                future = executor.submit(
                    process_instance,
                    instance,
                    agent_class,
                    metadata,
                    skip_workspace_mount,
                    reset_logger=bool(num_workers > 1),
                )
                future.add_done_callback(update_progress)
                futures.append(future)

            # Wait for all futures to complete
            for future in futures:
                future.result()
    except KeyboardInterrupt:
        print('KeyboardInterrupt received. Cleaning up...')
        cleanup()

    output_fp.close()
    logger.info('Evaluation finished.')
