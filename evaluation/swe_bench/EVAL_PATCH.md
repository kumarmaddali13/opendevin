# Evaluate Generated Patches

## Evaluate patches generated by OpenDevin

This section explains in detail how `evaluation/swe_bench/scripts/eval_infer.sh` described in [SWE-Bench README](./README.md) works.

Use `scripts/setup/get_agent_report.sh` to evaluate patches generated by an OpenDevin agent. This script is available in the container at `/swe_util/get_agent_report.sh`.

- `output-file` (*required*): specify the path to your patch file inside the container
- `agent-name` (*required*): your agent name
- `dataset` (*required*): `swe-bench-test-lite` or `swe-bench-test`
- `num-processes`: defaults to 15.
- `experiment-name`: set to `${parent_folder_of_output_fils}_${current_folder_of_output_file}` if not given. E.g., `xxx/CodeActAgent/gpt-4-1106-preview_maxiter_50_N_v2_cd/output.jsonl` -> `CodeActAgent_gpt-4-1106-preview_maxiter_50_N_v2_cd` as experiment name.
- `merge_report`: if set, merges the evaluation report into the original output jsonl file and saves as a `.merged.jsonl` file.

An example to run evaluation on the given example agent output (`./examples/example_agent_output.json`).

```shell
export MINICONDA3=/swe_util/miniforge3
export OD_SWE_BENCH=/OD-SWE-bench
export EVAL_DATA_DIR=/swe_util/eval_data
cd /swe_util && ./get_agent_report.sh --output-file /swe_bench_output/example_agent_output.jsonl \
--agent-name CodeActAgent \
--dataset swe-bench-test-lite \
--experiment-name test_experiment \
--merge-report
```

You should get the following report:
```shell
- no_generation: 4
- generated: 26
- with_logs: 26
- install_fail: 0
- reset_failed: 0
- no_apply: 0
- applied: 24
- test_errored: 0
- test_timeout: 0
- resolved: 6
['sphinx-doc__sphinx-8721', 'sympy__sympy-14774', 'django__django-17087', 'sympy__sympy-20590', 'django__django-11583', 'sympy__sympy-21612']
Report saved at /swe_util/eval_data/eval_logs/test_experiment/test_experiment_swe-bench-test-lite.report.json
Agent output with report merged created at /swe_bench_output/example_agent_output.merged.jsonl
```

An additional `fine_grained_report` field will be added to each instance in the `example_agent_output.merged.jsonl`.

```json
"fine_grained_report": {
  "gold_tests": {
    "FAIL_TO_PASS": "[\"tests/test_ext_viewcode.py::test_viewcode_epub_default\"]",
    "PASS_TO_PASS": "[\"tests/test_ext_viewcode.py::test_viewcode_epub_enabled\", \"tests/test_ext_viewcode.py::test_linkcode\", \"tests/test_ext_viewcode.py::test_local_source_files\"]"
  },
  "generated": true,
  "with_logs": true,
  "applied": true,
  "test_errored": false,
  "test_timeout": false,
  "resolved": true,
  "log_parse": {
    "tests/test_ext_viewcode.py::test_viewcode_epub_default": "PASSED",
    "tests/test_ext_viewcode.py::test_viewcode_epub_enabled": "PASSED",
    "tests/test_ext_viewcode.py::test_linkcode": "PASSED",
    "tests/test_ext_viewcode.py::test_local_source_files": "PASSED",
    "tests/test_ext_viewcode.py::test_viewcode": "FAILED"
  },
  "eval_report": {
    "FAIL_TO_PASS": {
      "success": [
        "tests/test_ext_viewcode.py::test_viewcode_epub_default"
      ],
      "failure": []
    },
    "PASS_TO_PASS": {
      "success": [
        "tests/test_ext_viewcode.py::test_viewcode_epub_enabled",
        "tests/test_ext_viewcode.py::test_linkcode",
        "tests/test_ext_viewcode.py::test_local_source_files"
      ],
      "failure": []
    },
    "FAIL_TO_FAIL": {
      "success": [],
      "failure": []
    },
    "PASS_TO_FAIL": {
      "success": [],
      "failure": []
    }
  }
}
```

## If you already have patches not generated by OpenDevin

### Prepare Output Files

Ensure that model outputs are formatted correctly as below:
```json
[
  {
    "instance_id": "",
    "model_patch": "",
    "model_name_or_path": ""
  },
  ...
]
```
An example can be found [here](./examples/example_model_output.json).

Agent output should be adhere to the OpenDevin format. An example can be found [here](./examples/example_agent_output.json).

### Set Up the Environment

Before evaluating generated patches, you need to set up the Docker environment. Run the following command to instantiate the Docker container and mount the directory to your output files on the host:

```shell
docker run -it \
-v DIR_TO_YOUR_PATCH_FILES_ON_HOST:/swe_bench_output \
ghcr.io/opendevin/eval-swe-bench:full-v1.2.1 /bin/bash
```

### Evaluate Model Generated Patches

Use `scripts/get_model_report.sh` to evaluate patches generated by a model. This script is located in the container at `/swe_util/get_model_report.sh`.

- `output-file` (*required*): specify the path to your patch file inside the container
- `model-name` (*required*): this must match the `model_name_or_path` in your patch file
- `dataset` (*required*): `swe-bench-test-lite` or `swe-bench-test`
- `num-processes`: defaults to 15.
- `experiment-name`: set to `{model-name}__{dataset}` unless specified

An example to run evaluation on the given example model output (`./examples/example_agent_output.json`).

```shell
export MINICONDA3=/swe_util/miniforge3
export OD_SWE_BENCH=/swe_util/OD-SWE-bench
export EVAL_DATA_DIR=/swe_util/eval_data
cd /swe_util && ./get_model_report.sh --output-file /swe_bench_output/example_model_output.json \
--model-name opendevin \
--dataset swe-bench-test-lite
```

You should get the following report:
```shell
- no_generation: 4
- generated: 26
- with_logs: 26
- install_fail: 0
- reset_failed: 0
- no_apply: 0
- applied: 24
- test_errored: 0
- test_timeout: 0
- resolved: 6
['sphinx-doc__sphinx-8721', 'sympy__sympy-14774', 'django__django-17087', 'sympy__sympy-20590', 'django__django-11583', 'sympy__sympy-21612']
Report saved at /swe_util/eval_data/eval_logs/opendevin__swe-bench-test-lite/example_model_output.report.json
```
Note: please ignore the `no_apply` in the report for now.

The script will generate a `{experiment_name}` folder under `$EVAL_DATA_DIR/eval_logs`
```shell
├── $EVAL_DATA_DIR/eval_logs/$experiment_name
│   ├── $experiment_name.json
│   ├── $experiment_name.report.json
│   ├── $model_name # eval log dir
```

### Evaluate Agent Generated Patches

Use `scripts/setup/get_agent_report.sh` to evaluate patches generated by an agent. This script is available in the container at `/swe_util/get_agent_report.sh`.

- `output-file` (*required*): specify the path to your patch file inside the container
- `agent-name` (*required*): your agent name
- `dataset` (*required*): `swe-bench-test-lite` or `swe-bench-test`
- `num-processes`: defaults to 15.
- `experiment-name`: set to `${parent_folder_of_output_fils}_${current_folder_of_output_file}` if not given. E.g., `xxx/CodeActAgent/gpt-4-1106-preview_maxiter_50_N_v2_cd/output.jsonl` -> `CodeActAgent_gpt-4-1106-preview_maxiter_50_N_v2_cd` as experiment name.
- `merge_report`: if set, merges the evaluation report into the original output jsonl file and saves as a `.merged.jsonl` file.

An example to run evaluation on the given example agent output (`./examples/example_agent_output.json`).

```shell
export MINICONDA3=/swe_util/miniforge3
export OD_SWE_BENCH=/OD-SWE-bench
export EVAL_DATA_DIR=/swe_util/eval_data
cd /swe_util && ./get_agent_report.sh --output-file /swe_bench_output/example_agent_output.jsonl \
--agent-name CodeActAgent \
--dataset swe-bench-test-lite \
--experiment-name test_experiment \
--merge-report
```

You should get the following report:
```shell
- no_generation: 4
- generated: 26
- with_logs: 26
- install_fail: 0
- reset_failed: 0
- no_apply: 0
- applied: 24
- test_errored: 0
- test_timeout: 0
- resolved: 6
['sphinx-doc__sphinx-8721', 'sympy__sympy-14774', 'django__django-17087', 'sympy__sympy-20590', 'django__django-11583', 'sympy__sympy-21612']
Report saved at /swe_util/eval_data/eval_logs/test_experiment/test_experiment_swe-bench-test-lite.report.json
Agent output with report merged created at /swe_bench_output/example_agent_output.merged.jsonl
```

An additional `fine_grained_report` field will be added to each instance in the `example_agent_output.merged.jsonl`.

```json
"fine_grained_report": {
  "gold_tests": {
    "FAIL_TO_PASS": "[\"tests/test_ext_viewcode.py::test_viewcode_epub_default\"]",
    "PASS_TO_PASS": "[\"tests/test_ext_viewcode.py::test_viewcode_epub_enabled\", \"tests/test_ext_viewcode.py::test_linkcode\", \"tests/test_ext_viewcode.py::test_local_source_files\"]"
  },
  "generated": true,
  "with_logs": true,
  "applied": true,
  "test_errored": false,
  "test_timeout": false,
  "resolved": true,
  "log_parse": {
    "tests/test_ext_viewcode.py::test_viewcode_epub_default": "PASSED",
    "tests/test_ext_viewcode.py::test_viewcode_epub_enabled": "PASSED",
    "tests/test_ext_viewcode.py::test_linkcode": "PASSED",
    "tests/test_ext_viewcode.py::test_local_source_files": "PASSED",
    "tests/test_ext_viewcode.py::test_viewcode": "FAILED"
  },
  "eval_report": {
    "FAIL_TO_PASS": {
      "success": [
        "tests/test_ext_viewcode.py::test_viewcode_epub_default"
      ],
      "failure": []
    },
    "PASS_TO_PASS": {
      "success": [
        "tests/test_ext_viewcode.py::test_viewcode_epub_enabled",
        "tests/test_ext_viewcode.py::test_linkcode",
        "tests/test_ext_viewcode.py::test_local_source_files"
      ],
      "failure": []
    },
    "FAIL_TO_FAIL": {
      "success": [],
      "failure": []
    },
    "PASS_TO_FAIL": {
      "success": [],
      "failure": []
    }
  }
}
```