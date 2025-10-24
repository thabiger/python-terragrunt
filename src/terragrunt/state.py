#
#  Copyright (c) 2022-2025 Tomasz Habiger and and contributors
#

import os
import json
import logging
import hcl
import hcl2
import re
from lark import UnexpectedToken, UnexpectedCharacters
from .objpath_helper import ObjectPath
from .process import Process as TerragruntProcess
from .s3 import S3

logger = logging.getLogger(__name__)

class State:
    def __init__(self, path=None, path_limit='/', config="root.hcl", key_prefix=None, key_filename='terraform.tfstate', state_as_optree=True):
        self.path = path if path else os.getcwd()
        self.path_limit = path_limit

        self.tfstate_config = config
        self.tfstate_key_prefix = key_prefix
        self.tfstate_key_filename = key_filename

        self.data_as_optree = state_as_optree
        self.data = None

        self.data = self.load()

    def _builtin_hcl_loads(self, content=None):
        rv = None

        skippable_exceptions = (
            UnexpectedToken,
            UnexpectedCharacters,
            UnicodeDecodeError
        )

        config_data = re.sub("\s+\\?", " ?", content, re.MULTILINE)
        for parser in [hcl2.loads, hcl.loads]:
            try:
                rv = parser(config_data)
            except skippable_exceptions:
                continue
            except Exception as e:
                print(f"Failed to parse HCL content: {e}")

        return rv

    def _builtin_hcl_load(self, file=''):
        rv = None

        logger.debug(f"loading HCL file: {file}")
        with open(file) as f:
            rv = self._builtin_hcl_loads(f.read())

        return rv

    def _builtin_search_file(self, fname=""):
        cp = os.path.abspath(self.path)
        relpath = []

        logger.debug(f"searching for file: {fname}")
        for d in list(filter(None, list(reversed(cp.removeprefix(self.path_limit).split('/'))))):
            relpath.insert(0, d)

            cp = cp.removesuffix("/{}".format(d))
            fpath = "{}/{}".format(cp, fname)

            logger.debug(f"checking path: {fpath}")
            if os.path.exists(fpath) and os.path.isfile(fpath) and os.access(fpath, os.F_OK | os.R_OK):
                return fpath, '/'.join(relpath)

        return None, None

    def _builtin_try_render(self, config=None):
        rv = None
        config_data = None
        config_created = False

        tg = TerragruntProcess(cwd=self.path, cmd="render")
        cfg = f"{self.path}/terragrunt.hcl"

        if tg.version >= (0, 77, 18):
            if not os.path.exists(cfg) or not os.path.isfile(cfg):
                with open(cfg, "w") as f:
                    f.write(f"include \"root\" {{\n  path = find_in_parent_folders(\"{config}\")\n}}\n")
                config_created = True
                logger.debug(f"rendered temporal configuration: {cfg}")

            tg.exec(live=False)
            try:
                config_data = self._builtin_hcl_loads(tg.output.stdout)
            except Exception as e:
                logger.warning(f"Cannot parse rendered Terragrunt config: {e}")

            if config_created:
                os.remove(cfg)
                logger.debug(f"removed temporal configuration: {cfg}")

            if config_data:
                tmp = ObjectPath.query(config_data, "$..remote_state..config")
                if tmp:
                    rv = {
                        'bucket': tmp[0]['bucket'],
                        'key': tmp[0]['key']
                    }
                    logger.debug(f"got OpenTofu/Terraform state location: {rv}")
        else:
            logger.warning(
                "Cannot use 'terragrunt render' for state configuration discovery:\n"
                "terragrunt version 0.77.18 or newer is required (installed version: {})".format('.'.join(map(str, tg.version)))
            )

        return rv

    def _builtin_try_search(self, config=None):
        rv = None
        config_data = None

        tfstate_config, tfstate_key_relpath = self._builtin_search_file(config)
        if tfstate_config:
            try:
                config_data = self._builtin_hcl_load(tfstate_config)
            except Exception as e:
                logger.warning(f"Cannot parse Terragrunt config file {tfstate_config}: {e}")

            if config_data:
                tmp = ObjectPath.query(config_data, "$..remote_state..config")
                if tmp:
                    rv = {
                        'bucket': tmp[0]['bucket'],
                        'key': '/'.join(filter(None, [self.tfstate_key_prefix, tfstate_key_relpath, self.tfstate_key_filename]))
                    }
                    logger.debug(f"got (calculated) OpenTofu/Terraform state location: {rv}")

        return rv

    def load(self):
        rv = None
        tfstate_data = []
        tfstate_json = None

        cfg_list = filter(None, [
            self.tfstate_config,
            "root.hcl",
            "terragrunt.hcl",
            "terraform.tfvars"
        ])

        for f in cfg_list:
            logger.debug(f"(mode:render) checking for terragrunt's configuration: {f}")
            rv = self._builtin_try_render(f)
            if rv:
                break

        if rv is None:
            for f in cfg_list:
                logger.debug(f"(mode:search) checking for terragrunt's configuration: {f}")
                rv = self._builtin_try_search(f)
                if rv:
                    break

        if rv is None:
            logger.error("Cannot extract any information about OpenTofu/Terraform state location")

        tfstate_json = S3.get(rv['bucket'], rv['key'])
        if tfstate_json:
            rv = json.loads(tfstate_json)
            if self.data_as_optree:
                tfstate_data.append(rv)
                rv = ObjectPath.load(tfstate_data)
        else:
            logger.error(f"Couldn't load OpenTofu/Terraform state from S3 location s3://{rv['bucket']}/{rv['key']}")
            rv = None

        return rv

    def get_resources(self, type_name, id_name=None):
        """
        Get list of resource IDs

        :param type_name: string, ie. "aws_instance", "aws_autoscaling_group", "aws_db_instance", etc.
        :param id_name: ID attribute identificator for a resource. Most often it is just "id", but
            there are resources like "aws_spot_instance_request", where ID refers to a request ID
            and not an instance ID. If we'd like to get an instance ID, we have to provide alternative
            id_name, like "spot_instance_id" in this case.
        :return: list of resource IDs, ie. for EC2: ('i-08bf03c667b7eab43', 'i-8bg023c6d66bheac42', ...)
        """

        id_name = id_name if id_name else 'id'

        try:
            if re.match('0.11.[0-9]+', self.data.execute("$..terraform_version[0]")):
                return tuple(
                    self.data.execute("$..modules.resources..*[@.type is '{}'].primary.{}".format(
                        type_name, id_name
                    ))
                )
            else:
                return tuple(
                    self.data.execute("$..resources[@.type is '{}']..instances.attributes.{}".format(
                        type_name, id_name
                    ))
                )
        except AttributeError:
            return None

    def is_empty(self):
        return False if self.data else True
