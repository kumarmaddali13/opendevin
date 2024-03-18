import os
import pty
import sys
import uuid
import time
import shlex
import select
import subprocess
from typing import List
from collections import namedtuple

InputType = namedtuple("InputDtype", ["content"])
OutputType = namedtuple("OutputDtype", ["content"])


class DockerInteractive:
    CONTAINER_IMAGE = "ubuntu:20.04"

    def __init__(self):
        self.instance_id: str = uuid.uuid4()
        cmd = f"docker run -it --rm --name sandbox-{self.instance_id} {self.CONTAINER_IMAGE} /bin/bash"
        self.master_fd, self.slave_fd = pty.openpty()
        self.container = subprocess.Popen(
            shlex.split(cmd),
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            text=True,
            close_fds=True,
        )
        time.sleep(1)  # wait for the container to start
        # TODO: use a more robust way to check if the container is ready
        self.history: List[InputType | OutputType] = [
            OutputType(self._wait_and_read_output())
        ]

    def _wait_and_read_output(self, user_input: str = None) -> str:
        output_str = ""
        while True:
            readable, _, _ = select.select([self.master_fd], [], [], 0.1)
            if readable:
                output = os.read(self.master_fd, 1024).decode()
                if not output:
                    break
                output_str += output
            else:
                break
        if user_input:
            output_str = output_str.lstrip(user_input).lstrip()
        return output_str

    def execute(self, cmd: str) -> str:
        os.write(self.master_fd, (cmd + "\n").encode())
        self.history.append(InputType(cmd))

        output = self._wait_and_read_output(cmd)
        self.history.append(OutputType(output))
        return output

    def close(self):
        os.close(self.master_fd)
        self.container.terminate()
        try:
            self.container.wait(timeout=5)
            print("Container stopped.")
        except subprocess.TimeoutExpired:
            self.container.kill()
            print("Container killed.")


if __name__ == "__main__":
    docker_interactive = DockerInteractive()
    print("Interactive Docker container started. Type 'exit' or use Ctrl+C to exit.")

    for item in docker_interactive.history:
        print(item.content, end="")
    sys.stdout.flush()
    try:
        while True:
            user_input = input()
            if user_input.lower() == "exit":
                print(f"Exiting...")
                break
            output = docker_interactive.execute(user_input)
            print(output, end="")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nExiting...")
    docker_interactive.close()
