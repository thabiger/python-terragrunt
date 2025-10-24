#
#  Copyright (c) 2022-2025 Tomasz Habiger and contributors
#

import logging
import objectpath

logger = logging.getLogger(__name__)

class ObjectPath:
    @staticmethod
    def load(obj=None):
        rv = None

        try:
            rv = objectpath.Tree(obj)
        except Exception as e:
            logger.error(f"Failed to convert selected object into ObjectPath resource: {e}")

        return rv

    @staticmethod
    def query(obj=None, q=None):
        rv = None

        try:
            tmp = ObjectPath.load(obj)
            rv = tuple(tmp.execute(q))
        except Exception as e:
            logger.error(f"Failed to execute query \"{q}\" on selected object: {e}")

        return rv
