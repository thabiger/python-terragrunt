import os
import logging
import subprocess

logger = logging.getLogger(__name__)

def execute(cmd, cwd=""):
    result = {}

    pipe_r, pipe_w = os.pipe()

    if sys.version_info < (3, 5, 0):
        terragrunt = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=pipe_w)
        result['output'] = terragrunt.stdout.read()
        terragrunt.poll()
        result['code'] = terragrunt.returncode == 0
    else:
        terragrunt = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=pipe_w)
        result['output'] = terragrunt.stdout
        result['code'] = terragrunt.returncode == 0

    # terragrunt sends its informational output to stderr which is logged here
    os.close(pipe_w)
    with os.fdopen(pipe_r) as fp:
        for line in fp:
            level = (logging.INFO, logging.ERROR)[result['code'] == 0]
            logger.log(level, line.rstrip())

    return result

