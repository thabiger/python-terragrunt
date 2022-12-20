import os
import json
import objectpath
import logging
import hcl
import hcl2
import re
from . import s3
from . import utils
from lark import UnexpectedToken, UnexpectedCharacters

logger = logging.getLogger(__name__)

class State:

    def __init__(self, path = None):
        self.path = path
        self.common_rsc = None
        self.state = self.get_remote_state_config()

    def get_remote_state_config(self):

        regex = "terra(form|grunt)\.(tfvars|hcl)$"
        state = []

        def search_up():
            if not self.common_rsc:
                for fd in list(reversed(utils.listfiles(dir=self.path + "/..", way="up", regex=regex))):
                    self.common_rsc = State.query_object(self.load_hcl(fd), "$..remote_state..config")
                    break
            return self.common_rsc

        for f in list(reversed(utils.listfiles(dir=self.path, regex=regex))):
            h = self.load_hcl(f)
            key = '/'.join(re.sub(os.path.abspath(self.path + "/.."), '', f).split('/')[0:-1])[1:]
            rsc = State.query_object(h, "$..remote_state..config")

            # if remote_state cannot be found within the directory,
            # try to search the director tree up
            if not rsc and '${find_in_parent_folders()}' in State.query_object(h, "$..include.path"):
                rsc = search_up()

            sr = s3.get(rsc[0]['bucket'], "%s/terraform.tfstate" % key)
            if sr:
              state.append(json.loads(sr))
            else:
                logger.error("Couldn't find a state file in expected path. Terraform code not initiated yet or deprecated.")

        if state:
            return objectpath.Tree(state)

    @staticmethod
    def query_object(o, q):
        try:
            op = objectpath.Tree(o)
            return tuple(op.execute(q))
        except Exception as e:
            print ("Failed to query the object")

    def query(self, q):
        return tuple(self.state.execute(q))

    def load_hcl(self, file):

        skippable_exceptions = (
            UnexpectedToken,
            UnexpectedCharacters,
            UnicodeDecodeError
        )

        with open(file) as f:
            c = re.sub("\s+\\?", " ?", f.read(), re.MULTILINE)
            for h in [hcl2.loads, hcl.loads]:
                try:
                   return h(c)
                except skippable_exceptions:
                    continue
                except Exception as e:
                    print(e)

    def get_resources(self, type_name, id_name = None):
        """ get resource ids list, based on type_name and id_name

            type_name: str, ie. aws_instance, aws_autoscaling_group, aws_db_instance. etc.
            id_name: id attribute identificator of the resource. most often it is just 'id', but there are resources
                    like 'aws_spot_instance_request', where id refers to a request id, not an instance id.
                    if we'd like to get instance id, we have to provide alternative id name, which is 'spot_instance_id'
                    in this case.

            returns: list of resources ids, ie. for ec2: ('i-08bf03c667b7eab43', 'i-8bg023c6d66bheac42')
        """

        id_name = id_name if id_name else 'id'

        try:
            if re.match('0.11.[0-9]+', self.state.execute("$..terraform_version[0]")):
                return tuple(self.state.execute("$..modules.resources..*[@.type is '{}'].primary.{}".format(type_name, id_name)))
            else:
                return tuple(self.state.execute("$..resources[@.type is '{}']..instances.attributes.{}".format(type_name, id_name)))
        except AttributeError:
            return None

    def empty(self):
        return False if self.state else True
