#
#  Copyright (c) 2025 Wojciech Moczulski
#

import asyncio
import logging
import re
import shlex
import sys
from subprocess import run, CalledProcessError

logger = logging.getLogger(__name__)

TERRAGRUNT_BINARY = "terragrunt"

class Process:
    def __init__(self, cwd=None, cmd=None, opts='', tfcmd=None, tfopts=''):
        assert (cmd is not None) and (len(cmd) > 0), f"cmd: cannot be None or empty string, got: {cmd}"

        self.tg_cwd = cwd
        self.tg_cmd = shlex.split(cmd)
        self.tg_opts = shlex.split(opts)

        self.tf_cmd = tfcmd
        self.tf_opts = shlex.split(tfopts)

        self.output = None
        self.version = self.get_version()

    def get_version(self):
        rv = None

        cmd = [TERRAGRUNT_BINARY, "-v"]
        try:
            rematch = re.search(
                r'(\d+)\.(\d+)\.(\d+)',
                run(cmd, cwd=self.tg_cwd, capture_output=True, text=True).stdout
            )
            rv = int(rematch.group(1)), int(rematch.group(2)), int(rematch.group(3))
            logger.debug(f"got terragrunt's version signature: {rematch.group(0)}")
        except CalledProcessError as e:
            logger.error(f"Cannot run terragrunt process to determine its version: {e}")
        except AttributeError as e:
            logger.error(f"Could not extract valid terragrunt's version: {e}")

        return rv

    def exec(self, live=False, std=False):
        rv = 0

        if self.version < (0, 73, 0):
            # https://github.com/gruntwork-io/terragrunt/releases/tag/v0.73.0
            cmd = list(filter(None, [
                TERRAGRUNT_BINARY,
                *self.tg_cmd, *self.tg_opts, self.tf_cmd, *self.tf_opts
            ]))
        else:
            cmd = list(filter(None, [
                TERRAGRUNT_BINARY,
                *self.tg_cmd, *self.tg_opts, "--" if self.tf_cmd else None, self.tf_cmd, *self.tf_opts
            ]))

        logger.debug(f"executing: terragrunt {cmd}")
        try:
            if live:
                asyncio.run(self._builtin_exec_live(cmd=cmd[1:], std=std))
            else:
                self.output = run(cmd, cwd=self.tg_cwd, capture_output=True, text=True)
        except CalledProcessError:
            rv = 1

        return rv

    async def _builtin_exec_poll_stream(self, stream, callback):
        while True:
            l = await stream.readline()
            if l:
                callback(l.decode("utf-8"))
            else:
                break

    async def _builtin_exec_live(self, cmd=None, std=False):
        p = await asyncio.create_subprocess_exec(
            TERRAGRUNT_BINARY, *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=self.tg_cwd
        )

        await asyncio.gather(
            self._builtin_exec_poll_stream(
                p.stdout,
                lambda out: sys.stdout.write(out) if std else logger.log(logging.INFO, out.rstrip())
            ),
            self._builtin_exec_poll_stream(
                p.stderr,
                lambda err: sys.stderr.write(err) if std else logger.log(logging.ERROR, err.rstrip())
            )
        )

        return await p.wait()
